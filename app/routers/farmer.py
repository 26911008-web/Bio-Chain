"""Router: Petani (🌾) — Endpoints khusus petani.

Desain: ultra-simpel, setiap endpoint hanya memerlukan data minimal.
"""

from typing import Annotated
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role, get_current_user
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..engines.incentive import calculate_incentive, DeliveryEvent

router = APIRouter()


class HarvestReportRequest(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=50000,
                               description="Jumlah sekam dalam kg")
    mill_id: int | None = None
    photo_url: str | None = None


class HarvestResponse(BaseModel):
    id: int
    uuid: str
    quantity_kg: float
    status: str
    qr_code: str
    message: str


@router.post("/harvest", response_model=HarvestResponse, status_code=201)
async def report_harvest(
    req: HarvestReportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Laporkan stok sekam yang siap dijual — One-click report."""
    h_uuid = str(uuid.uuid4())
    qr = f"BIO-{h_uuid[:8].upper()}"

    harvest = Harvest(
        uuid=h_uuid,
        farmer_id=user.id,
        mill_id=req.mill_id,
        quantity_kg=req.quantity_kg,
        status=HarvestStatus.REPORTED,
        qr_code=qr,
        photo_url=req.photo_url,
        reported_at=datetime.now(timezone.utc),
    )
    db.add(harvest)
    await db.flush()

    status_str = harvest.status.value if hasattr(harvest.status, 'value') else str(harvest.status)
    return HarvestResponse(
        id=harvest.id,
        uuid=harvest.uuid,
        quantity_kg=harvest.quantity_kg,
        status=status_str,
        qr_code=qr,
        message=f"✅ {req.quantity_kg} kg sekam berhasil dilaporkan! Pengepul akan segera menghubungi.",
    )


@router.get("/harvests")
async def list_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    limit: int = 20,
):
    """Lihat riwayat laporan panen."""
    result = await db.execute(
        select(Harvest)
        .where(Harvest.farmer_id == user.id)
        .order_by(Harvest.reported_at.desc())
        .limit(limit)
    )
    harvests = result.scalars().all()
    return [
        {
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "status": h.status.value if hasattr(h.status, 'value') else str(h.status),
            "grade": (h.grade.value if hasattr(h.grade, 'value') else str(h.grade)) if h.grade else None,
            "qr_code": h.qr_code,
            "total_price": h.total_price,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
        }
        for h in harvests
    ]


@router.get("/incentive")
async def get_incentive_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Lihat status XP dan tier insentif petani."""
    # Hitung total harvests
    result = await db.execute(
        select(func.count(Harvest.id), func.sum(Harvest.quantity_kg))
        .where(Harvest.farmer_id == user.id)
        .where(Harvest.status != HarvestStatus.REJECTED)
    )
    row = result.one()
    total_harvests = row[0] or 0
    total_kg = row[1] or 0

    return {
        "xp_total": user.xp_total,
        "tier": (user.incentive_tier.value if hasattr(user.incentive_tier, 'value') else str(user.incentive_tier)) if user.incentive_tier else "pemula",
        "total_harvests": total_harvests,
        "total_kg": round(total_kg, 1),
        "next_tier_xp": _next_tier_xp(user.xp_total),
    }


def _next_tier_xp(current_xp: int) -> int | None:
    thresholds = [100, 500, 1500]
    for t in thresholds:
        if current_xp < t:
            return t
    return None
