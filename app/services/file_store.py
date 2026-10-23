"""Penyimpanan berkas bukti (foto timbangan, serah-terima, laporan lab).

Backend:
- LocalStore    : folder di disk (dev / server tunggal). Default.
- SupabaseStore : bucket privat Supabase Storage (serverless: disk Vercel sementara). Aktif bila
                  SUPABASE_URL + SUPABASE_SECRET_KEY diisi. Kunci rahasia hanya di server; browser
                  tetap mengambil berkas lewat /uploads/<nama> milik aplikasi (CSP 'self', tanpa URL bertanda).
Nama berkas dibuat server (sha256 isi), jadi URL /uploads/<nama> lama tetap berlaku di kedua backend.
"""

import re
from pathlib import Path

import anyio.to_thread
import httpx

from ..config import settings

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".webp": "image/webp", ".pdf": "application/pdf"}


def is_safe_name(name: str) -> bool:
    """Tolak path traversal (`..`, `/`, `\\`) & nama tersembunyi sebelum menyentuh backend apa pun."""
    return bool(SAFE_NAME.match(name)) and ".." not in name


def content_type_for(name: str) -> str:
    return CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


class LocalStore:
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def exists(self, name: str) -> bool:
        return (self.root / name).is_file()

    async def save(self, name: str, content: bytes, content_type: str) -> None:
        await anyio.to_thread.run_sync((self.root / name).write_bytes, content)

    async def load(self, name: str) -> bytes | None:
        path = self.root / name
        if not path.is_file():
            return None
        return await anyio.to_thread.run_sync(path.read_bytes)


class SupabaseStore:
    name = "supabase"

    def __init__(self, url: str, secret_key: str, bucket: str, transport: httpx.AsyncBaseTransport | None = None):
        self._base = f"{url.rstrip('/')}/storage/v1/object/{bucket}"
        self._headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
        self._transport = transport                 # tes: httpx.MockTransport

    def _client(self) -> httpx.AsyncClient:
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, headers=self._headers)
        from ..ai.providers import ssl_context      # trust store OS (proxy/antivirus korporat saat dev)
        return httpx.AsyncClient(verify=ssl_context(), timeout=20.0, headers=self._headers)

    async def exists(self, name: str) -> bool:
        async with self._client() as c:
            r = await c.head(f"{self._base}/{name}")
        return r.status_code == 200

    async def save(self, name: str, content: bytes, content_type: str) -> None:
        async with self._client() as c:
            r = await c.post(f"{self._base}/{name}", content=content,
                             headers={"Content-Type": content_type, "x-upsert": "true"})
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase Storage menolak unggahan ({r.status_code}).")

    async def load(self, name: str) -> bytes | None:
        async with self._client() as c:
            r = await c.get(f"{self._base}/{name}")
        if r.status_code in (400, 404):              # Storage membalas 400 "Object not found"
            return None
        r.raise_for_status()
        return r.content


_store: LocalStore | SupabaseStore | None = None


def get_store() -> LocalStore | SupabaseStore:
    global _store
    if _store is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
            _store = SupabaseStore(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY, settings.SUPABASE_BUCKET)
        else:
            _store = LocalStore(settings.uploads_path)
    return _store
