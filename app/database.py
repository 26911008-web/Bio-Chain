"""Bio-Chain v2 — Database engine & async session factory.

Mendukung PostgreSQL (produksi/docker) dan SQLite lokal (development/demo standalone)
secara otomatis tanpa error. Jika PostgreSQL tidak aktif, otomatis fallback ke SQLite.
"""

import socket
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

SQLITE_PATH = Path(__file__).parent.parent / "biochain.db"
SQLITE_URL = f"sqlite+aiosqlite:///{SQLITE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _is_postgres_available(host="localhost", port=5432) -> bool:
    """Cek cepat (0.2s) apakah port PostgreSQL terbuka."""
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
        use_sqlite = ("sqlite" in settings.DATABASE_URL.lower()) or (not _is_postgres_available())
        self.active_db_url = SQLITE_URL if use_sqlite else settings.DATABASE_URL
        self.active_driver = "sqlite" if use_sqlite else "postgresql"
        if use_sqlite:
            self._engine = create_async_engine(
                self.active_db_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )
        else:
            self._engine = create_async_engine(
                self.active_db_url,
                echo=False,
                pool_size=10,
                max_overflow=5,
                pool_pre_ping=True,
            )
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
        self._engine = create_async_engine(
            self.active_db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
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
