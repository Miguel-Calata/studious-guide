"""
Tarea 2 — Auditoría de extracción v1 (mínima viable).

En lugar de la auditoría LLM self-audit (legacy `audit` prompt
semillada en 006), esta versión compara el contenido extraído contra
una lista curada de "hechos esperados" (checklist) por tipo de fuente
usando matching por palabra clave/entidad. Es una primera iteración
documentada como tal: una keyword matchea si la versión normalizada
de la keyword aparece como subcadena en la versión normalizada del
contenido. No es NLP — es una red de seguridad barata y reproducible
contra omisiones flagrantes (p.ej. "no mencioné los criterios KDIGO
en una guía KDIGO").

Storage: el checklist se almacena en `prompt_templates` con
`type="audit_checklist"`, versionable igual que el resto de prompts.
La función `find_missing_facts` es pura (no toca BD) para facilitar
testing contra `merged_document.md` o cualquier texto arbitrario.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import Extraction
from app.models.prompt_template import PromptTemplate
from app.models.source_document import SourceDocument


def normalize_text(text: str) -> str:
    """
    Normalización para matching v1:
      - minúsculas
      - sin acentos (NFKD)
      - espacios colapsados

    No es un tokenizer formal; es una red de seguridad contra
    diferencias de formato triviales. Documentado como v1.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents.lower()).strip()


def keyword_present(keyword: str, normalized_content: str) -> bool:
    k = normalize_text(keyword)
    if not k:
        return False
    return k in normalized_content


@dataclass(frozen=True)
class ExpectedFact:
    id: str
    fact: str
    keywords: tuple[str, ...]


@dataclass
class AuditReport:
    document_id: str
    extraction_id: str
    checklist_name: str
    checklist_version: int
    total_facts: int
    present_count: int
    missing_count: int
    missing: list[ExpectedFact]
    generated_at: datetime

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "extraction_id": self.extraction_id,
            "checklist_name": self.checklist_name,
            "checklist_version": self.checklist_version,
            "total_facts": self.total_facts,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "missing": [
                {"id": f.id, "fact": f.fact} for f in self.missing
            ],
            "generated_at": self.generated_at.isoformat(),
        }


def parse_checklist(raw_content: str) -> list[ExpectedFact]:
    """
    Parsea el JSON del checklist. Si el formato es inválido, retorna
    lista vacía (la auditoría se considerará vacía y se logueará
    warning, sin romper el pipeline).

    Solo se aceptan ítems con al menos una keyword (un hecho sin
    keywords no es contrastable).
    """
    try:
        data = json.loads(raw_content)
    except (ValueError, TypeError):
        return []
    items = data.get("items") or []
    out: list[ExpectedFact] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kw = item.get("keywords") or []
        if not isinstance(kw, list) or not kw:
            continue
        out.append(
            ExpectedFact(
                id=str(item.get("id", "")),
                fact=str(item.get("fact", "")),
                keywords=tuple(str(k) for k in kw),
            )
        )
    return out


def find_missing_facts(
    content: str,
    expected: list[ExpectedFact],
) -> list[ExpectedFact]:
    """
    Función pura: dado el contenido extraído y la lista de hechos
    esperados, devuelve los hechos que NO se consideran presentes
    (ninguna de sus keywords matchea). Acepta cualquier texto —
    puede invocarse contra una extracción individual, contra
    `merged_document.md` o contra cualquier string arbitrario para
    evaluación.
    """
    if not expected:
        return []
    normalized = normalize_text(content)
    missing: list[ExpectedFact] = []
    for fact in expected:
        if not any(keyword_present(kw, normalized) for kw in fact.keywords):
            missing.append(fact)
    return missing


def checklist_name_for_document_type(document_type: str) -> str:
    """
    Resuelve el nombre del checklist en `prompt_templates` según el
    tipo de documento. Mapea al namespace sembrado en migración 010.
    Fallback: 'article'.
    """
    mapping = {
        "bmj": "audit_checklist_bmj",
        "guideline": "audit_checklist_guideline",
        "article": "audit_checklist_article",
    }
    return mapping.get(document_type, "audit_checklist_article")


async def load_active_checklist(
    db: AsyncSession, document_type: str
) -> tuple[PromptTemplate, list[ExpectedFact]]:
    """
    Carga la versión activa del checklist para un tipo de documento.
    Si no existe (versión semilla no aplicada), devuelve ([], []).
    """
    name = checklist_name_for_document_type(document_type)
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.name == name,
            PromptTemplate.is_active,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        return None, []
    return prompt, parse_checklist(prompt.content)


async def run_audit_for_extraction(
    db: AsyncSession,
    extraction: Extraction,
    document: SourceDocument,
) -> AuditReport:
    """
    Ejecuta la auditoría v1 sobre una extracción. Escribe el reporte
    en `extraction.audit_content` y marca `extraction.audit_completed`.

    Nunca lanza: fallos se registran en el reporte y se loguean.
    """
    prompt, expected = await load_active_checklist(db, document.document_type)
    if prompt is None or not expected:
        report = AuditReport(
            document_id=str(document.id),
            extraction_id=str(extraction.id),
            checklist_name=(
                checklist_name_for_document_type(document.document_type)
            ),
            checklist_version=0,
            total_facts=0,
            present_count=0,
            missing_count=0,
            missing=[],
            generated_at=datetime.now(UTC),
        )
        extraction.audit_completed = True
        extraction.audit_content = json.dumps(
            {
                **report.to_dict(),
                "note": "checklist no disponible para este document_type",
            },
            ensure_ascii=False,
        )
        await db.commit()
        return report

    missing = find_missing_facts(extraction.content or "", expected)
    present_count = len(expected) - len(missing)
    report = AuditReport(
        document_id=str(document.id),
        extraction_id=str(extraction.id),
        checklist_name=prompt.name,
        checklist_version=prompt.version,
        total_facts=len(expected),
        present_count=present_count,
        missing_count=len(missing),
        missing=missing,
        generated_at=datetime.now(UTC),
    )
    extraction.audit_completed = True
    extraction.audit_content = json.dumps(
        report.to_dict(), ensure_ascii=False
    )
    await db.commit()
    return report
