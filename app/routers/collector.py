"""Router: Pengepul (📦) — Endpoints khusus pengepul/collector."""

from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, QualityGrade
from ..engines.quality import FeedstockSample, score_sample

router = APIRouter()


class VerifyHarvestRequest(BaseModel):
    harvest_id: int
    moisture: float = Field(..., ge=0, le=60)
    ash: float = Field(..., ge=0, le=40)
    volatile_matter: float = Field(..., ge=0, le=100)
    fixed_carbon: float = Field(..., ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)


@router.get("/available-harvests")
async def list_available_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    kecamatan: str | None = None,
):
    """Lihat laporan sekam dari petani yang siap diverifikasi/diambil."""
    query = select(Harvest).where(Harvest.status == HarvestStatus.REPORTED)
    if kecamatan:
        query = query.join(User, Harvest.farmer_id == User.id).where(
            User.kecamatan == kecamatan
        )
    query = query.order_by(Harvest.reported_at.desc()).limit(50)

    result = await db.execute(query)
    harvests = result.scalars().all()

    # H1 fix: Batch-load all farmers in a single query instead of N+1
    farmer_ids = list({h.farmer_id for h in harvests if h.farmer_id})
    farmers_map = {}
    if farmer_ids:
        farmers_result = await db.execute(
            select(User).where(User.id.in_(farmer_ids))
        )
        farmers_map = {u.id: u for u in farmers_result.scalars().all()}

    results_list = []
    for h in harvests:
        farmer = farmers_map.get(h.farmer_id)
        results_list.append({
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "farmer_id": h.farmer_id,
            "farmer_name": farmer.full_name if farmer else f"Petani #{h.farmer_id}",
            "farmer_phone": farmer.phone if farmer else None,
            "kecamatan": farmer.kecamatan if farmer else None,
            "qr_code": h.qr_code,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
        })
    return results_list


@router.post("/verify")
async def verify_harvest(
    req: VerifyHarvestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Verifikasi kualitas sekam dan beri grade menggunakan Engine ②."""
    result = await db.execute(select(Harvest).where(Harvest.id == req.harvest_id))
    harvest = result.scalar_one_or_none()
    if not harvest:
        raise HTTPException(404, "Harvest tidak ditemukan")
    if harvest.status != HarvestStatus.REPORTED:
        raise HTTPException(400, "Harvest sudah diverifikasi/diambil")

    # Jalankan Engine ② Quality Scorer
    sample = FeedstockSample(
        moisture=req.moisture,
        ash=req.ash,
        volatile_matter=req.volatile_matter,
        fixed_carbon=req.fixed_carbon,
        contamination=req.contamination,
        pyrolysis_temp_c=req.pyrolysis_temp_c,
    )
    quality = score_sample(sample)

    # Update harvest
    harvest.collector_id = user.id
    harvest.moisture = req.moisture
    harvest.ash = req.ash
    harvest.volatile_matter = req.volatile_matter
    harvest.fixed_carbon = req.fixed_carbon
    harvest.contamination = req.contamination
    harvest.grade = quality["grade"]
    harvest.quality_score = quality["score"]
    harvest.status = HarvestStatus.VERIFIED
    harvest.verified_at = datetime.now(timezone.utc)

    # Hitung harga
    base_price = 400  # Rp/kg base
    harvest.base_price_per_kg = base_price
    harvest.incentive_multiplier = quality["price_multiplier"]
    harvest.total_price = harvest.quantity_kg * base_price * quality["price_multiplier"]

    return {
        "harvest_id": harvest.id,
        "grade": quality["grade"],
        "score": quality["score"],
        "total_price": harvest.total_price,
        "quality_detail": quality,
        "message": f"Sekam dinilai Grade {quality['grade']} (skor {quality['score']})",
    }


@router.get("/daily-summary")
async def daily_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Ringkasan koleksi hari ini."""
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    next_day = start_of_day + timedelta(days=1)
    result = await db.execute(
        select(
            func.count(Harvest.id),
            func.sum(Harvest.quantity_kg),
            func.avg(Harvest.quality_score),
            func.sum(Harvest.total_price),
        )
        .where(Harvest.collector_id == user.id)
        .where(Harvest.verified_at >= start_of_day)
        .where(Harvest.verified_at < next_day)
    )
    row = result.one()
    return {
        "date": start_of_day.date().isoformat(),
        "total_pickups": row[0] or 0,
        "total_kg": round(row[1] or 0, 1),
        "avg_quality_score": round(row[2] or 0, 1),
        "total_cost": round(row[3] or 0),
    }
