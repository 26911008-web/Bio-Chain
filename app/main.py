"""Bio-Chain API v2 — Production-ready FastAPI application.

Mendukung:
- Multi-persona (Petani, Pengepul, Driver, Pabrik, Admin)
- JWT Authentication
- Redis Rate Limiting
- PostgreSQL persistence
- Backward-compatible dengan API v1 (prototype alpha)

Jalankan:
  docker compose up -d                    # PostgreSQL + Redis
  py -m uvicorn app.main:app --reload     # API server
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# v2 infrastructure
from .config import settings
from .middleware.rate_limiter import RateLimiterMiddleware
from .routers import jobs as jobs_router, labs
from .security.policy import RoutePolicyMiddleware

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle with automatic SQLite fallback & demo seed."""
    from .database import engine, Base, switch_to_sqlite
    from .migrations import upgrade_schema
    from . import models  # noqa: F401  — daftarkan semua tabel ke metadata
    import app.database as db_module

    # 0. Rahasia default tidak boleh dipakai di luar mode demo
    if not settings.DEBUG and settings.JWT_SECRET.startswith("biochain-dev-secret"):
        raise RuntimeError("JWT_SECRET masih nilai default. Set JWT_SECRET di .env sebelum DEBUG=false.")

    # 1. Startup: connect to database (PostgreSQL or fallback to SQLite)
    try:
        async with db_module.engine.begin() as conn:
            if settings.AUTO_MIGRATE:
                await conn.run_sync(Base.metadata.create_all)
                added = await conn.run_sync(upgrade_schema)
            else:                                    # peran aplikasi tanpa hak DDL: cukup uji koneksi
                await conn.exec_driver_sql("SELECT 1")
                added = []
        print(f"✅ Database tables created/verified ({db_module.active_driver})"
              + (f" · kolom baru: {', '.join(added)}" if added else ""))
    except Exception as e:
        print(f"⚠️ Primary database unavailable ({e}). Fallback to local SQLite...")
        await switch_to_sqlite()
        async with db_module.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(upgrade_schema)
        print("✅ Local SQLite database tables ready (biochain.db)")

    # 2. Auto-seed demo data if empty
    try:
        from .seed import seed_if_empty
        async with db_module.async_session() as session:
            await seed_if_empty(session)
        from .services.params_store import load as load_params
        async with db_module.async_session() as session:
            await load_params(session)
    except Exception as e:
        print(f"⚠️ Auto-seed note: {e}")

    yield

    # Shutdown
    try:
        await db_module.engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title="Bio-Chain API",
    description=(
        "Smart rice-husk supply chain untuk feedstock pirolisis biochar.\n\n"
        "**ANGEL Innovation Hackathon 2026** · Topik #4 Smart Bioenergy Feedstock Optimization.\n\n"
        "Multi-persona: Petani 🌾 · Pengepul 📦 · Driver 🚛 · Pabrik 🏭 · Admin ⚙️ · Auditor 🔍"
    ),
    version="2.0.0",
    lifespan=lifespan,
    # Peta API hanya dibuka di mode demo; produksi tidak mengiklankan seluruh permukaan serangan.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# --- Middleware Stack ---
# 1. CORS — izinkan frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate Limiter (Redis-backed, fail-open)
app.add_middleware(RateLimiterMiddleware)
# 3. Kebijakan akses deny-by-default (paling luar: ditolak sebelum menyentuh rate limiter/handler)
app.add_middleware(RoutePolicyMiddleware)


# --- Domain errors → HTTP (transaksi request otomatis di-rollback oleh get_db) ---
from .services.custody import CustodyForbidden, TransitionConflict  # noqa: E402


@app.exception_handler(TransitionConflict)
async def _conflict(_: Request, exc: TransitionConflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(CustodyForbidden)
async def _forbidden(_: Request, exc: CustodyForbidden):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(LookupError)
async def _not_found(_: Request, exc: LookupError):
    return JSONResponse(status_code=404, content={"detail": str(exc).strip("'\"")})


from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as PoolTimeoutError  # noqa: E402
from .concurrency import Overloaded  # noqa: E402


def _busy(detail: str, retry_after: int = 2) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": detail}, headers={"Retry-After": str(retry_after)})


@app.exception_handler(Overloaded)
async def _overloaded(_: Request, exc: Overloaded):
    return _busy(str(exc))


@app.exception_handler(PoolTimeoutError)
async def _pool_exhausted(_: Request, exc: PoolTimeoutError):
    return _busy("Server sedang padat; permintaan Anda aman untuk diulang.")


@app.exception_handler(OperationalError)
async def _db_operational(_: Request, exc: OperationalError):
    msg = str(exc.orig).lower()
    if "locked" in msg or "busy" in msg or "timeout" in msg or "deadlock" in msg:
        return _busy("Database sibuk; ulangi sebentar lagi.")
    raise exc


@app.exception_handler(IntegrityError)
async def _integrity(_: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Data bentrok dengan transaksi lain (kirim ganda?)."})


from .engines.factory_econ import PriceMissing  # noqa: E402


@app.exception_handler(PriceMissing)
async def _price_missing(_: Request, exc: PriceMissing):
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "price_missing"})


@app.exception_handler(ZeroDivisionError)
async def _zero_div(_: Request, exc: ZeroDivisionError):
    return JSONResponse(status_code=422, content={"detail": f"Perhitungan tidak terdefinisi: {exc}"})

# Static files
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ================================================================
# v2 ROUTERS (new persona-based API)
# ================================================================
try:
    from .routers import auth, farmer, collector, driver, factory, admin, auditor, assistant, params as params_router

    app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["🔐 Auth"])
    app.include_router(farmer.router,    prefix="/api/v1/farmer",    tags=["🌾 Petani"])
    app.include_router(collector.router, prefix="/api/v1/collector", tags=["📦 Pengepul"])
    app.include_router(driver.router,    prefix="/api/v1/driver",    tags=["🚛 Driver"])
    app.include_router(factory.router,   prefix="/api/v1/factory",   tags=["🏭 Pabrik"])
    app.include_router(admin.router,     prefix="/api/v1/admin",     tags=["⚙️ Admin"])
    app.include_router(auditor.router,   prefix="/api/v1/auditor",   tags=["🔍 Auditor"])
    app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["🤖 Asisten AI"])
    app.include_router(params_router.router, prefix="/api/v1/params", tags=["⚙️ Parameter Asumsi"])
    from .routers import reports as reports_router
    app.include_router(reports_router.router, prefix="/api/v1/reports", tags=["📊 Laporan Bulanan"])
    app.include_router(reports_router.router, prefix="/api/reports", include_in_schema=False)
    print("✅ v2 persona routers loaded")
except Exception as e:
    print(f"⚠️  v2 routers not loaded ({e}). Legacy API still available.")


# ================================================================
# HEALTH & STATUS
# ================================================================
@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "version": "2.0.0", "engines": 7}


@app.get("/api/v1/system/status", tags=["System"])
async def system_status():
    import app.database as db_module
    return {
        "status": "healthy",
        "version": "2.0.0",
        "engines": 7,
        "database": db_module.active_driver,
        "demo_ready": True,
    }


# ================================================================
# LEGACY API (backward compatible — prototype alpha)
# ================================================================
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


app.include_router(labs.router, prefix="/api/v1/labs", tags=["🧪 Lab 7 Engine (Pabrik/Admin)"])
app.include_router(jobs_router.router, prefix="/api/v1/jobs", tags=["⏳ Jobs (asinkron)"])


