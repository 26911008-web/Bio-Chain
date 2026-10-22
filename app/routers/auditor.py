"""Router: Auditor (🔍) — akses baca-saja ke chain-of-custody, mass balance, dan ledger biochar.

Tidak ada endpoint tulis di router ini; role auditor juga tidak ada di tabel TRANSITIONS.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.harvest import Harvest
from ..models.ledger import BiocharLedgerEntry
from ..models.user import User, UserRole
from ..services.custody import mass_balance

router = APIRouter()

_auditor = require_role(UserRole.AUDITOR, UserRole.ADMIN)


@router.get("/discrepancies")
async def list_discrepancies(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_auditor)],
    limit: int = 50,
):
    """Harvest dengan selisih timbangan di luar toleransi."""
    rows = (await db.execute(
        select(Harvest).where(Harvest.discrepancy_flag.is_(True)).order_by(Harvest.id.desc())
        .limit(min(max(limit, 1), 200))
    )).scalars().all()
    return {
        "tolerance_pct": P("sirkular.shrinkage_tolerance_pct"),
        "items": [{"harvest_id": h.id, "farmer_id": h.farmer_id, "verified_kg": h.verified_kg,
                   "received_kg": h.received_kg, "shrinkage_pct": h.shrinkage_pct, "note": h.discrepancy_note}
                  for h in rows],
    }


@router.get("/mass-balance/{harvest_id}")
async def harvest_mass_balance(
    harvest_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_auditor)],
):
    return await mass_balance(db, harvest_id)


@router.get("/summary")
async def circular_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_auditor)],
):
    """Neraca massa agregat: sekam ditimbang pengepul → diterima pabrik → biochar kembali ke petani."""
    w = (await db.execute(select(
        func.coalesce(func.sum(Harvest.verified_kg), 0.0),
        func.coalesce(func.sum(Harvest.received_kg), 0.0),
        func.count(Harvest.id).filter(Harvest.discrepancy_flag.is_(True)),
    ).where(Harvest.received_kg.is_not(None)))).one()
    allocated = (await db.execute(
        select(func.coalesce(func.sum(BiocharLedgerEntry.amount_kg), 0.0))
        .where(BiocharLedgerEntry.entry_type == "allocation")
    )).scalar_one()
    verified, received, flagged = float(w[0]), float(w[1]), int(w[2])
    return {
        "collector_scale_kg": round(verified, 3),
        "factory_scale_kg": round(received, 3),
        "total_shrinkage_kg": round(verified - received, 3),
        "total_shrinkage_pct": round((verified - received) / verified * 100, 3) if verified > 0 else 0.0,
        "flagged_harvests": flagged,
        "biochar_allocated_to_farmers_kg": round(float(allocated), 3),
    }
