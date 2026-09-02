import asyncio
import hashlib
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncContextManager, Protocol

import boto3
from botocore.config import Config

from app.core.config import get_settings


class MediaTooLargeError(ValueError):
    pass


class MediaStorage(Protocol):
    backend_name: str

    async def save_stream(
        self,
        storage_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int,
    ) -> tuple[int, str]: ...

    def open_local(self, storage_key: str) -> AsyncContextManager[Path]: ...

    async def delete(self, storage_key: str) -> None: ...


async def _stream_to_path(
    path: Path,
    stream: AsyncIterator[bytes],
    *,
    max_bytes: int,
) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open("wb") as handle:
            async for chunk in stream:
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise MediaTooLargeError(
                        f"Audio exceeds the {max_bytes} byte upload limit"
                    )
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise ValueError("Audio upload is empty")
    return size, digest.hexdigest()


class FilesystemMediaStorage:
    backend_name = "filesystem"

    def __init__(self, root: str | Path | None = None) -> None:
        settings = get_settings()
        self.root = Path(root or settings.media_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Invalid media storage key")
        return candidate

    async def save_stream(
        self,
        storage_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int,
    ) -> tuple[int, str]:
        path = self.path_for(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return await _stream_to_path(path, stream, max_bytes=max_bytes)

    @asynccontextmanager
    async def open_local(self, storage_key: str):
        path = self.path_for(storage_key)
        if not path.is_file():
            raise FileNotFoundError("Media object is missing from filesystem storage")
        yield path

    async def delete(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)


class RailwayS3MediaStorage:
    backend_name = "railway_s3"

    def __init__(self) -> None:
        settings = get_settings()
        if not all(
            [
                settings.bucket,
                settings.access_key_id,
                settings.secret_access_key,
                settings.region,
                settings.endpoint,
            ]
        ):
            raise RuntimeError("Railway Bucket credentials are incomplete")
        self.bucket = settings.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key.get_secret_value(),
            region_name=settings.region,
            config=Config(s3={"addressing_style": "virtual"}),
        )

    async def save_stream(
        self,
        storage_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int,
    ) -> tuple[int, str]:
        with tempfile.NamedTemporaryFile(prefix="dd21-upload-", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            size, checksum = await _stream_to_path(
                temp_path,
                stream,
                max_bytes=max_bytes,
            )
            await asyncio.to_thread(
                self.client.upload_file,
                str(temp_path),
                self.bucket,
                storage_key,
            )
            return size, checksum
        finally:
            temp_path.unlink(missing_ok=True)

    @asynccontextmanager
    async def open_local(self, storage_key: str):
        with tempfile.NamedTemporaryFile(prefix="dd21-media-", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            await asyncio.to_thread(
                self.client.download_file,
                self.bucket,
                storage_key,
                str(temp_path),
            )
            yield temp_path
        finally:
            temp_path.unlink(missing_ok=True)

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object,
            Bucket=self.bucket,
            Key=storage_key,
        )


def get_media_storage() -> MediaStorage:
    settings = get_settings()
    if settings.media_storage_backend == "railway_s3":
        return RailwayS3MediaStorage()
    if settings.media_storage_backend == "filesystem":
        return FilesystemMediaStorage()
    raise RuntimeError(
        f"Unsupported media storage backend: {settings.media_storage_backend}"
    )
