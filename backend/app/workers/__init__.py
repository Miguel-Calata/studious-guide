"""
ARQ worker configuration.

Este módulo expone la WorkerSettings usada por la CLI de `arq`. Los
jobs se registran en la lista `functions`.

Tarea 1: el pipeline de generación completo se ejecuta ahora
secuencialmente (1 → 11) a través del PipelineOrchestrator para
mantener continuidad real de contexto entre secciones. Los jobs
nuevos son:
  - `generate_compendium`: genera las 11 secciones en orden
  - `regenerate_section_job`: regenera 1 sección (cascada R-9 si
    es la 4 o la 5)
"""

from arq.connections import RedisSettings

from app.config import settings
from app.models import (  # noqa: F401  (ensure all mappers configure)
    Base,
    CompendiumSection,
    Extraction,
    NotionConfig,
    Project,
    PromptTemplate,
    SourceDocument,
    User,
)
from app.workers.compendium_jobs import (
    generate_compendium,
    regenerate_section_job,
)
from app.workers.extraction_worker import audit_extraction, extract_document
from app.workers.generation_worker import generate_section

__all__ = [
    "WorkerSettings",
    "health_check_task",
    "extract_document",
    "audit_extraction",
    "generate_section",
    "generate_compendium",
    "regenerate_section_job",
]


async def health_check_task(ctx) -> str:
    """Simple health-check task used to verify workers are running."""
    return "worker-ok"


class WorkerSettings:
    """ARQ worker settings."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        health_check_task,
        extract_document,
        audit_extraction,
        generate_section,
        generate_compendium,
        regenerate_section_job,
    ]
    max_jobs = 10
    job_timeout = 1800
    max_tries = 2
