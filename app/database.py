"""Bio-Chain v2 — Database engine & async session factory.

Mendukung PostgreSQL (produksi/docker) dan SQLite lokal (development/demo standalone)
secara otomatis tanpa error. Jika PostgreSQL tidak aktif, otomatis fallback ke SQLite.
"""

import socket
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

SQLITE_PATH = Path(__file__).parent.parent / "biochain.db"
SQLITE_URL = f"sqlite+aiosqlite:///{SQLITE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _sqlite_engine(url: str):
    """SQLite untuk demo: WAL + busy_timeout. SQLite hanya punya satu penulis; banyak koneksi justru
    saling busy-wait (backoff tidur s/d 100 ms), jadi request diantrekan FIFO di pool berukuran kecil."""
    eng = create_async_engine(url, echo=False, connect_args={"check_same_thread": False, "timeout": 10},
                              pool_size=settings.SQLITE_POOL_SIZE, max_overflow=0,
                              pool_timeout=settings.DB_POOL_TIMEOUT_S)

    @event.listens_for(eng.sync_engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return eng


def _postgres_engine(url: str):
    connect_args = {"server_settings": {"statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                                        "lock_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                                        "idle_in_transaction_session_timeout": "30000"}}
    if settings.PGBOUNCER:
        connect_args["statement_cache_size"] = 0          # wajib untuk PgBouncer transaction pooling
        connect_args["prepared_statement_cache_size"] = 0 # cache prepared statement SQLAlchemy juga (Supavisor :6543)
    if settings.DB_NULLPOOL:
        # Koneksi asyncpg terikat ke event loop pembuatnya; harness tes membuat banyak loop (TestClient,
        # asyncio.run). Produksi (1 loop per proses Uvicorn) tetap memakai pool.
        from sqlalchemy.pool import NullPool
        return create_async_engine(url, echo=False, poolclass=NullPool, connect_args=connect_args)
    return create_async_engine(url, echo=False, pool_size=settings.DB_POOL_SIZE,
                               max_overflow=settings.DB_MAX_OVERFLOW, pool_timeout=settings.DB_POOL_TIMEOUT_S,
                               pool_pre_ping=True, pool_recycle=1800, connect_args=connect_args)


def _is_postgres_available(url: str | None = None) -> bool:
    """Cek cepat (0.2s) apakah host:port dari DATABASE_URL terbuka (bukan selalu localhost:5432 —
    port itu bisa milik proyek lain di mesin yang sama)."""
    from sqlalchemy.engine import make_url
    try:
        u = make_url(url or settings.DATABASE_URL)
        host, port = u.host or "localhost", u.port or 5432
    except Exception:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


class DatabaseManager:
    """Singleton manager for database engine and session maker."""

    def __init__(self):
        self._engine = None
        self._sessionmaker = None
        self.active_driver = "sqlite"
        self.active_db_url = SQLITE_URL
        self._init_engine()

    def _init_engine(self):
        explicit_sqlite = "sqlite" in settings.DATABASE_URL.lower()
        pg_up = explicit_sqlite or _is_postgres_available(settings.DATABASE_URL)
        if not pg_up and not settings.ALLOW_SQLITE_FALLBACK:
            # Produksi: tunggu PostgreSQL (mis. container baru naik) — JANGAN diam-diam pindah ke SQLite
            import time
            for _ in range(30):
                time.sleep(1)
                if _is_postgres_available(settings.DATABASE_URL):
                    pg_up = True
                    break
            if not pg_up:
                print("❌ PostgreSQL tidak terjangkau dan ALLOW_SQLITE_FALLBACK=False — koneksi akan gagal jelas (503).")
        use_sqlite = explicit_sqlite or (not pg_up and settings.ALLOW_SQLITE_FALLBACK)
        # SQLite eksplisit di DATABASE_URL → pakai path itu (dulu selalu biochain.db, sehingga tes/E2E yang
        # mengira memakai DB terpisah diam-diam menulis ke DB pengembangan). Fallback darurat tetap biochain.db.
        self.active_db_url = (settings.DATABASE_URL if explicit_sqlite else SQLITE_URL) if use_sqlite else settings.DATABASE_URL
        self.active_driver = "sqlite" if use_sqlite else "postgresql"
        self._engine = _sqlite_engine(self.active_db_url) if use_sqlite else _postgres_engine(self.active_db_url)
        self._sessionmaker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @property
    def engine(self):
        return self._engine

    @property
    def async_session(self):
        return self._sessionmaker

    async def switch_to_sqlite(self):
        """Fallback ke SQLite lokal jika diperlukan saat runtime."""
        if self._engine:
            try:
                await self._engine.dispose()
            except Exception:
                pass
        self.active_driver = "sqlite"
        self.active_db_url = SQLITE_URL
        self._engine = _sqlite_engine(self.active_db_url)
        self._sessionmaker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        return self._engine


db_manager = DatabaseManager()


# Module-level backward-compatible accessors
def __getattr__(name: str):
    if name == "engine":
        return db_manager.engine
    if name == "async_session":
        return db_manager.async_session
    if name == "active_driver":
        return db_manager.active_driver
    if name == "active_db_url":
        return db_manager.active_db_url
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


async def switch_to_sqlite():
    return await db_manager.switch_to_sqlite()


async def get_db():
    """Dependency: yield async database session with auto-commit/rollback.

    Convention (H3 documented):
    - Routers SHOULD NOT call db.commit() or db.flush() directly.
    - Simply mutate ORM objects; this dependency auto-commits on success.
    - On exception, the session is rolled back automatically.
    """
    async with db_manager.async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
