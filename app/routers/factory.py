"""Router: Pabrik (🏭) — Endpoints analytics-heavy untuk pabrik/end-user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.conversion import Conversion, CarbonCredit
from ..engines.carbon import CarbonInput, calculate_carbon_reduction
from ..engines.forecaster import ForecastInput, forecast_supply
from ..engines.quality import FeedstockSample, score_sample, yield_curve
from ..engines.blending import BlendRequest, optimize_blend

router = APIRouter()

_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)


@router.post("/carbon/calculate")
async def carbon_calculate(
    inp: CarbonInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Hitung pengurangan emisi CO₂ (IPCC Tier 2)."""
    return calculate_carbon_reduction(inp)


@router.post("/forecast")
async def supply_forecast(
    inp: ForecastInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Prediksi pasokan sekam bulanan."""
    return forecast_supply(inp)


@router.get("/forecast/30d")
async def forecast_30_days(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    harvest_area_ha: float = 500,
):
    """Proyeksi pasokan 30 hari ke depan."""
    from datetime import date, timedelta

    today = date.today()
    points = []
    for i in range(30):
        d = today + timedelta(days=i)
        inp = ForecastInput(
            harvest_area_ha=harvest_area_ha,
            month=d.month,
            year=d.year,
        )
        result = forecast_supply(inp)
        daily = result.predicted_supply_ton / 30  # rough daily estimate
        points.append({
            "date": d.isoformat(),
            "predicted": round(daily, 1),
            "pred_husk_ton": round(daily, 1),
            "low": round(result.confidence_low / 30, 1),
            "high": round(result.confidence_high / 30, 1),
        })
    return {
        "points": points,
        "harvest_area_ha": harvest_area_ha,
        "total_predicted_ton": round(sum(p["predicted"] for p in points), 1),
    }


@router.post("/quality/score")
async def quality_score(
    sample: FeedstockSample,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Evaluasi kualitas feedstock masuk."""
    return score_sample(sample)


@router.get("/quality/yield-curve")
async def quality_yield(
    user: Annotated[User, Depends(_pabrik_dep)],
    ash: float = 18.0,
):
    """Kurva rendemen biochar vs suhu pirolisis."""
    return yield_curve(ash)


@router.post("/blend/recommend")
async def blend_recommend(
    req: BlendRequest,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Optimasi campuran feedstock (Engine ③)."""
    if not req.feedstocks:
        raise HTTPException(422, "Minimal satu feedstock.")
    return optimize_blend(req)


@router.get("/esg/summary")
async def esg_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Ringkasan ESG: total emisi dihindari, kredit karbon."""
    result = await db.execute(
        select(
            func.count(CarbonCredit.id),
            func.sum(CarbonCredit.biomass_ton),
            func.sum(CarbonCredit.emission_avoided_tco2),
            func.sum(CarbonCredit.net_reduction_tco2),
        )
    )
    row = result.one()
    return {
        "total_records": row[0] or 0,
        "total_biomass_ton": round(row[1] or 0, 2),
        "total_emission_avoided_tco2": round(row[2] or 0, 4),
        "net_carbon_credits_tco2": round(row[3] or 0, 4),
        "methodology": "IPCC 2006 Tier 2",
    }


@router.get("/supply/overview")
async def supply_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Overview supply saat ini dari semua petani."""
    result = await db.execute(
        select(
            Harvest.status,
            func.count(Harvest.id),
            func.sum(Harvest.quantity_kg),
        )
        .group_by(Harvest.status)
    )
    rows = result.all()
    return {
        "by_status": [
            {"status": r[0].value if hasattr(r[0], "value") else str(r[0]), "count": r[1], "total_kg": round(r[2] or 0, 1)}
            for r in rows
        ]
    }
