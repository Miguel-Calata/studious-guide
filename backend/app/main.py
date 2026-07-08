from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.modules.auth.router import router as auth_router
from app.modules.compendiums.router import router as compendiums_router
from app.modules.documents.router import router as documents_router
from app.modules.extractions.router import router as extractions_router
from app.modules.projects.router import router as projects_router
from app.modules.prompts.router import router as prompts_router
from app.modules.publishing.router import public_router as publishing_public_router
from app.modules.publishing.router import router as publishing_router
from app.modules.notion.router import router as notion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await app.state.redis.ping()
    except Exception:
        app.state.redis = None

    app.state.arq_pool = await create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )

    yield

    if app.state.arq_pool:
        await app.state.arq_pool.close()
    if app.state.redis:
        await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SAM Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = [
        origin.strip()
        for origin in settings.backend_cors_origins.split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        db_ok = False
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            db_ok = True
        except Exception:
            pass

        redis_ok = False
        if app.state.redis:
            try:
                await app.state.redis.ping()
                redis_ok = True
            except Exception:
                pass

        status_healthy = db_ok and redis_ok
        return {
            "status": "healthy" if status_healthy else "degraded",
            "db": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(extractions_router, prefix="/api/v1")
    app.include_router(prompts_router, prefix="/api/v1")
    app.include_router(compendiums_router, prefix="/api/v1")
    app.include_router(publishing_router, prefix="/api/v1")
    app.include_router(publishing_public_router)
    app.include_router(notion_router, prefix="/api/v1")

    return app


app = create_app()
