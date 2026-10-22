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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Legacy imports (backward compat)
from .data import DEPOT, MILLS
from .engines.blending import DEFAULT_FEEDSTOCKS, PRODUCT_SPECS, BlendRequest, optimize_blend
from .engines.quality import REF_ASH, FeedstockSample, score_sample, yield_curve
from .engines.routing import RouteRequest, plan_routes

# New engine imports
from .engines.carbon import CarbonInput, calculate_carbon_reduction
from .engines.forecaster import ForecastInput, forecast_supply
from .engines.incentive import DeliveryEvent, calculate_incentive

# v2 infrastructure
from .config import settings
from .middleware.rate_limiter import RateLimiterMiddleware

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle with automatic SQLite fallback & demo seed."""
    from .database import engine, Base, switch_to_sqlite
    import app.database as db_module

    # 1. Startup: connect to database (PostgreSQL or fallback to SQLite)
    try:
        async with db_module.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"✅ Database tables created/verified ({db_module.active_driver})")
    except Exception as e:
        print(f"⚠️ Primary database unavailable ({e}). Fallback to local SQLite...")
        await switch_to_sqlite()
        async with db_module.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Local SQLite database tables ready (biochain.db)")

    # 2. Auto-seed demo data if empty
    try:
        from .seed import seed_if_empty
        async with db_module.async_session() as session:
            await seed_if_empty(session)
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
        "Multi-persona: Petani 🌾 · Pengepul 📦 · Driver 🚛 · Pabrik 🏭 · Admin ⚙️"
    ),
    version="2.0.0",
    lifespan=lifespan,
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

# Static files
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ================================================================
# v2 ROUTERS (new persona-based API)
# ================================================================
try:
    from .routers import auth, farmer, collector, driver, factory, admin

    app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["🔐 Auth"])
    app.include_router(farmer.router,    prefix="/api/v1/farmer",    tags=["🌾 Petani"])
    app.include_router(collector.router, prefix="/api/v1/collector", tags=["📦 Pengepul"])
    app.include_router(driver.router,    prefix="/api/v1/driver",    tags=["🚛 Driver"])
    app.include_router(factory.router,   prefix="/api/v1/factory",   tags=["🏭 Pabrik"])
    app.include_router(admin.router,     prefix="/api/v1/admin",     tags=["⚙️ Admin"])
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


@app.post("/quality/score", tags=["② Quality & Yield (Legacy)"])
def quality_score(sample: FeedstockSample):
    return score_sample(sample)


@app.get("/quality/yield-curve", tags=["② Quality & Yield (Legacy)"])
def quality_yield_curve(ash: float = REF_ASH):
    return yield_curve(ash)


@app.get("/blend/defaults", tags=["③ Blending (Legacy)"])
def blend_defaults():
    return {
        "feedstocks": [f.model_dump() for f in DEFAULT_FEEDSTOCKS],
        "products": {k: {"label": v["label"], "spec": v["spec"].model_dump()}
                     for k, v in PRODUCT_SPECS.items()},
    }


@app.post("/blend/recommend", tags=["③ Blending (Legacy)"])
def blend_recommend(req: BlendRequest):
    if not req.feedstocks:
        raise HTTPException(422, "Minimal satu feedstock.")
    return optimize_blend(req)


@app.get("/supply/mills", tags=["⑤ Routing (Legacy)"])
def supply_mills():
    return {"depot": DEPOT, "mills": MILLS}


@app.post("/routes/optimize", tags=["⑤ Routing (Legacy)"])
def routes_optimize(req: RouteRequest):
    mills = MILLS if not req.mill_ids else [m for m in MILLS if m["id"] in set(req.mill_ids)]
    if not mills:
        raise HTTPException(422, "Tidak ada penggilingan yang dipilih.")
    return plan_routes(DEPOT, mills, req)


# ================================================================
# NEW STANDALONE ENGINE ENDPOINTS (no auth, for demo/hackathon)
# ================================================================
@app.post("/carbon/calculate", tags=["⑦ ESG Carbon (New)"])
def carbon_calc(inp: CarbonInput):
    """Hitung pengurangan emisi CO₂ — IPCC Tier 2."""
    return calculate_carbon_reduction(inp)


@app.post("/forecast/supply", tags=["① Supply Forecast (New)"])
def forecast(inp: ForecastInput):
    """Prediksi pasokan sekam bulanan."""
    return forecast_supply(inp)


@app.post("/incentive/calculate", tags=["⑥ Incentive (New)"])
def incentive_calc(event: DeliveryEvent):
    """Hitung XP dan tier insentif petani."""
    return calculate_incentive(event)
