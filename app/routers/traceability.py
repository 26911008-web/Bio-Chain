"""Router API untuk Ketelusuran Sirkular QR Code End-to-End.

Dua jalur akses:
- **Pengguna login** (UI "Lacak QR sirkular"): query berjalan dengan identitas RLS pengguna itu.
- **Publik / konsumen tanpa login** (scan QR di karung/kemasan): hanya kode QR **bertanda tangan**
  (``BIO-XXXXXXXX-TTTTTT``, HMAC kunci server) yang diterima, sehingga lot tidak bisa dienumerasi dengan
  ID angka/kode berurutan. Data dibaca dengan identitas sistem (baca-saja); DTO sudah menyamarkan HP & GPS.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user, security
from ..models.harvest import Harvest
from ..models.user import User
from ..security.rls import SYSTEM_IDENTITY, apply_now, bind_identity
from ..services.circular_traceability import get_circular_traceability, COMMODITY_LABELS
from ..services.qr_sign import normalize, signature_valid

router = APIRouter()


async def optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Pengguna login bila ada Bearer yang sah; None untuk akses publik. Token rusak/kedaluwarsa tetap 401."""
    if credentials is None:
        return None
    return await get_current_user(request, credentials, db)


@router.get("/circular/{identifier}")
async def circular_trace(
    identifier: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(optional_user)],
):
    """Mengambil silsilah lengkap ketelusuran sirkular QR Code dari petani sampai kembali ke sawah."""
    if user is None:
        code = normalize(identifier)
        if not signature_valid(code):
            raise HTTPException(401, "Tanpa login, ketelusuran hanya bisa dibuka dengan scan QR asli pada karung/kemasan.")
        bind_identity(db, *SYSTEM_IDENTITY)
        await apply_now(db)
        identifier = code
    return await get_circular_traceability(db, identifier)


@router.get("/recent")
async def recent_circular_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50),
):
    """Daftar lot biomassa terkini (dalam cakupan RLS pengguna) untuk navigasi cepat. Wajib login."""
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
