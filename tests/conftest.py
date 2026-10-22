"""Helper bersama: header Authorization untuk akun demo (endpoint lab kini butuh login Pabrik/Admin)."""

import os

import pytest

# Tes tidak boleh bergantung pada Redis yang kebetulan hidup di mesin pengembang: longgarkan rate limit
# (harus diset sebelum app.config diimpor oleh modul tes).
os.environ.setdefault("RATE_LIMIT_REQUESTS", "1000000")
os.environ.setdefault("LOGIN_RATE_LIMIT", "1000000")
# Jangan pernah menulis ke Redis yang kebetulan hidup di mesin (bisa milik proyek lain): port 1 selalu
# tertutup → rate limiter fail-open, backend job lokal.
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["JOB_BACKEND"] = "local"
os.environ.setdefault("DB_NULLPOOL", "true")      # asyncpg: koneksi per event loop (lihat app/database.py)

DEMO = {
    "petani": ("petani_sugeng", "sekam123"),
    "pengepul": ("pengepul_sleman", "kud2026"),
    "driver": ("sopir_budi", "truk2026"),
    "pabrik": ("pabrik_indmira", "pabrik2026"),
    "auditor": ("auditor_esg", "audit2026"),
    "admin": ("admin", "admin2026"),
}
_cache: dict[str, dict] = {}


def demo_headers(client, role: str) -> dict:
    """Login akun demo sekali per sesi tes (PBKDF2 mahal) dan kembalikan header Bearer."""
    if role not in _cache:
        ident, pw = DEMO[role]
        r = client.post("/api/v1/auth/login", json={"identifier": ident, "password": pw})
        assert r.status_code == 200, r.text
        _cache[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _cache[role]


@pytest.fixture
def pabrik(client):
    return demo_headers(client, "pabrik")


def isolated_engine(tmp_path, name: str):
    """Engine DB terisolasi per tes. Default SQLite file sementara; bila BIOCHAIN_TEST_PG_OWNER_URL diset,
    skema PostgreSQL baru per tes (search_path) agar alur bisnis & race condition teruji di PostgreSQL."""
    import uuid

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    pg = os.getenv("BIOCHAIN_TEST_PG_OWNER_URL")
    if not pg:
        return create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / name).as_posix()}", poolclass=NullPool), None
    schema = f"t_{uuid.uuid4().hex[:12]}"
    import asyncio
    import asyncpg

    async def mk():
        c = await asyncpg.connect(pg.replace("postgresql+asyncpg://", "postgresql://"))
        await c.execute(f'CREATE SCHEMA "{schema}"')
        await c.close()
    asyncio.run(mk())
    eng = create_async_engine(pg, poolclass=NullPool,
                              connect_args={"server_settings": {"search_path": schema}})

    def drop():
        async def rm():
            c = await asyncpg.connect(pg.replace("postgresql+asyncpg://", "postgresql://"))
            await c.execute(f'DROP SCHEMA "{schema}" CASCADE')
            await c.close()
        asyncio.run(rm())
    return eng, drop
