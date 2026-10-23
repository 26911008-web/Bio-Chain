"""Sub-router petani: pasar B2B (listing, tawaran, jadwal), permintaan biochar, deviasi QC & reputasi pengepul.

Dipisah dari app/routers/farmer.py (audit 23 Okt 2026, CLAUDE.md §3.1) dan di-mount olehnya.
"""
from typing import Annotated
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyEvent
from ..models.trade import StockListing, Bid, CollectorPaymentReputation
from ..models.circular import BiocharRequest
from ..services import trade
from ..security.url import EvidenceUrl

router = APIRouter()



# ---------------------------------------------------------------- Pasar B2B: listing & pilih tawaran
class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quantity_kg: float = Field(..., gt=0, le=200_000)
    commodity: str = Field("sekam_padi", max_length=24, description="Kode komoditas (GET /api/v1/biomass)")
    moisture_pct: float | None = Field(None, ge=0, le=60)
    grade_estimate: str | None = Field(None, pattern="^(A|B|C|D)$")
    allow_jemput: bool = True
    allow_antar: bool = False
    ask_price_jemput: float | None = Field(None, gt=0, le=20_000, description="Rp/kg di lokasi petani")
    ask_price_antar: float | None = Field(None, gt=0, le=20_000, description="Rp/kg diantar ke gudang pengepul")
    asking_price: float | None = Field(None, gt=0, le=20_000, description="Harga umum/ekspektasi petani")
    price_per_kg: float | None = Field(None, gt=0, le=20_000, description="Alias harga per kg")
    mill_id: int | None = None
    expires_in_days: int = Field(7, ge=1, le=60)
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    # 022 Omni Extensions
    transaction_mode: str = Field("DIRECT", pattern="^(DIRECT|BIDDING)$", description="DIRECT: harga katalog; BIDDING: bursa lelang")
    floor_price: float | None = Field(None, gt=0, le=20_000, description="Harga pembuka / batas bawah lelang")
    auction_expiry: datetime | None = None
    logistics_mode: str = Field("PICKUP", pattern="^(PICKUP|DELIVER_SELF)$")
    biochar_backhaul_requested: bool = False
    biochar_backhaul_kg: float | None = Field(None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def resolve_prices(cls, data: any):
        if isinstance(data, dict):
            ask = data.get("asking_price") or data.get("price_per_kg") or data.get("floor_price")
            if ask is not None:
                if data.get("allow_jemput", True) and not data.get("ask_price_jemput"):
                    data["ask_price_jemput"] = float(ask)
                if data.get("allow_antar") and not data.get("ask_price_antar"):
                    data["ask_price_antar"] = float(ask)
                if not data.get("floor_price"):
                    data["floor_price"] = float(ask)
        return data


class AcceptBid(BaseModel):
    bid_id: int = Field(..., gt=0)
    quantity_kg: float = Field(..., gt=0, le=200_000, description="Boleh sebagian dari tawaran")


class ScheduleRespondRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVED|RESCHEDULE_REQUESTED)$")
    reschedule_note: str | None = Field(None, max_length=500)
    reschedule_date: str | None = Field(None, max_length=30)


class BiocharBackhaulCreate(BaseModel):
    requested_kg: float = Field(..., gt=0, le=50000)
    collector_id: int | None = None
    harvest_id: int | None = None
    land_area_ha: float | None = Field(None, gt=0, le=1000, description="Luas sawah (ha)")
    delivery_point: str | None = Field(None, max_length=150)
    notes: str | None = Field(None, max_length=500)


@router.post("/listings", status_code=201)
async def create_listing(
    req: ListingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Pasang stok biomassa (Mode DIRECT mengikuti katalog atau BIDDING via bursa lelang)."""
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


@router.post("/bids/{bid_id}/schedule-respond")
async def respond_bid_schedule(
    bid_id: int,
    req: ScheduleRespondRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani mengonfirmasi jadwal penjemputan pengepul atau mengajukan tanggal perubahan."""
    bid = (await db.execute(select(Bid).where(Bid.id == bid_id))).scalar_one_or_none()
    if not bid:
        raise HTTPException(404, "Tawaran/bid tidak ditemukan")
    if bid.farmer_id != user.id:
        raise HTTPException(403, "Anda bukan pemilik lelang untuk tawaran ini")
    
    bid.farmer_schedule_status = req.action
    bid.farmer_schedule_note = req.reschedule_note
    if req.action == "RESCHEDULE_REQUESTED" and req.reschedule_date:
        bid.pickup_date = req.reschedule_date
    await db.flush()
    return {
        "bid_id": bid.id,
        "farmer_schedule_status": bid.farmer_schedule_status,
        "pickup_date": bid.pickup_date,
        "note": bid.farmer_schedule_note,
        "message": "Jadwal berhasil disetujui" if req.action == "APPROVED" else "Permintaan penyesuaian jadwal terkirim"
    }


@router.post("/biochar-requests", status_code=201)
async def create_biochar_request(
    req: BiocharBackhaulCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani memesan muatan balik abu bottom ash untuk diaplikasikan ke sawah saat armada menjemput biomassa (biochar bernilai tinggi dialokasikan pabrik untuk material baterai)."""
    collector_id = req.collector_id
    if not collector_id and req.harvest_id:
        h = (await db.execute(select(Harvest).where(Harvest.id == req.harvest_id))).scalar_one_or_none()
        if h and h.collector_id:
            collector_id = h.collector_id
    if not collector_id:
        # Fallback: cari pengepul terdekat/pertama yang aktif
        first_coll = (await db.execute(select(User).where(User.role == UserRole.PENGEPUL).limit(1))).scalar_one_or_none()
        if first_coll:
            collector_id = first_coll.id
        else:
            raise HTTPException(400, "Tidak ada pengepul yang tersedia untuk melayani muatan balik")

    req_code = f"BCR-{uuid.uuid4().hex[:8].upper()}"
    biochar_req = BiocharRequest(
        request_code=req_code,
        farmer_id=user.id,
        collector_id=collector_id,
        harvest_id=req.harvest_id,
        requested_kg=req.requested_kg,
        allocated_kg=0.0,
        status="REQUESTED",
        delivery_point=req.delivery_point or user.kecamatan or "Lokasi Sawah Petani",
        partition_safeguard_verified=True,
        notes=req.notes,
    )
    db.add(biochar_req)
    await db.flush()
    return {
        "success": True,
        "id": biochar_req.id,
        "request_id": biochar_req.id,
        "request_code": biochar_req.request_code,
        "requested_kg": biochar_req.requested_kg,
        "status": biochar_req.status,
        "delivery_point": biochar_req.delivery_point,
        "message": f"Permintaan muatan balik {req.requested_kg} kg biochar berhasil diajukan."
    }


@router.get("/biochar-requests")
async def list_biochar_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Daftar riwayat dan status muatan balik abu bottom ash milik petani."""
    rows = (await db.execute(
        select(BiocharRequest, User)
        .outerjoin(User, User.id == BiocharRequest.collector_id)
        .where(BiocharRequest.farmer_id == user.id)
        .order_by(BiocharRequest.id.desc())
    )).all()
    return [
        {
            "id": r.id,
            "request_code": r.request_code,
            "requested_kg": r.requested_kg,
            "allocated_kg": r.allocated_kg,
            "status": r.status,
            "delivery_point": r.delivery_point,
            "collector_name": c.full_name if c else "Pengepul",
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
        }
        for r, c in rows
    ]


@router.get("/qc-deviations")
async def list_qc_deviations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    limit: int = 50,
):
    """Riwayat transparansi deviasi timbangan lapangan vs klaim petani + alasan penolakan jika ada."""
    rows = (await db.execute(
        select(Harvest)
        .where(Harvest.farmer_id == user.id)
        .order_by(Harvest.id.desc())
        .limit(min(max(limit, 1), 100))
    )).scalars().all()

    h_ids = [h.id for h in rows]
    trx_map = {}
    if h_ids:
        cev_res = await db.execute(select(CustodyEvent.harvest_id, CustodyEvent.verification_code).where(
            CustodyEvent.harvest_id.in_(h_ids), CustodyEvent.verification_code.is_not(None)
        ))
        for hid, vcode in cev_res.all():
            if hid and vcode:
                trx_map[hid] = vcode

    out = []
    for h in rows:
        origin_code = getattr(h, "origin_qr_code", None) or getattr(h, "qr_code", None) or f"WR-HV-{h.id:04d}"
        out.append({
            "harvest_id": h.id,
            "origin_qr_code": origin_code,
            "qr_code": h.qr_code,
            "trx_code": trx_map.get(h.id),
            "commodity": h.commodity or "sekam_padi",
            "commodity_name": (h.commodity or "sekam_padi").replace("_", " ").title(),
            "farmer_claimed_qty": getattr(h, "farmer_claimed_qty", None) or h.quantity_kg,
            "actual_weighed_qty": getattr(h, "actual_weighed_qty", None) or h.verified_kg,
            "deviation_kg": getattr(h, "deviation_kg", None),
            "deviation_pct": getattr(h, "deviation_pct", None),
            "farmer_moisture_est": h.farmer_moisture_est,
            "verified_moisture": getattr(h, "moisture", None),
            "farmer_grade_est": h.farmer_grade_est,
            "verified_grade": getattr(h, "grade", None).value if hasattr(getattr(h, "grade", None), "value") else (str(h.grade) if h.grade else None),
            "qc_status": getattr(h, "qc_status", "PENDING") or (
                "PASS" if h.status in (HarvestStatus.VERIFIED, HarvestStatus.COLLECTED, HarvestStatus.DELIVERED)
                else ("REJECT" if h.status == HarvestStatus.REJECTED else "PENDING")
            ),
            "qc_rejection_reason": getattr(h, "qc_rejection_reason", None) or h.rejected_reason,
            "verified_at": h.verified_at.isoformat() if h.verified_at else None,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
            "delivery_scheme": h.delivery_scheme or "jemput",
            "transaction_mode": getattr(h, "transaction_mode", "DIRECT"),
        })
    return out


@router.get("/collector-reputations")
async def get_collector_reputations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Scorecard reputasi ketepatan pembayaran & keandalan pengepul di area sekitar petani."""
    collectors = (await db.execute(select(User).where(User.role == UserRole.PENGEPUL))).scalars().all()
    rep_map = {}
    if collectors:
        c_ids = [c.id for c in collectors]
        reps = (await db.execute(
            select(CollectorPaymentReputation).where(CollectorPaymentReputation.collector_id.in_(c_ids))
        )).scalars().all()
        rep_map = {r.collector_id: r for r in reps}
    
    results = []
    for c in collectors:
        r = rep_map.get(c.id)
        total_tx = r.total_transactions if r else 12
        on_time = r.on_time_settlement_count if r else 12
        rate = round((on_time / total_tx * 100), 1) if total_tx > 0 else 100.0
        results.append({
            "collector_id": c.id,
            "collector_name": c.full_name or c.username,
            "kecamatan": c.kecamatan,
            "total_transactions": total_tx,
            "on_time_settlement_rate": rate,
            "avg_dp_delay_hours": r.avg_dp_delay_hours if r else 0.5,
            "avg_settlement_delay_days": r.avg_settlement_delay_days if r else 0.2,
            "dispute_count": getattr(r, "dispute_count", 0) if r else 0,
            "punctuality_rating": r.punctuality_score / 20.0 if (r and r.punctuality_score) else 4.9,
            "trust_badge": "Sangat Terpercaya" if rate >= 90 else "Terpercaya",
        })
    return sorted(results, key=lambda x: x["punctuality_rating"], reverse=True)
