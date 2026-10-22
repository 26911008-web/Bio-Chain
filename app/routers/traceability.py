"""Router API untuk Ketelusuran Sirkular QR Code End-to-End."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session
from ..models.harvest import Harvest, HarvestStatus
from ..services.circular_traceability import get_circular_traceability, COMMODITY_LABELS

router = APIRouter()


async def get_db():
    async with async_session() as session:
        yield session


@router.get("/circular/{identifier}")
async def circular_trace(
    identifier: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mengambil silsilah lengkap ketelusuran sirkular QR Code dari petani sampai kembali ke sawah."""
    return await get_circular_traceability(db, identifier)


@router.get("/recent")
async def recent_circular_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
):
    """Daftar lot biomassa terkini yang memiliki ketelusuran sirkular untuk navigasi cepat."""
    rows = (await db.execute(
        select(Harvest)
        .order_by(Harvest.id.desc())
        .limit(limit)
    )).scalars().all()

    items = []
    for h in rows:
        wr_code = h.origin_qr_code or h.qr_code or f"WR-HV-{h.id:04d}"
        items.append({
            "id": h.id,
            "origin_qr_code": wr_code,
            "qr_code": h.qr_code,
            "commodity": h.commodity,
            "commodity_name": COMMODITY_LABELS.get(h.commodity, h.commodity.replace("_", " ").title()),
            "quantity_kg": h.verified_kg or h.quantity_kg,
            "status": h.status.value if hasattr(h.status, "value") else str(h.status),
            "reported_at": (h.reported_at or h.created_at).isoformat() if (h.reported_at or h.created_at) else None,
        })
    return items
