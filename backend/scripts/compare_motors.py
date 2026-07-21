"""
Harness de comparación empírica de motores (Tarea 4).

Genera las secciones 🔴 (por defecto 3, 5, 8, 9) de un proyecto
usando CUALQUIER subconjunto de modelos del catálogo
AVAILABLE_MODELS, y guarda las salidas + métricas para una
revisión humana posterior.

NO decide automáticamente si la bifurcación original Gemini/Claude
sigue justificándose: entrega evidencia, no veredicto.

USO (dentro del backend, con OPENROUTER_API_KEY configurada):

    cd backend
    python -m scripts.compare_motors \
        --project-id <UUID> \
        --models google/gemini-3.1-pro-preview,anthropic/claude-sonnet-5,anthropic/claude-opus-4.8 \
        --sections 3,5,8,9

Los outputs van a:
    comparisons/<timestamp>/
        <model_id>/
            seccion_03.md
            seccion_05.md
            ...
        metrics.json
        comparison_report.md  (borrador, a completar por humano)

MÉTRICAS OBJETIVAS:
  - tokens (input/output), costo (USD), latencia (segundos)
  - find_missing_facts (Tarea 2) contra el checklist del documento
    original como proxy de fidelidad a fuentes
  - longitud del output (caracteres)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.compendium_section import CompendiumSection
from app.models.project import Project
from app.modules.ai_gateway.models import AVAILABLE_MODELS
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.audit.service import (
    find_missing_facts,
    load_active_checklist,
)
from app.modules.prompts.ecos_service import (
    get_active_ecos_map,
    get_ecos_for_section,
    pathology_key_for,
)
from app.modules.prompts.section_builder import (
    DOSIFICATION_MAP,
    MAX_TOKENS_BY_DOSIFICATION,
    SECTION_CONFIGS,
    build_section_instruction,
)
from app.modules.prompts.service import get_active_prompt
from app.services.orchestrator import (
    _build_extra_params,
    _replay_conversation,
)

DEFAULT_RED_SECTIONS = [3, 5, 8, 9]
COMPARISONS_DIR = Path("comparisons")


def _validate_models(model_ids: list[str]) -> list[str]:
    """Verifica que todos los modelos solicitados están en AVAILABLE_MODELS."""
    valid = {m["id"] for m in AVAILABLE_MODELS}
    unknown = [m for m in model_ids if m not in valid]
    if unknown:
        raise ValueError(
            f"Modelos no disponibles en AVAILABLE_MODELS: {unknown}. "
            f"Válidos: {sorted(valid)}"
        )
    return model_ids


def _infer_motor(model_id: str) -> str:
    mid = (model_id or "").lower()
    if "claude" in mid:
        return "claude"
    return "gemini"


async def _generate_section_for_model(
    project: Project,
    sections_by_number: dict[int, CompendiumSection],
    section_number: int,
    model_id: str,
    system_prompt: str,
    patch_gemini: str | None,
    source_filename: str,
    eco_map,
) -> tuple[str, dict]:
    """
    Genera UNA sección con UN modelo. Replica el flujo del
    orchestrator (replay conversación + extra_params) sin
    persistir. Devuelve (contenido, métricas).
    """
    ai = OpenRouterClient()
    motor = _infer_motor(model_id)
    extra_params = _build_extra_params(motor, section_number)

    conv = _replay_conversation(
        project=project,
        sections_by_number=sections_by_number,
        section_number=section_number,
        system_prompt=system_prompt,
        patch_gemini=patch_gemini,
        source_filename=source_filename,
    )

    section_ecos = get_ecos_for_section(eco_map, section_number)
    instruction = build_section_instruction(
        section_number=section_number,
        pathology_name=project.name,
        source_filename=source_filename,
        is_last=(section_number == 11),
        ecos=section_ecos,
    )

    max_tokens = MAX_TOKENS_BY_DOSIFICATION.get(
        DOSIFICATION_MAP.get(
            SECTION_CONFIGS[section_number].dosification_level,
            "STANDARD",
        ),
        8192,
    )

    t0 = time.monotonic()
    ai_result = await ai.generate_in_conversation(
        conversation=conv,
        user_message=instruction,
        model=model_id,
        temperature=0.1,
        max_tokens=max_tokens,
        max_continuations=10,
        **extra_params,
    )
    elapsed = time.monotonic() - t0

    metrics = {
        "model": ai_result.model,
        "input_tokens": ai_result.input_tokens,
        "output_tokens": ai_result.output_tokens,
        "cost_usd": float(ai_result.cost_usd or 0.0),
        "latency_s": round(elapsed, 2),
        "finish_reason": ai_result.finish_reason,
        "content_chars": len(ai_result.content),
        "thinking_enabled": extra_params.get("reasoning", {}).get("enabled", False),
    }
    return ai_result.content, metrics


async def run_comparison(
    project_id: str,
    model_ids: list[str],
    section_numbers: list[int] = DEFAULT_RED_SECTIONS,
) -> Path:
    """
    Ejecuta la comparación. Devuelve el directorio con outputs +
    metrics + report_borrador.
    """
    model_ids = _validate_models(model_ids)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_root = COMPARISONS_DIR / f"{timestamp}_{project_id[:8]}"
    out_root.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        project = (
            await db.execute(
                select(Project).where(Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project '{project_id}' not found")

        system_prompt_rec = await get_active_prompt(
            db, "system_prompt_sam_v9"
        )
        system_prompt = system_prompt_rec.content

        patch_gemini = None
        if SECTION_CONFIGS[1].motor == "gemini":
            patch_rec = await get_active_prompt(db, "patch_gemini_density")
            patch_gemini = patch_rec.content

        pathology_key = pathology_key_for(project.name)
        eco_map = await get_active_ecos_map(db, pathology_key)

        # Cargar checklist del primer documento del proyecto (si
        # existe) para usarlo como métrica objetiva de fidelidad.
        doc_type = (
            project.documents[0].document_type if project.documents else "article"
        )
        _, expected = await load_active_checklist(db, doc_type)

        source_filename = (
            ", ".join(d.filename for d in project.documents)
            if project.documents
            else "N/A"
        )

        all_metrics: dict[str, dict] = {}
        # Para cada modelo, generar TODAS las secciones de la lista.
        for model_id in model_ids:
            safe_model_dir = out_root / model_id.replace("/", "_")
            safe_model_dir.mkdir(exist_ok=True)
            all_metrics[model_id] = {
                "sections": {},
                "aggregate": {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_latency_s": 0.0,
                },
            }

            # Pre-cargar secciones existentes para replay
            sections_by_number: dict[int, CompendiumSection] = {}
            for sec in project.sections:
                sections_by_number[sec.section_number] = sec

            for section_number in section_numbers:
                content, metrics = await _generate_section_for_model(
                    project=project,
                    sections_by_number=sections_by_number,
                    section_number=section_number,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    patch_gemini=patch_gemini,
                    source_filename=source_filename,
                    eco_map=eco_map,
                )
                out_path = (
                    safe_model_dir / f"seccion_{section_number:02d}.md"
                )
                out_path.write_text(content, encoding="utf-8")

                # Métrica objetiva Tarea 2
                if expected:
                    missing = find_missing_facts(content, expected)
                    metrics["missing_facts"] = [
                        f.id for f in missing
                    ]
                    metrics["missing_count"] = len(missing)
                else:
                    metrics["missing_facts"] = None
                    metrics["missing_count"] = None

                all_metrics[model_id]["sections"][
                    section_number
                ] = metrics
                agg = all_metrics[model_id]["aggregate"]
                agg["total_input_tokens"] += metrics["input_tokens"]
                agg["total_output_tokens"] += metrics["output_tokens"]
                agg["total_cost_usd"] += metrics["cost_usd"]
                agg["total_latency_s"] += metrics["latency_s"]

            # Round aggregate
            for k in ("total_cost_usd", "total_latency_s"):
                all_metrics[model_id]["aggregate"][k] = round(
                    all_metrics[model_id]["aggregate"][k], 4
                )

    # Guardar metrics.json
    metrics_path = out_root / "metrics.json"
    metrics_path.write_text(
        json.dumps(all_metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Borrador de reporte (a completar por humano)
    report_path = out_root / "comparison_report.md"
    _write_report_template(report_path, all_metrics, project, model_ids)

    print(f"\n✅ Comparación completada → {out_root}")
    print(f"   Métricas: {metrics_path}")
    print(f"   Reporte (borrador): {report_path}")
    return out_root


def _write_report_template(
    path: Path,
    all_metrics: dict,
    project: Project,
    model_ids: list[str],
) -> None:
    rows = []
    for model_id in model_ids:
        agg = all_metrics[model_id]["aggregate"]
        rows.append(
            f"| `{model_id}` | {agg['total_input_tokens']:,} | "
            f"{agg['total_output_tokens']:,} | "
            f"${agg['total_cost_usd']:.4f} | "
            f"{agg['total_latency_s']:.1f}s |"
        )
    table = "\n".join(rows)

    content = f"""# Comparación empírica de motores — {project.name}

**Proyecto:** `{project.id}`
**Fecha:** {datetime.now(UTC).isoformat()}

## Modelos comparados

{', '.join(f'`{m}`' for m in model_ids)}

## Métricas agregadas (secciones {DEFAULT_RED_SECTIONS})

| Modelo | Input tokens | Output tokens | Costo USD | Latencia total |
| --- | ---: | ---: | ---: | ---: |
{table}

## Métricas por sección y por modelo

Ver `metrics.json` para detalle por sección (incluye
`missing_facts` por sección, calculada con `find_missing_facts`
de la Tarea 2 contra el checklist curado para el tipo de
documento).

## Rúbrica de revisión humana

Por modelo, para cada sección generada:

1. **Fidelidad a fuentes** — ¿Los datos coinciden con el
   `merged_content.md`? ¿Hay alucinaciones numéricas?
2. **Cobertura** — ¿Se desarrollan los temas del MAPA DE ECOS
   sin omitir? (Comparar con `missing_facts`.)
3. **Cumplimiento de las 10 Leyes** (R-1…R-10) — verificación
   manual: ¿respeta referencias cruzadas? ¿cita granular? ¿formato
   callout correcto?
4. **Calidad clínica** — Razonamiento diagnóstico, manejo, dosis.
5. **Latencia / costo** — ¿La diferencia de calidad justifica la
   diferencia de costo/latencia?

## Outputs

- `metrics.json` — métricas machine-readable
- `<model_id>/seccion_NN.md` — contenido completo por modelo y
  sección
"""
    path.write_text(content, encoding="utf-8")


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comparación empírica de motores (Tarea 4)"
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="UUID del proyecto con merged_content listo",
    )
    parser.add_argument(
        "--models",
        required=True,
        type=_parse_csv,
        help=(
            "Lista de IDs de OpenRouter separados por coma. "
            "Deben estar en AVAILABLE_MODELS. Ejemplo: "
            "google/gemini-3.1-pro-preview,anthropic/claude-sonnet-5"
        ),
    )
    parser.add_argument(
        "--sections",
        type=_parse_csv,
        default=DEFAULT_RED_SECTIONS,
        help=(
            f"Lista de secciones a generar. Default: "
            f"{DEFAULT_RED_SECTIONS}"
        ),
    )
    args = parser.parse_args()

    if not settings.openrouter_api_key:
        print(
            "ERROR: OPENROUTER_API_KEY no configurada.",
            file=sys.stderr,
        )
        sys.exit(2)

    asyncio.run(
        run_comparison(
            project_id=args.project_id,
            model_ids=args.models,
            section_numbers=[int(s) for s in args.sections],
        )
    )


if __name__ == "__main__":
    main()
