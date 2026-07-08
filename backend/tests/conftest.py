import asyncio
import os
import subprocess
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import get_db
from app.dependencies import get_arq_pool, get_storage
from app.main import app
from app.services.storage import LocalStorageBackend

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sam:sam@postgres:5432/sam_platform_test",
)
TEST_DATABASE_NAME = TEST_DATABASE_URL.rsplit("/", 1)[-1]
TEST_DATABASE_ADMIN_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"


def _async_url_to_dsn(url: str) -> str:
    """Convert sqlalchemy+asyncpg URL to asyncpg DSN."""
    return url.replace("postgresql+asyncpg", "postgresql")


async def _create_test_database() -> None:
    dsn = _async_url_to_dsn(TEST_DATABASE_ADMIN_URL)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)"
        )
        await conn.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
    finally:
        await conn.close()


def _run_migrations() -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL
    backend_dir = Path(__file__).parent.parent
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create the test database and run migrations once per test run."""
    asyncio.run(_create_test_database())
    _run_migrations()


@pytest_asyncio.fixture
async def db_session():
    """Yield an async session bound to a nested transaction that rolls back."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with engine.connect() as connection:
        transaction = await connection.begin_nested()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
        )
        yield session
        await session.close()
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def sample_pdf() -> bytes:
    return b"%PDF-1.4 test content"


@pytest.fixture
def test_storage(tmp_path):
    return LocalStorageBackend(str(tmp_path))


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, test_storage: LocalStorageBackend):
    """Yield an HTTP client with the database and storage dependencies overridden."""

    async def override_get_db():
        yield db_session

    async def override_get_arq_pool():
        return None

    def override_get_storage():
        return test_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_storage] = override_get_storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
