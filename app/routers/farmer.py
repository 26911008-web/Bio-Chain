"""Router: Petani (🌾) — Endpoints khusus petani.

Desain: ultra-simpel, setiap endpoint hanya memerlukan data minimal.
"""

from typing import Annotated
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role, get_current_user
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, Mill
from ..models.ledger import BiocharLedgerEntry, CustodyEvent, CustodyStage
from ..engines.incentive import calculate_incentive, DeliveryEvent, next_tier_xp
from ..models.trade import StockListing
from ..services import trade
from ..services.biomass import get_biomass
from ..services.qr_sign import new_qr_code
from ..services.custody import find_replay, trusted_device_time, wallet_balance
from ..security.url import EvidenceUrl

router = APIRouter()


class HarvestReportRequest(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=50000,
                               description="Jumlah biomassa dalam kg")
    commodity: str = Field("sekam_padi", max_length=24, description="Kode komoditas (GET /api/v1/biomass)")
    mill_id: int | None = None
    photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    # Opsional: taksiran petani. Tidak memengaruhi harga — QC pengepul yang menentukan; dipakai untuk umpan balik
    moisture_est: float | None = Field(None, ge=0, le=60, description="Taksiran kadar air (%), boleh kosong")
    grade_est: str | None = Field(None, pattern="^[ABCD]$", description="Taksiran grade A-D, boleh kosong")
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = Field(None, description="Waktu lapor di perangkat (bisa saat offline)")


class HarvestResponse(BaseModel):
    id: int
    uuid: str
    quantity_kg: float
    status: str
    qr_code: str
    message: str
    replayed: bool = False
    commodity: str = "sekam_padi"


@router.post("/harvest", response_model=HarvestResponse, status_code=201)
async def report_harvest(
    req: HarvestReportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Laporkan stok sekam yang siap dijual — One-click report.

    Idempoten: laporan yang dikirim ulang dari antrean offline dengan client_event_id sama
    mengembalikan harvest yang sudah dibuat, bukan membuat duplikat.
    """
    uid = user.id          # simpan: objek user kedaluwarsa bila transaksi di-rollback di bawah
    replay = await find_replay(db, req.client_event_id)
    if replay is not None:
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.farmer_id != user.id:
            raise HTTPException(409, "client_event_id sudah dipakai.")
        return HarvestResponse(id=h.id, uuid=h.uuid, quantity_kg=h.quantity_kg, status=h.status.value,
                               qr_code=h.qr_code, message="ℹ️ Laporan ini sudah tercatat sebelumnya.",
                               replayed=True)
    if req.mill_id is not None and not (await db.execute(select(Mill.id).where(Mill.id == req.mill_id))).first():
        raise HTTPException(422, "mill_id tidak dikenal")

    h_uuid = str(uuid.uuid4())
    qr = new_qr_code(h_uuid)

    harvest = Harvest(
        uuid=h_uuid,
        farmer_id=user.id,
        mill_id=req.mill_id,
        quantity_kg=req.quantity_kg,
        commodity=(await get_biomass(db, req.commodity)).code,
        status=HarvestStatus.REPORTED,
        qr_code=qr,
        photo_url=req.photo_url,
        farmer_moisture_est=req.moisture_est,
        farmer_grade_est=req.grade_est,
        reported_at=trusted_device_time(req.client_recorded_at)[0],
    )
    db.add(harvest)
    await db.flush()
    db.add(CustodyEvent(harvest_id=harvest.id, stage=CustodyStage.FARMER_REPORT.value, from_status=None,
                        to_status=HarvestStatus.REPORTED.value, weight_kg=req.quantity_kg, actor_id=user.id,
                        actor_role=UserRole.PETANI.value, client_event_id=req.client_event_id,
                        client_recorded_at=req.client_recorded_at, note="Estimasi petani"))
    try:
        await db.flush()
    except IntegrityError:
        # Spam-click: kiriman kembar dengan client_event_id sama sudah menang lebih dulu.
        # Batalkan insert kita (harvest + event) dan kembalikan hasil pemenang.
        await db.rollback()
        replay = await find_replay(db, req.client_event_id)
        if replay is None:
            raise
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.farmer_id != uid:
            raise HTTPException(409, "client_event_id sudah dipakai.")
        return HarvestResponse(id=h.id, uuid=h.uuid, quantity_kg=h.quantity_kg, status=h.status.value,
                               qr_code=h.qr_code, message="ℹ️ Laporan ini sudah tercatat sebelumnya.",
                               replayed=True)

    status_str = harvest.status.value if hasattr(harvest.status, 'value') else str(harvest.status)
    return HarvestResponse(
        id=harvest.id,
        uuid=harvest.uuid,
        quantity_kg=harvest.quantity_kg,
        status=status_str,
        qr_code=qr,
        commodity=harvest.commodity,
        message=f"✅ {req.quantity_kg} kg berhasil dilaporkan! Pengepul akan segera menghubungi.",
    )


@router.get("/payments")
async def my_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Bukti bayar dari pengepul atas sekam saya (F8): bruto, potongan pajak, bersih, metode, nomor kuitansi."""
    from ..models.compliance import FarmerPayment
    from ..services.payments import payment_dict
    rows = (await db.execute(select(FarmerPayment).where(FarmerPayment.farmer_id == user.id)
                             .order_by(FarmerPayment.id.desc()).limit(100))).scalars().all()
    return [payment_dict(p) for p in rows]


@router.get("/payments/overview")
async def my_payment_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Menu Pembayaran petani: sudah dibayar, menunggu bayar (terlambat bila lewat batas), dan belum ditimbang."""
    from ..services.payments import farmer_overview
    return await farmer_overview(db, user)


@router.get("/quality-feedback")
async def my_quality_feedback(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    months: int = 6,
):
    """Kurva mutu bulanan dari QC pengepul & QC pabrik + defect rate dan penyebabnya (umpan balik petani)."""
    from ..services.feedback import farmer_quality_feedback
    return await farmer_quality_feedback(db, user.id, min(max(months, 1), 24))


class RedeemRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    kg: float = Field(..., gt=0, le=100_000)
    land_area_ha: float | None = Field(None, gt=0, le=100, description="Luas sawah tujuan aplikasi")
    pickup_point: str = Field("pabrik", pattern="^(pabrik|pengepul)$")
    note: str | None = Field(None, max_length=300)


@router.get("/biochar/estimate")
async def biochar_estimate(
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    kg: float,
    land_area_ha: float,
):
    """Perkiraan manfaat ekonomi biochar di sawah (rumus pendekatan sirkular, parameter menu Pabrik/Admin)."""
    from ..engines.biochar_field import estimate
    if kg <= 0 or land_area_ha <= 0:
        raise HTTPException(422, "kg dan luas sawah harus > 0")
    return estimate(kg, land_area_ha)


@router.get("/biochar/redemptions")
async def my_redemptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    from ..services.circular import redemption_dict
    from ..models.circular import BiocharRedemption
    rows = (await db.execute(select(BiocharRedemption).where(BiocharRedemption.farmer_id == user.id)
                             .order_by(BiocharRedemption.id.desc()).limit(50))).scalars().all()
    return [redemption_dict(r) for r in rows]


@router.post("/biochar/redeem", status_code=201)
async def redeem_biochar(
    req: RedeemRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Ajukan pengambilan biochar untuk sawah. Saldo ditahan; ledger berkurang saat pabrik menyerahkan karung."""
    from ..services.circular import request_redemption
    return await request_redemption(db, user, req.kg, req.land_area_ha, req.pickup_point, req.note)


@router.post("/biochar/redemptions/{redemption_id}/cancel")
async def cancel_redemption(
    redemption_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    from ..services.circular import cancel_redemption as _cancel
    return await _cancel(db, user, redemption_id, "dibatalkan petani")


@router.get("/mills")
async def list_mills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI, UserRole.PENGEPUL))],  # pengepul: lapor proxy
):
    """Daftar penggilingan untuk form lapor (pengganti /supply/mills yang kini khusus lab)."""
    mills = (await db.execute(
        select(Mill).where(Mill.is_active.is_(True)).order_by(Mill.kecamatan, Mill.name)
    )).scalars().all()
    return [{"id": m.id, "name": m.name, "kecamatan": m.kecamatan} for m in mills]


@router.get("/wallet")
async def biochar_wallet(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    limit: int = 20,
):
    """Saldo biochar petani (hak dari sekam yang sudah diolah) + riwayat ledger."""
    entries = (await db.execute(
        select(BiocharLedgerEntry).where(BiocharLedgerEntry.farmer_id == user.id)
        .order_by(BiocharLedgerEntry.id.desc()).limit(min(max(limit, 1), 100))
    )).scalars().all()
    from ..services.circular import pending_kg
    balance = await wallet_balance(db, user.id)
    held = await pending_kg(db, user.id)
    return {
        "farmer_id": user.id,
        "balance_kg": balance,
        "held_kg": held,                                   # sedang diajukan, belum diserahkan
        "available_kg": round(max(0.0, balance - held), 2),
        "entries": [{"id": e.id, "type": e.entry_type, "amount_kg": e.amount_kg, "harvest_id": e.harvest_id,
                     "conversion_id": e.conversion_id, "note": e.note,
                     "created_at": e.created_at.isoformat() if e.created_at else None} for e in entries],
    }


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
        .limit(min(max(limit, 1), 100))
    )
    harvests = result.scalars().all()
    return [
        {
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "commodity": h.commodity or "sekam_padi",
            "status": h.status.value if hasattr(h.status, 'value') else str(h.status),
            "grade": (h.grade.value if hasattr(h.grade, 'value') else str(h.grade)) if h.grade else None,
            "qr_code": h.qr_code,
            "verified_kg": h.verified_kg,
            "received_kg": h.received_kg,
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
        "next_tier_xp": next_tier_xp(user.xp_total or 0),
    }


# ---------------------------------------------------------------- Pasar B2B: listing & pilih tawaran
class ListingCreate(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=200_000)
    commodity: str = Field("sekam_padi", max_length=24, description="Kode komoditas (GET /api/v1/biomass)")
    moisture_pct: float | None = Field(None, ge=0, le=60)
    grade_estimate: str | None = Field(None, pattern="^(A|B|C|D)$")
    allow_jemput: bool = True
    allow_antar: bool = False
    ask_price_jemput: float | None = Field(None, gt=0, le=10_000, description="Rp/kg di lokasi petani")
    ask_price_antar: float | None = Field(None, gt=0, le=10_000, description="Rp/kg diantar ke gudang pengepul")
    mill_id: int | None = None
    expires_in_days: int = Field(7, ge=1, le=60)
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000)


class AcceptBid(BaseModel):
    bid_id: int = Field(..., gt=0)
    quantity_kg: float = Field(..., gt=0, le=200_000, description="Boleh sebagian dari tawaran")


@router.post("/listings", status_code=201)
async def create_listing(
    req: ListingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Pasang stok sekam untuk ditawar pengepul (skema jemput dan/atau antar, harga minimum per skema)."""
    try:
        listing = await trade.create_listing(db, user, req.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return trade.listing_dict(listing)


@router.get("/listings")
async def my_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    rows = (await db.execute(select(StockListing).where(StockListing.farmer_id == user.id)
                             .order_by(StockListing.id.desc()).limit(50))).scalars().all()
    return [trade.listing_dict(r) for r in rows]


@router.get("/listings/{listing_id}/bids")
async def listing_bids(
    listing_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Semua tawaran + nilai bersih per kg bagi petani (skema antar dikurangi ongkos antar)."""
    return await trade.bids_for_farmer(db, user, listing_id)


@router.post("/listings/{listing_id}/accept")
async def accept_bid(
    listing_id: int,
    req: AcceptBid,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani memilih tawaran (boleh sebagian). Atomik: stok tidak pernah terjual melebihi sisa."""
    try:
        return await trade.accept_bid(db, user, listing_id, req.bid_id, req.quantity_kg)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/listings/{listing_id}/cancel")
async def cancel_listing(
    listing_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    await trade.cancel_listing(db, user, listing_id)
    return {"listing_id": listing_id, "status": "cancelled"}
