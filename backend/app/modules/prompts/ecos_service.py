"""
Tarea 3 — Servicio de ecos maps.

Funciones:
  - `pathology_key_for(name)`: normaliza un nombre de proyecto a
    una clave estable para lookup.
  - `get_active_ecos_map(db, pathology_key)`: obtiene el mapa
    aprobado+activo actual (None si no existe).
  - `get_pending_draft(db, pathology_key)`: obtiene el borrador
    pendiente (draft, no activo) más reciente para una patología.
  - `propose_ecos_map(db, ai, pathology_name, source_content)`:
    genera un borrador vía mini-prompt LLM y lo guarda como
    `draft` (origen `autopopulado`). Acepta contenido fuente
    opcional (merged_content) para proponer ecos grounded.
  - `update_ecos_map_draft(db, map_id, sections, description)`:
    edita un borrador existente (draft-only).
  - `validate_ecos_map(draft)`: garantiza cobertura completa de
    los slots del template y propiedad única por sección.
  - `approve_ecos_map(db, map_id, approver_user_id)`: marca como
    approved, asigna versión incrementada, desactiva versiones
    previas.
  - `require_approved_map(db, pathology_key)`: usado por el
    pipeline; lanza EcoMapNotApprovedError si no hay mapa
    aprobado.

Semántica real de los ecos (R-1 "mención ≠ desarrollo"): los ecos
de la sección N son referencias cruzadas a temas YA desarrollados
en secciones ANTERIORES. `validate_ecos_map` exige cobertura con
esa semántica: cada slot de las secciones 1..10 debe aparecer como
eco en alguna sección POSTERIOR a su dueña; la sección 1 va vacía.

`propose_ecos_map` es FAIL-LOUD: si el LLM trunca su respuesta o
no devuelve un JSON parseable con claves de sección, lanza
`EcoMapProposalError` y NO persiste ningún borrador vacío.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ecos_map import EcosMap, EcosMapOrigin, EcosMapStatus
from app.models.project import Project
from app.modules.ai_gateway.models import DEFAULT_ECOS_MAP_MODEL
from app.modules.prompts.ecos_template import ECOS_SECTION_TEMPLATE
from app.modules.prompts.service import get_active_prompt

if TYPE_CHECKING:
    from app.modules.ai_gateway.interfaces import AIGatewayClient


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def pathology_key_for(name: str) -> str:
    """
    Normaliza un nombre de patología a una clave estable.

    Política v1: lowercase + slug básico (sin acentos vía NFKD,
    alfanumérico + guiones). Si en el futuro hace falta un alias
    map (LRA / AKI / Insuficiencia Renal Aguda), se añade aquí.
    """
    if not name:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", _strip_accents(name).lower()).strip("-")
    return slug


def _coerce_ecos_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        # Si llega un string con saltos de línea, partirlo.
        return [
            line.strip("-• \t").strip()
            for line in value.splitlines()
            if line.strip("-• \t").strip()
        ]
    return []


def _normalize_match_text(text: str) -> str:
    """Minúsculas sin acentos, para matching robusto eco ↔ slot."""
    return _strip_accents(text).lower()


def _slot_matches(slot: dict, eco: str) -> bool:
    eco_norm = _normalize_match_text(eco)
    label_norm = _normalize_match_text(slot["label"])
    slot_id_norm = _normalize_match_text(
        slot["slot_id"].replace("_", " ")
    )
    return label_norm in eco_norm or slot_id_norm in eco_norm


def validate_ecos_map(draft_sections: dict) -> tuple[bool, list[str]]:
    """
    Valida un borrador de ecos map contra la SEMÁNTICA REAL de los
    ecos (referencias cruzadas hacia secciones ANTERIORES, R-1
    "mención ≠ desarrollo"):

    - R1: la sección 1 debe ir vacía (no hay secciones anteriores
      que referenciar).
    - Cobertura: cada slot de las secciones 1..10 debe aparecer
      como eco en AL MENOS UNA sección POSTERIOR a su dueña. La
      sección dueña lo DESARROLLA (no se referencia a sí misma);
      las posteriores lo citan como eco. Los slots de la sección
      11 están exentos: no hay secciones posteriores.
    - R7: sin ecos duplicados dentro de una misma sección.

    Returns (ok, problems). Los warnings NO bloquean el guardado
    (el criterio del doctor manda), pero deben ser señales reales:
    un problema reportado aquí indica un riesgo R-1 concreto
    (una sección posterior podría re-desarrollar un tema ya
    cubierto al no ver su eco).
    """
    problems: list[str] = []

    ecos_by_section = {
        n: _coerce_ecos_list(draft_sections.get(str(n)))
        for n in range(1, 12)
    }

    # R1: la sección 1 no tiene secciones anteriores → siempre [].
    if ecos_by_section[1]:
        problems.append(
            "la sección 1 debe ir vacía: no hay secciones "
            "anteriores que referenciar (R1)"
        )

    # R7: duplicados exactos dentro de una misma sección.
    for n, ecos in ecos_by_section.items():
        normalized = [_normalize_match_text(e) for e in ecos]
        if len(normalized) != len(set(normalized)):
            problems.append(
                f"la sección {n} tiene ecos duplicados (R7)"
            )

    # Cobertura: slot de la sección S (S < 11) debe aparecer como
    # eco en alguna sección posterior (S+1 .. 11).
    for section_number, slots in ECOS_SECTION_TEMPLATE.items():
        if section_number >= 11:
            continue
        later_ecos = [
            eco
            for n in range(section_number + 1, 12)
            for eco in ecos_by_section[n]
        ]
        for slot in slots:
            if not any(_slot_matches(slot, eco) for eco in later_ecos):
                problems.append(
                    f"slot '{slot['slot_id']}' no aparece como eco "
                    f"en ninguna sección posterior a su sección "
                    f"dueña ({section_number})"
                )

    return (len(problems) == 0, problems)


async def get_active_ecos_map(
    db: AsyncSession, pathology_key: str
) -> EcosMap | None:
    if not pathology_key:
        return None
    result = await db.execute(
        select(EcosMap).where(
            EcosMap.pathology_key == pathology_key,
            EcosMap.is_active,
            EcosMap.status == EcosMapStatus.APPROVED,
        )
    )
    return result.scalar_one_or_none()


async def get_pending_draft(
    db: AsyncSession, pathology_key: str
) -> EcosMap | None:
    """Obtiene el borrador pendiente (draft, no activo) más reciente."""
    if not pathology_key:
        return None
    result = await db.execute(
        select(EcosMap)
        .where(
            EcosMap.pathology_key == pathology_key,
            EcosMap.status == EcosMapStatus.DRAFT,
            EcosMap.is_active == False,  # noqa: E712
        )
        .order_by(EcosMap.version.desc())
    )
    return result.scalars().first()


async def require_approved_map(
    db: AsyncSession, pathology_key: str
) -> EcosMap:
    """
    Usado por el pipeline de generación. Si no hay mapa aprobado
    activo, lanza RuntimeError con mensaje accionable. El caller
    (compendiums service) traduce a HTTPException 409 con sugerencia
    del endpoint de auto-poblado.
    """
    eco_map = await get_active_ecos_map(db, pathology_key)
    if eco_map is None:
        raise EcoMapNotApprovedError(
            f"No existe ecos_map aprobado+activo para patología "
            f"'{pathology_key}'. Genera un borrador con "
            f"POST /api/v1/pathologies/{{key}}/ecos-map:propose "
            f"y apruébalo antes de generar el compendio."
        )
    return eco_map


class EcoMapNotApprovedError(Exception):
    """No hay eco map aprobado para la patología; bloquear generación."""


class EcoMapProposalError(Exception):
    """
    El LLM no produjo un borrador utilizable (respuesta truncada,
    JSON no parseable o sin claves de sección). Se lanza en lugar
    de persistir un borrador vacío (fail-loud, nunca fail-silent).
    """


def _has_section_keys(draft: dict) -> bool:
    """True si el dict parseado contiene al menos una clave '1'..'11'."""
    return isinstance(draft, dict) and any(
        str(n) in draft for n in range(1, 12)
    )


async def find_project_for_pathology(
    db: AsyncSession, pathology_key: str
) -> Project | None:
    """
    Devuelve el proyecto más reciente cuya `pathology_key` (derivada
    de su nombre) coincide; prefiere proyectos con `merged_content`
    para que el propose manual sea grounded como el auto-propose.
    None si ningún proyecto corresponde a esa patología.
    """
    if not pathology_key:
        return None
    result = await db.execute(
        select(Project).order_by(Project.updated_at.desc())
    )
    candidates = [
        p
        for p in result.scalars().all()
        if pathology_key_for(p.name) == pathology_key
    ]
    if not candidates:
        return None
    with_content = [
        p for p in candidates if (p.merged_content or "").strip()
    ]
    return (with_content or candidates)[0]


async def propose_ecos_map(
    db: AsyncSession,
    ai: AIGatewayClient,
    pathology_name: str,
    source_content: str | None = None,
    model: str | None = None,
) -> EcosMap:
    """
    Genera un borrador de ecos map vía mini-prompt LLM. El
    `ecos_map_autopopulate` debe estar sembrado en
    `prompt_templates` (type='ecos_map').

    Si se proporciona `source_content` (extracto de merged_content),
    el LLM priorizará ecos para temas realmente cubiertos por las
    fuentes documentales del proyecto ("grounded propose").

    Raises:
        EcoMapProposalError: si el LLM trunca la respuesta o no
            devuelve un JSON parseable con claves de sección. En
            ese caso NO se persiste nada (fail-loud).
        RuntimeError: si el prompt autopopulate no está sembrado.
    """
    from app.config import settings

    prompt = await get_active_prompt(db, "ecos_map_autopopulate")
    if prompt is None:
        raise RuntimeError(
            "Prompt 'ecos_map_autopopulate' no encontrado en "
            "prompt_templates. Aplica las migraciones 011/013/014."
        )

    template_json = json.dumps(
        {
            section_number: [
                {"slot_id": s["slot_id"], "label": s["label"]}
                for s in slots
            ]
            for section_number, slots in ECOS_SECTION_TEMPLATE.items()
        },
        ensure_ascii=False,
    )

    source_block = ""
    if source_content and source_content.strip():
        max_chars = settings.ecos_map_max_source_chars
        excerpt = source_content[:max_chars]
        truncation = (
            "\n[... CONTENIDO TRUNCADO ...]"
            if len(source_content) > max_chars
            else ""
        )
        source_block = (
            f"\n\nCONTENIDO FUENTE DEL PROYECTO "
            f"(extractos de guías clínicas subidas):\n"
            f"{excerpt}{truncation}\n\n"
            "PRIORIZA los ecos para temas que REALMENTE están "
            "cubiertos en este contenido fuente. Si un tema del "
            "template NO aparece en las fuentes, genera el eco "
            "igual pero anótalo como 'candidato a revisión'."
        )

    user_payload = (
        f"PATOLOGÍA: {pathology_name}\n\n"
        f"TEMPLATE GENÉRICO:\n{template_json}"
        f"{source_block}\n\n"
        f"Devuelve exclusivamente un JSON válido con la forma "
        f'{{"1": ["..."], "2": ["..."], ..., "11": ["..."]}} '
        f"donde cada lista contiene los ecos (referencias "
        f"cruzadas, no desarrollo) para esa sección. Cada eco "
        f"debe mencionar el slot_id o su label del template."
    )

    model_id = model or DEFAULT_ECOS_MAP_MODEL

    result = await ai.generate(
        prompt=user_payload,
        model=model_id,
        temperature=0.1,
        system_prompt=prompt.content,
        # Margen amplio: Gemini 3.1 Pro consume parte del presupuesto
        # de salida en reasoning tokens; 8k podía truncar el JSON.
        max_tokens=16384,
    )

    # FAIL-LOUD: una respuesta truncada o no parseable NUNCA se
    # persiste como borrador vacío. Un mapa con sections={} parece
    # "generado" en la UI pero no contiene nada revisable.
    if result.finish_reason == "length":
        raise EcoMapProposalError(
            "El modelo truncó su respuesta (finish_reason='length') "
            "antes de completar el JSON del ecos map. No se guardó "
            "ningún borrador. Reintenta la generación."
        )

    draft_sections = _parse_draft_json(result.content)
    if not _has_section_keys(draft_sections):
        raise EcoMapProposalError(
            "El modelo no devolvió un JSON válido con claves de "
            "sección ('1'..'11'). No se guardó ningún borrador "
            "vacío. Respuesta (primeros 200 chars): "
            f"{(result.content or '')[:200]!r}"
        )

    ok, problems = validate_ecos_map(draft_sections)
    next_v = await _next_version(db, pathology_name)
    description = (
        f"Borrador auto-poblado v{next_v}"
        + (
            ""
            if ok
            else f" — ATENCIÓN: cobertura incompleta ({len(problems)} slot(s))"
        )
    )

    pathology_key = pathology_key_for(pathology_name)
    new_map = EcosMap(
        id=str(uuid4()),
        pathology_key=pathology_key,
        pathology_name=pathology_name,
        version=next_v,
        sections=draft_sections,
        status=(
            EcosMapStatus.DRAFT
        ),  # SIEMPRE draft; aprobación es humana
        origin=EcosMapOrigin.AUTOPOPULATED,
        is_active=False,
        model_used=model_id,
        description=description,
    )
    db.add(new_map)
    await db.commit()
    await db.refresh(new_map)
    return new_map


def _parse_draft_json(raw: str) -> dict:
    """
    Extrae el JSON del output del LLM. Acepta bloques ```json``` o
    texto crudo que arranca con {. Si falla, devuelve dict vacío.
    """
    if not raw:
        return {}
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        # Intento laxo: tomar desde el primer { hasta el último }.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                return {}
        return {}


async def _next_version(db: AsyncSession, pathology_name: str) -> int:
    """Calcula la siguiente versión para una patología."""
    from sqlalchemy import func

    key = pathology_key_for(pathology_name)
    result = await db.execute(
        select(func.max(EcosMap.version)).where(
            EcosMap.pathology_key == key
        )
    )
    current = result.scalar() or 0
    return int(current) + 1


async def approve_ecos_map(
    db: AsyncSession,
    map_id: str,
    approver_user_id: str,
) -> EcosMap:
    """
    Aprueba un borrador. Desactiva cualquier mapa activo previo de
    la misma patología y marca este como approved+active.
    """
    from datetime import datetime

    result = await db.execute(
        select(EcosMap).where(EcosMap.id == map_id)
    )
    eco_map = result.scalar_one_or_none()
    if eco_map is None:
        raise EcoMapNotFoundError(f"ecos_map '{map_id}' no existe")
    if eco_map.status == EcosMapStatus.APPROVED and eco_map.is_active:
        return eco_map  # ya aprobado, idempotente

    # Desactivar versiones activas previas de la misma patología
    prev_active = await db.execute(
        select(EcosMap).where(
            EcosMap.pathology_key == eco_map.pathology_key,
            EcosMap.is_active,
        )
    )
    for prev in prev_active.scalars().all():
        prev.is_active = False

    eco_map.status = EcosMapStatus.APPROVED
    eco_map.is_active = True
    eco_map.approved_by = approver_user_id
    eco_map.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(eco_map)
    return eco_map


async def update_ecos_map_draft(
    db: AsyncSession,
    map_id: str,
    sections: dict,
    description: str | None = None,
) -> tuple[EcosMap, list[str]]:
    """
    Edita un borrador existente (draft-only). Devuelve el mapa
    actualizado y la lista de problemas de cobertura (warnings).
    El criterio del doctor manda: puede guardar con warnings.
    """
    result = await db.execute(
        select(EcosMap).where(EcosMap.id == map_id)
    )
    eco_map = result.scalar_one_or_none()
    if eco_map is None:
        raise EcoMapNotFoundError(f"ecos_map '{map_id}' no existe")
    if eco_map.status != EcosMapStatus.DRAFT:
        raise EcoMapNotEditableError(
            f"Solo se pueden editar borradores "
            f"(estado actual: {eco_map.status})"
        )

    _coerce_all_sections(sections)
    eco_map.sections = sections
    if description is not None:
        eco_map.description = description

    _, problems = validate_ecos_map(sections)

    await db.commit()
    await db.refresh(eco_map)
    return eco_map, problems


def _coerce_all_sections(sections: dict) -> None:
    """Normaliza in-place los valores de sections a list[str]."""
    for key in list(sections.keys()):
        sections[key] = _coerce_ecos_list(sections[key])


class EcoMapNotEditableError(Exception):
    """El ecos_map no está en estado draft; no es editable."""


class EcoMapNotFoundError(Exception):
    pass


def get_ecos_for_section(
    eco_map: EcosMap | None, section_number: int
) -> list[str]:
    """
    Devuelve la lista de ecos para una sección desde el mapa
    aprobado, o lista vacía si no hay mapa. Si el mapa no tiene
    entrada para la sección, devuelve [] (la sección podrá cubrir
    sin ecos; el orchestrator loguea warning).
    """
    if eco_map is None:
        return []
    sections = eco_map.sections or {}
    raw = sections.get(str(section_number), [])
    return _coerce_ecos_list(raw)
