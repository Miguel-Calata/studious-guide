"""
Storage abstraction for file management.

Supports both local filesystem and S3-compatible storage (AWS S3, MinIO, R2).
The rest of the codebase interacts only with the abstract interface.

=== URI format ===
- Local:  local://{project_id}/{document_id}.pdf
- S3:     s3://{bucket}/pdfs/{project_id}/{document_id}.pdf
          s3://{bucket}/compendiums/{slug}.md

=== Environment variables ===
For local storage (default for PDFs):
  STORAGE_BACKEND=local
  PDF_STORAGE_PATH=/app/data/pdfs

For S3 / MinIO:
  STORAGE_BACKEND=s3
  S3_BUCKET=compendiums
  S3_ENDPOINT=https://s3.amazonaws.com   # or http://minio:9000
  S3_ACCESS_KEY=...
  S3_SECRET_KEY=...
  S3_REGION=us-east-1
  S3_USE_SSL=true

=== MIGRATION GUIDE: Local to S3 ===
1. Set STORAGE_BACKEND=s3 and configure S3_* variables.
2. Existing local files can be migrated with a script that:
   a. Reads all source_documents with file_path starting with "local://"
   b. Uploads each file to S3 using the same key pattern
   c. Updates file_path to "s3://{bucket}/pdfs/..."
3. The DB schema does NOT need to change.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlparse

import aiofiles
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(
        self, file: UploadFile, project_id: str, document_id: str
    ) -> str:
        """Save file and return a URI (local://... or s3://...)."""
        ...

    @abstractmethod
    async def save_bytes(self, key: str, content: bytes) -> str:
        """Save raw bytes under the given key and return a URI."""
        ...

    @abstractmethod
    async def read_bytes(self, file_uri: str) -> bytes:
        """Read file contents by URI."""
        ...

    @abstractmethod
    async def delete(self, file_uri: str) -> None:
        """Delete file by URI."""
        ...

    @abstractmethod
    async def exists(self, file_uri: str) -> bool:
        """Check if file exists."""
        ...

    @abstractmethod
    def get_local_path(self, file_uri: str) -> Path:
        """Resolve URI to a local filesystem path for reading, if supported."""
        ...

    async def stream(self, file_uri: str) -> AsyncIterator[bytes]:
        """Stream file contents in chunks (64KB).

        Default raises NotImplementedError. Override in subclass.
        """
        raise NotImplementedError
        if False:  # pragma: no cover
            yield b""


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)

    async def save(
        self, file: UploadFile, project_id: str, document_id: str
    ) -> str:
        project_dir = self.base_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        file_path = project_dir / f"{document_id}.pdf"
        content = await file.read()
        file_path.write_bytes(content)

        return f"local://{project_id}/{document_id}.pdf"

    async def save_bytes(self, key: str, content: bytes) -> str:
        file_path = self.base_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return f"local://{key}"

    async def read_bytes(self, file_uri: str) -> bytes:
        path = self.get_local_path(file_uri)
        return path.read_bytes()

    async def delete(self, file_uri: str) -> None:
        path = self.get_local_path(file_uri)
        if path.exists():
            path.unlink()

    async def exists(self, file_uri: str) -> bool:
        return self.get_local_path(file_uri).exists()

    def get_local_path(self, file_uri: str) -> Path:
        if not file_uri.startswith("local://"):
            raise ValueError(f"Invalid local URI: {file_uri}")
        relative = file_uri.removeprefix("local://")
        return self.base_path / relative

    async def stream(self, file_uri: str) -> AsyncIterator[bytes]:
        path = self.get_local_path(file_uri)
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(64 * 1024):
                yield chunk


class S3StorageBackend(StorageBackend):
    """
    S3-compatible backend using aiobotocore.

    Works with AWS S3, MinIO, Cloudflare R2, DigitalOcean Spaces, etc.
    """

    def __init__(
        self,
        bucket: str,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_ssl: bool = True,
    ):
        self.bucket = bucket
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.use_ssl = use_ssl
        self._bucket_ensured = False
        self._ensure_lock = asyncio.Lock()

    def _client(self):
        from aiobotocore.session import get_session
        from aiobotocore.config import AioConfig

        session = get_session()
        config = AioConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
        return session.create_client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            use_ssl=self.use_ssl,
            config=config,
        )

    async def ensure_bucket(self) -> None:
        """Create the bucket if it does not exist (idempotent)."""
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                error_code = exc.response["Error"]["Code"]
                if error_code in ("404", "NoSuchBucket"):
                    await client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={
                            "LocationConstraint": self.region
                        },
                    )
                else:
                    raise

    async def _ensure_bucket_once(self) -> None:
        if self._bucket_ensured:
            return
        async with self._ensure_lock:
            if not self._bucket_ensured:
                await self.ensure_bucket()
                self._bucket_ensured = True

    @staticmethod
    def _parse_uri(file_uri: str) -> tuple[str, str]:
        parsed = urlparse(file_uri)
        if parsed.scheme != "s3":
            raise ValueError(f"Invalid S3 URI: {file_uri}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key

    async def save(
        self, file: UploadFile, project_id: str, document_id: str
    ) -> str:
        content = await file.read()
        key = f"pdfs/{project_id}/{document_id}.pdf"
        return await self.save_bytes(key, content)

    async def save_bytes(self, key: str, content: bytes) -> str:
        await self._ensure_bucket_once()
        async with self._client() as client:
            await client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return f"s3://{self.bucket}/{key}"

    async def read_bytes(self, file_uri: str) -> bytes:
        await self._ensure_bucket_once()
        bucket, key = self._parse_uri(file_uri)
        async with self._client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def stream(self, file_uri: str) -> AsyncIterator[bytes]:
        await self._ensure_bucket_once()
        bucket, key = self._parse_uri(file_uri)
        async with self._client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as body:
                async for chunk in body.iter_chunks(chunk_size=64 * 1024):
                    yield chunk

    async def delete(self, file_uri: str) -> None:
        await self._ensure_bucket_once()
        bucket, key = self._parse_uri(file_uri)
        async with self._client() as client:
            await client.delete_object(Bucket=bucket, Key=key)

    async def exists(self, file_uri: str) -> bool:
        await self._ensure_bucket_once()
        bucket, key = self._parse_uri(file_uri)
        async with self._client() as client:
            try:
                await client.head_object(Bucket=bucket, Key=key)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "404":
                    return False
                raise

    def get_local_path(self, file_uri: str) -> Path:
        raise NotImplementedError("S3 storage has no local path")


_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        if settings.storage_backend == "s3":
            _backend = S3StorageBackend(
                bucket=settings.s3_bucket,
                endpoint=settings.s3_endpoint,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                region=settings.s3_region,
                use_ssl=settings.s3_use_ssl,
            )
        else:
            _backend = LocalStorageBackend(settings.pdf_storage_path)
    return _backend
