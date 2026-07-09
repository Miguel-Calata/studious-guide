"""
ARQ worker configuration.

This module exposes the WorkerSettings class used by the `arq` CLI.
Jobs are registered in the `functions` list.
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
from app.workers.extraction_worker import audit_extraction, extract_document
from app.workers.generation_worker import generate_section


async def health_check_task(ctx) -> str:
    """Simple health-check task used to verify workers are running."""
    return "worker-ok"


class WorkerSettings:
    """ARQ worker settings."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [health_check_task, extract_document, audit_extraction, generate_section]
    max_jobs = 10
    job_timeout = 1800
    max_tries = 2
