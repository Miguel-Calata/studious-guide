from arq.connections import ArqRedis
from fastapi import Request

from app.services.storage import StorageBackend, get_storage_backend


async def get_arq_pool(request: Request) -> ArqRedis | None:
    return getattr(request.app.state, "arq_pool", None)


def get_storage() -> StorageBackend:
    return get_storage_backend()
