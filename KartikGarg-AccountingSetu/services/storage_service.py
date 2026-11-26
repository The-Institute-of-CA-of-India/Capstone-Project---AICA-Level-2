"""Private document storage with tenant-scoped paths.

Paths: {firm_id}/{client_id}/{yyyy}/{mm}/{name}  — the Supabase storage policies in
database/migrations/003_storage.sql check these path segments against the user's membership.
Files are never served by URL; they are streamed only after an authorization check
(see document_service.read_document_bytes).
"""
from __future__ import annotations

from pathlib import Path

from config import settings


class StorageError(Exception):
    pass


def _safe(path: str) -> str:
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    if not parts:
        raise StorageError("empty path")
    return "/".join(parts)


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _full(self, path: str) -> Path:
        full = (self.root / _safe(path)).resolve()
        if self.root.resolve() not in full.parents:
            raise StorageError("path escapes storage root")
        return full

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        full = self._full(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        if full.exists():
            raise StorageError("object already exists (originals are immutable)")
        full.write_bytes(data)
        return _safe(path)

    def put_overwrite(self, path: str, data: bytes) -> str:
        full = self._full(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return _safe(path)

    def get(self, path: str) -> bytes:
        full = self._full(path)
        if not full.exists():
            raise StorageError("object not found")
        return full.read_bytes()

    def exists(self, path: str) -> bool:
        return self._full(path).exists()


class SupabaseStorage:
    """Server-side storage client. Uses the service key ONLY on the server; the browser never
    receives a storage URL or key. Authorization is checked in Python before every call."""

    def __init__(self):
        from supabase import create_client

        key = settings.supabase_service_role_key or settings.supabase_anon_key
        self.client = create_client(settings.supabase_url, key)
        self.bucket = settings.supabase_bucket

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        self.client.storage.from_(self.bucket).upload(_safe(path), data, {"content-type": content_type or "application/octet-stream",
                                                                          "upsert": "false"})
        return _safe(path)

    def put_overwrite(self, path: str, data: bytes) -> str:
        self.client.storage.from_(self.bucket).upload(_safe(path), data, {"upsert": "true"})
        return _safe(path)

    def get(self, path: str) -> bytes:
        return self.client.storage.from_(self.bucket).download(_safe(path))

    def exists(self, path: str) -> bool:
        try:
            self.get(path)
            return True
        except Exception:
            return False


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = SupabaseStorage() if settings.backend == "supabase" else LocalStorage(settings.storage_dir)
    return _storage


def set_storage(storage) -> None:
    global _storage
    _storage = storage
