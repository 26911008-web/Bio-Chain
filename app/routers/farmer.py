"""Router: Petani (🌾) — Endpoints khusus petani.

Desain: ultra-simpel, setiap endpoint hanya memerlukan data minimal.
"""

from typing import Annotated
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role, get_current_user
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, Mill
from ..models.ledger import BiocharLedgerEntry, CustodyEvent, CustodyStage
from ..engines.incentive import calculate_incentive, DeliveryEvent, next_tier_xp
from ..models.trade import StockListing, Bid, CollectorPaymentReputation, CollectorRating
from ..models.circular import BiocharRequest, BiocharQualityEvaluation, BiocharCircularRequest
from ..models.trade import StockListing, Bid, CollectorPaymentReputation, CollectorRating, ListingStatus, DeliveryScheme
from ..services import trade
from ..services.biomass import get_biomass
from ..services.qr_sign import new_qr_code
from ..services.custody import find_replay, trusted_device_time, wallet_balance
from ..services.notifications import record_notification
from ..security.url import EvidenceUrl

router = APIRouter()


class HarvestReportRequest(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=200000,
                               description="Jumlah biomassa dalam kg")
    commodity: str = Field("sekam_padi", max_length=24, description="Kode komoditas (GET /api/v1/biomass)")
    mill_id: int | None = None
    collector_id: int | None = Field(None, description="Pengepul tujuan yang dipilih petani")
    delivery_scheme: str | None = Field(None, description="jemput | antar")
    photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    # Opsional: taksiran petani. Tidak memengaruhi harga — QC pengepul yang menentukan; dipakai untuk umpan balik
    moisture_est: float | None = Field(None, ge=0, le=60, description="Taksiran kadar air (%), boleh kosong")
    grade_est: str | None = Field(None, pattern="^[ABCD]$", description="Taksiran grade A-D, boleh kosong")
    # Dual-Mode Workflow & Logistics
    transaction_mode: str | None = Field("DIRECT", description="DIRECT | BIDDING")
    logistics_mode: str | None = Field("PICKUP", description="PICKUP | DELIVER_SELF")
    floor_price: float | None = Field(None, ge=0, description="Harga dasar/minimum lelang (Rp/kg)")
    # Opsi Kebutuhan Biochar Sirkular Petani
    biochar_request_kg: float | None = Field(None, ge=0, description="Kebutuhan biochar sirkular petani (kg)")
    biochar_land_area_ha: float | None = Field(None, ge=0, description="Luas lahan aplikasi biochar (ha)")
    biochar_delivery_point: str | None = Field("Lahan Petani", max_length=200)
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = Field(None, description="Waktu lapor di perangkat (bisa saat offline)")


class HarvestResponse(BaseModel):
    id: int
    uuid: str
    quantity_kg: float
    status: str
    qr_code: str | None = None
    message: str
    replayed: bool = False
    commodity: str = "sekam_padi"
    transaction_mode: str = "DIRECT"
    logistics_mode: str = "PICKUP"
    listing_id: int | None = None
    biochar_request_id: int | None = None


@router.post("/harvest", response_model=HarvestResponse, status_code=201)
async def report_harvest(
    req: HarvestReportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Laporkan stok biomassa yang siap dijual — Dual-Mode (Langsung ke Pengepul / Lelang Bebas)
    serta integrasi pemesanan biochar sirkular untuk pembenah tanah sawah.

    Idempoten: laporan yang dikirim ulang dari antrean offline dengan client_event_id sama
    mengembalikan harvest yang sudah dibuat, bukan membuat duplikat.
    """
    uid = user.id          # simpan: objek user kedaluwarsa bila transaksi di-rollback di bawah
    replay = await find_replay(db, req.client_event_id)
    if replay is not None:
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.farmer_id != user.id:
            raise HTTPException(409, "client_event_id sudah dipakai.")
        status_val = h.status.value if hasattr(h.status, "value") else str(h.status)
        return HarvestResponse(id=h.id, uuid=h.uuid, quantity_kg=h.quantity_kg, status=status_val,
                               qr_code=h.qr_code, message="ℹ️ Laporan ini sudah tercatat sebelumnya.",
                               replayed=True, commodity=h.commodity or "sekam_padi",
                               transaction_mode=h.transaction_mode or "DIRECT",
                               logistics_mode=h.logistics_mode or "PICKUP",
                               listing_id=h.listing_id)

    # Fallback aman bila mill_id tidak diisi atau tidak terdaftar di DB
    if req.mill_id:
        mill_exists = (await db.execute(select(Mill.id).where(Mill.id == req.mill_id))).first()
        if not mill_exists:
            req.mill_id = (await db.execute(select(Mill.id).where(Mill.is_active.is_(True)).limit(1))).scalar_one_or_none()
    else:
        req.mill_id = (await db.execute(select(Mill.id).where(Mill.is_active.is_(True)).limit(1))).scalar_one_or_none()

    # Validasi aman untuk collector_id
    if req.collector_id:
        col_exists = (await db.execute(select(User.id).where(User.id == req.collector_id, User.role == UserRole.PENGEPUL))).first()
        if not col_exists:
            req.collector_id = None
    else:
        req.collector_id = None

    biomass_item = await get_biomass(db, req.commodity or "sekam_padi")
    com_code = biomass_item.code

    h_uuid = str(uuid.uuid4())
    qr = new_qr_code(h_uuid)

    tx_mode = "BIDDING" if (req.transaction_mode and req.transaction_mode.upper() == "BIDDING") else "DIRECT"
    log_mode = "DELIVER_SELF" if (req.logistics_mode and req.logistics_mode.upper() == "DELIVER_SELF") or req.delivery_scheme == "antar" else "PICKUP"

    harvest = Harvest(
        uuid=h_uuid,
        farmer_id=user.id,
        mill_id=req.mill_id,
        collector_id=req.collector_id,
        delivery_scheme="antar" if log_mode == "DELIVER_SELF" else "jemput",
        quantity_kg=req.quantity_kg,
        commodity=com_code,
        status=HarvestStatus.REPORTED,
        qr_code=qr,
        origin_qr_code=qr,
        photo_url=req.photo_url,
        farmer_moisture_est=req.moisture_est,
        farmer_grade_est=req.grade_est,
        farmer_claimed_qty=req.quantity_kg,
        transaction_mode=tx_mode,
        logistics_mode=log_mode,
        reported_at=trusted_device_time(req.client_recorded_at)[0],
    )
    db.add(harvest)
    await db.flush()

    listing_obj = None
    if tx_mode == "BIDDING":
        listing_obj = StockListing(
            farmer_id=user.id,
            mill_id=req.mill_id,
            quantity_kg=req.quantity_kg,
            remaining_kg=req.quantity_kg,
            commodity=com_code,
            moisture_pct=req.moisture_est,
            grade_estimate=req.grade_est,
            allow_jemput=(log_mode == "PICKUP"),
            allow_antar=(log_mode == "DELIVER_SELF"),
            ask_price_jemput=req.floor_price,
            ask_price_antar=req.floor_price,
            floor_price=req.floor_price,
            transaction_mode="BIDDING",
            auction_status="OPEN",
            logistics_mode=log_mode,
            farmer_claimed_qty=req.quantity_kg,
            origin_qr_code=qr,
            status=ListingStatus.OPEN,
        )
        db.add(listing_obj)
        await db.flush()
        harvest.listing_id = listing_obj.id

    bcr_obj = None
    if req.biochar_request_kg and req.biochar_request_kg > 0:
        bcr_code = f"BCR-{uuid.uuid4().hex[:8].upper()}"
        col_target_id = req.collector_id
        if not col_target_id:
            first_col = (await db.execute(select(User.id).where(User.role == UserRole.PENGEPUL).limit(1))).scalar_one_or_none()
            col_target_id = first_col or user.id
        bcr_obj = BiocharCircularRequest(
            request_code=bcr_code,
            farmer_id=user.id,
            collector_id=col_target_id,
            harvest_id=harvest.id,
            listing_id=listing_obj.id if listing_obj else None,
            requested_kg=req.biochar_request_kg,
            allocated_kg=0.0,
            land_area_ha=req.biochar_land_area_ha,
            delivery_point=req.biochar_delivery_point or "Lahan Petani",
            status="REQUESTED",
            notes=f"Dipesan bersamaan dengan laporan biomassa #{harvest.id}"
        )
        db.add(bcr_obj)
        harvest.biochar_backhaul_requested = True
        harvest.biochar_backhaul_kg = req.biochar_request_kg

    db.add(CustodyEvent(harvest_id=harvest.id, stage=CustodyStage.FARMER_REPORT.value, from_status=None,
                        to_status=HarvestStatus.REPORTED.value, weight_kg=req.quantity_kg, actor_id=user.id,
                        actor_role=UserRole.PETANI.value, client_event_id=req.client_event_id,
                        client_recorded_at=req.client_recorded_at, note=f"Lapor {tx_mode} - {log_mode}"))
    try:
        await db.flush()
    except IntegrityError:
        # Spam-click: kiriman kembar dengan client_event_id sama sudah menang lebih dulu.
        await db.rollback()
        replay = await find_replay(db, req.client_event_id)
        if replay is None:
            raise
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.farmer_id != uid:
            raise HTTPException(409, "client_event_id sudah dipakai.")
        status_val = h.status.value if hasattr(h.status, "value") else str(h.status)
        return HarvestResponse(id=h.id, uuid=h.uuid, quantity_kg=h.quantity_kg, status=status_val,
                               qr_code=h.qr_code, message="ℹ️ Laporan ini sudah tercatat sebelumnya.",
                               replayed=True, commodity=h.commodity or "sekam_padi",
                               transaction_mode=h.transaction_mode or "DIRECT",
                               logistics_mode=h.logistics_mode or "PICKUP",
                               listing_id=h.listing_id)

    status_str = harvest.status.value if hasattr(harvest.status, 'value') else str(harvest.status)
    mode_text = "Bursa Lelang" if tx_mode == "BIDDING" else "Jalur Langsung"
    biochar_msg = f" + Request biochar {req.biochar_request_kg} kg dicatat" if bcr_obj else ""

    # Catat notifikasi perubahan transaksi untuk Petani & Pengepul
    await record_notification(
        db,
        event_type="HARVEST_REPORTED",
        title=f"🌾 Laporan Stok Biomassa #{harvest.id} Terdaftar",
        message=f"Pasokan {int(harvest.quantity_kg)} kg {harvest.commodity.replace('_', ' ').title()} berhasil didaftarkan via {mode_text}. Menunggu verifikasi kuantitas & harga.",
        status_group="PENDING_ACTION",
        target_role="petani",
        user_id=user.id,
        harvest_id=harvest.id,
        transaction_code=qr,
        actor_role="petani",
        actor_name=user.full_name or user.username,
        action_type="trace",
        action_payload=qr,
    )
    await record_notification(
        db,
        event_type="NEW_OFFER_TO_VERIFY",
        title=f"📦 Penawaran Baru Masuk: {int(harvest.quantity_kg)} kg {harvest.commodity.replace('_', ' ').title()}",
        message=f"Petani {user.full_name or user.username} mendaftarkan pasokan ({mode_text}). Mohon lakukan verifikasi timbangan dan harga beli.",
        status_group="PENDING_ACTION",
        target_role="pengepul",
        user_id=req.collector_id,
        harvest_id=harvest.id,
        transaction_code=qr,
        actor_role="petani",
        actor_name=user.full_name or user.username,
        action_type="action",
        action_payload="verify_offer",
    )

    return HarvestResponse(
        id=harvest.id,
        uuid=harvest.uuid,
        quantity_kg=harvest.quantity_kg,
        status=status_str,
        qr_code=qr,
        commodity=harvest.commodity or "sekam_padi",
        transaction_mode=tx_mode,
        logistics_mode=log_mode,
        listing_id=listing_obj.id if listing_obj else None,
        biochar_request_id=bcr_obj.id if bcr_obj else None,
        message=f"✅ {req.quantity_kg:g} kg berhasil dilaporkan via {mode_text} ({log_mode}){biochar_msg}!",
    )


@router.get("/payments")
async def my_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Bukti bayar dari pengepul atas biomassa saya (F8): bruto, potongan pajak, bersih, metode, nomor kuitansi."""
    from ..models.compliance import FarmerPayment, FarmerDownPayment
    from ..services.payments import payment_dict
    rows = (await db.execute(select(FarmerPayment).where(FarmerPayment.farmer_id == user.id)
                             .order_by(FarmerPayment.id.desc()).limit(100))).scalars().all()
    h_ids = list({p.harvest_id for p in rows if p.harvest_id})
    h_map = {}
    if h_ids:
        h_res = await db.execute(select(Harvest).where(Harvest.id.in_(h_ids)))
        h_map = {h.id: h for h in h_res.scalars().all()}
    
    col_ids = list({p.collector_id for p in rows if p.collector_id})
    col_map = {}
    if col_ids:
        c_res = await db.execute(select(User).where(User.id.in_(col_ids)))
        col_map = {c.id: (c.full_name or c.username) for c in c_res.scalars().all()}

    dps = {}
    if h_ids:
        dp_res = await db.execute(select(FarmerDownPayment).where(FarmerDownPayment.harvest_id.in_(h_ids)))
        dps = {d.harvest_id: d for d in dp_res.scalars().all()}

    result = []
    for p in rows:
        d = payment_dict(p)
        h = h_map.get(p.harvest_id)
        dp = dps.get(p.harvest_id)
        d["commodity"] = h.commodity if h else "sekam_padi"
        d["commodity_name"] = (h.commodity or "sekam_padi").replace("_", " ").title() if h else "Sekam Padi"
        d["origin_qr_code"] = (getattr(h, "origin_qr_code", None) or getattr(h, "qr_code", None) or f"WR-HV-{p.harvest_id:04d}") if h else f"WR-HV-{p.harvest_id:04d}"
        d["quantity_kg"] = (h.verified_kg or h.quantity_kg) if h else 0
        d["collector_name"] = col_map.get(p.collector_id, "Pengepul")
        d["dp_receipt_code"] = dp.receipt_code if dp else None
        d["dp_status"] = dp.status if dp else None
        d["is_paid"] = True
        result.append(d)
    return result


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
    res = await farmer_quality_feedback(db, user.id, min(max(months, 1), 24))

    harvests = (await db.execute(
        select(Harvest)
        .where(Harvest.farmer_id == user.id)
        .order_by(Harvest.id.desc())
        .limit(100)
    )).scalars().all()

    items = []
    for h in harvests:
        claimed = h.farmer_claimed_qty or h.quantity_kg
        actual = h.verified_kg or h.actual_weighed_qty or claimed
        dev_kg = round(actual - claimed, 2)
        dev_pct = round((dev_kg / claimed * 100), 1) if claimed > 0 else 0.0

        tips = []
        if (h.moisture or 0) > 18:
            tips.append(f"Kadar air {h.moisture}% cukup tinggi. Jemur di atas terpal kering selama 4-6 jam.")
        if (h.contamination or 0) > 2:
            tips.append(f"Kontaminan {h.contamination}% (batu/tanah). Gunakan alas saung bersih.")
        if not tips:
            tips.append("Mutu biomassa prima memenuhi standar industri.")

        items.append({
            "harvest_id": h.id,
            "commodity": h.commodity or "sekam_padi",
            "reported_at": h.created_at.isoformat() if hasattr(h, "created_at") and h.created_at else None,
            "claimed_kg": claimed,
            "actual_weighed_kg": actual,
            "deviation_kg": dev_kg,
            "deviation_pct": dev_pct,
            "qc_status": h.qc_status or ("PASS" if h.status != HarvestStatus.REJECTED else "REJECT"),
            "rejection_reason": h.rejected_reason or h.qc_rejection_reason,
            "quality_grade": h.grade.value if hasattr(h.grade, "value") else str(h.grade or "A"),
            "actionable_tips": " ".join(tips),
        })

    res["farmer_id"] = user.id
    res["total_deliveries"] = len(items)
    res["items"] = items
    return res


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
@router.post("/biochar/redemptions", status_code=201)
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


@router.get("/collectors")
async def list_collectors(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI, UserRole.PENGEPUL))],
    commodity: str | None = None,
):
    """Daftar pengepul mitra aktif yang dapat dipilih oleh petani untuk penyerahan biomassa."""
    query = (
        select(User, CollectorPaymentReputation)
        .outerjoin(CollectorPaymentReputation, CollectorPaymentReputation.collector_id == User.id)
        .where(User.role == UserRole.PENGEPUL, User.is_active.is_(True))
    )
    rows = (await db.execute(query)).all()

    ratings_q = (
        select(CollectorRating.collector_id, func.avg(CollectorRating.overall_rating))
        .group_by(CollectorRating.collector_id)
    )
    ratings_map = dict((await db.execute(ratings_q)).all())

    collectors = []
    for u, rep in rows:
        spec = u.specialization_commodity or ""
        if not spec:
            u_low = f"{(u.username or '')} {(u.full_name or '')}".lower()
            if "sekam" in u_low:
                spec = "sekam_padi"
            elif "jagung" in u_low:
                spec = "tongkol_jagung"
            elif "tebu" in u_low:
                spec = "ampas_tebu"
            elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low:
                spec = "serbuk_sengon"
            elif "tempurung" in u_low or "cangkang" in u_low:
                spec = "tempurung_kelapa"
            elif "sabut" in u_low or "coir" in u_low:
                spec = "sabut_kelapa"
            elif "karet" in u_low:
                spec = "serbuk_karet"

        punctuality = rep.punctuality_score if rep and rep.punctuality_score is not None else 95.0
        tier = rep.rating_tier if rep and rep.rating_tier else "EXCELLENT"
        avg_star = round(float(ratings_map.get(u.id, 5.0)), 1)
        is_match = bool(commodity and spec and spec.lower() == commodity.lower())

        collectors.append({
            "id": u.id,
            "name": u.full_name or u.username,
            "username": u.username,
            "phone": u.phone,
            "kecamatan": u.kecamatan or "Sleman",
            "kabupaten": u.kabupaten or "Sleman",
            "specialization_commodity": spec,
            "punctuality_score": punctuality,
            "rating_tier": tier,
            "rating_avg": avg_star,
            "is_specialist_match": is_match,
        })

    collectors.sort(key=lambda c: (
        0 if c["is_specialist_match"] else (1 if not c["specialization_commodity"] else 2),
        -c["punctuality_score"],
        c["name"]
    ))
    return collectors


@router.get("/wallet")
async def biochar_wallet(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
    limit: int = 20,
):
    """Saldo biochar petani (hak dari biomassa yang sudah diolah) + riwayat ledger."""
    entries = (await db.execute(
        select(BiocharLedgerEntry).where(BiocharLedgerEntry.farmer_id == user.id)
        .order_by(BiocharLedgerEntry.id.desc()).limit(min(max(limit, 1), 100))
    )).scalars().all()
    from ..services.circular import pending_kg
    from ..models.circular import BiocharRedemption
    balance = await wallet_balance(db, user.id)
    held = await pending_kg(db, user.id)

    # Hitung biochar yang sudah diserahkan / diambil
    taken_res = (await db.execute(
        select(func.coalesce(func.sum(BiocharRedemption.kg), 0.0))
        .where(BiocharRedemption.farmer_id == user.id, BiocharRedemption.status == "diserahkan")
    )).scalar()
    taken_kg = round(float(taken_res or 0.0), 2)
    if taken_kg == 0.0:
        neg_res = (await db.execute(
            select(func.coalesce(func.sum(func.abs(BiocharLedgerEntry.amount_kg)), 0.0))
            .where(BiocharLedgerEntry.farmer_id == user.id, BiocharLedgerEntry.amount_kg < 0)
        )).scalar()
        taken_kg = round(float(neg_res or 0.0), 2)

    pos_res = (await db.execute(
        select(func.coalesce(func.sum(BiocharLedgerEntry.amount_kg), 0.0))
        .where(BiocharLedgerEntry.farmer_id == user.id, BiocharLedgerEntry.amount_kg > 0)
    )).scalar()
    total_earned_kg = round(float(pos_res or 0.0), 2)
    available_kg = round(max(0.0, balance - held), 2)

    return {
        "farmer_id": user.id,
        "balance_kg": balance,
        "held_kg": held,                                   # sedang diajukan, belum diserahkan
        "available_kg": available_kg,                      # potensi yang bisa diambil saat ini
        "taken_kg": taken_kg,                              # yang sudah diambil
        "total_earned_kg": total_earned_kg,
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

    bid_ids = [h.bid_id for h in harvests if h.bid_id]
    bid_map = {}
    if bid_ids:
        b_res = await db.execute(select(Bid).where(Bid.id.in_(bid_ids)))
        bid_map = {b.id: b for b in b_res.scalars().all()}

    items = []
    for h in harvests:
        b = bid_map.get(h.bid_id) if h.bid_id else None
        p_date = b.pickup_date if b and b.pickup_date else (h.verified_at.strftime("%Y-%m-%d") if h.verified_at else None)

        if h.status == HarvestStatus.VERIFIED:
            lbl = "Terverifikasi Pengepul"
        elif h.status == HarvestStatus.REPORTED:
            lbl = "Menunggu Verifikasi Pengepul"
        elif h.status == HarvestStatus.COLLECTED:
            lbl = "Diangkut Pengepul"
        elif h.status in (HarvestStatus.DELIVERED, HarvestStatus.CONVERTED):
            lbl = "Diterima Gudang/Pabrik"
        elif h.status == HarvestStatus.REJECTED:
            lbl = "Ditolak QC"
        else:
            lbl = str(h.status)

        items.append({
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "commodity": h.commodity or "sekam_padi",
            "status": h.status.value if hasattr(h.status, 'value') else str(h.status),
            "status_label": lbl,
            "is_active": h.status in (HarvestStatus.REPORTED, HarvestStatus.VERIFIED),
            "grade": (h.grade.value if hasattr(h.grade, 'value') else str(h.grade)) if h.grade else None,
            "qr_code": h.qr_code,
            "origin_qr_code": h.origin_qr_code or h.qr_code,
            "wr_code": h.origin_qr_code or h.qr_code or f"WR-HV-{h.id:04d}",
            "listing_id": h.listing_id,
            "batch_ref": f"WR-LST-{h.listing_id:04d}" if h.listing_id else f"WR-HV-{h.id:04d}",
            "verified_kg": h.verified_kg,
            "received_kg": h.received_kg,
            "total_price": h.total_price,
            "delivery_scheme": h.delivery_scheme or "jemput",
            "farmer_moisture_est": h.farmer_moisture_est,
            "farmer_grade_est": h.farmer_grade_est,
            "photo_url": h.photo_url,
            "biochar_backhaul_requested": h.biochar_backhaul_requested,
            "biochar_backhaul_kg": h.biochar_backhaul_kg,
            "payment_status": h.payment_status or "UNPAID",
            "pickup_date": p_date,
            "verified_at": h.verified_at.isoformat() if h.verified_at else None,
            "collected_at": h.collected_at.isoformat() if h.collected_at else None,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
        })
    return items


@router.get("/incentive")
async def get_incentive_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Lihat status XP dan tier insentif petani."""
    # Hitung total harvests & rentang aktif untuk average per bulan
    result = await db.execute(
        select(func.count(Harvest.id), func.sum(Harvest.quantity_kg), func.min(Harvest.reported_at))
        .where(Harvest.farmer_id == user.id)
        .where(Harvest.status != HarvestStatus.REJECTED)
    )
    row = result.one()
    total_harvests = row[0] or 0
    total_kg = row[1] or 0
    min_date = row[2]

    now_utc = datetime.now(timezone.utc)
    if min_date:
        # SQLite/Postgres timezone handling
        if min_date.tzinfo is None:
            min_date = min_date.replace(tzinfo=timezone.utc)
        days = max(1, (now_utc - min_date).days)
        span_months = max(1.0, round(days / 30.4375, 1))
    else:
        span_months = 1.0

    avg_harvests_per_month = round(total_harvests / span_months, 1)
    avg_ton_per_month = round((total_kg / 1000.0) / span_months, 2)

    return {
        "xp_total": user.xp_total,
        "tier": (user.incentive_tier.value if hasattr(user.incentive_tier, 'value') else str(user.incentive_tier)) if user.incentive_tier else "pemula",
        "total_harvests": total_harvests,
        "total_kg": round(total_kg, 1),
        "avg_harvests_per_month": avg_harvests_per_month,
        "avg_ton_per_month": avg_ton_per_month,
        "active_months": span_months,
        "next_tier_xp": next_tier_xp(user.xp_total or 0),
    }


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
    """Petani memesan muatan balik biochar untuk diaplikasikan ke sawah saat armada menjemput biomassa."""
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
    """Daftar riwayat dan status muatan balik biochar milik petani."""
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


# -----------------------------------------------------------------------------
# Evaluasi Mutu Biochar & Performa Pengepul oleh Petani
# -----------------------------------------------------------------------------
class BiocharEvaluationCreate(BaseModel):
    biochar_request_id: int | None = None
    collector_id: int | None = None
    batch_code: str | None = Field(None, max_length=50)
    grain_size_mesh_rating: int = Field(5, ge=1, le=5, description="Kesesuaian ukuran butir/mesh (1-5)")
    pyrolysis_maturity_rating: int = Field(5, ge=1, le=5, description="Tingkat kematangan pirolisis/karbonisasi (1-5)")
    moisture_rating: int = Field(5, ge=1, le=5, description="Kekeringan / kelembapan biochar (1-5)")
    soil_impact_rating: int = Field(5, ge=1, le=5, description="Dampak perbaikan struktur tanah & tanaman (1-5)")
    review_notes: str | None = Field(None, max_length=1000)


@router.post("/biochar-evaluations", status_code=201)
async def submit_biochar_evaluation(
    req: BiocharEvaluationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani mengisi evaluasi kualitas biochar yang diterima (mesh, kematangan, kelembapan, dampak tanah)."""
    overall = round((req.grain_size_mesh_rating + req.pyrolysis_maturity_rating + req.moisture_rating + req.soil_impact_rating) / 4.0, 2)
    eval_record = BiocharQualityEvaluation(
        farmer_id=user.id,
        biochar_request_id=req.biochar_request_id,
        collector_id=req.collector_id,
        batch_code=req.batch_code,
        grain_size_mesh_rating=req.grain_size_mesh_rating,
        pyrolysis_maturity_rating=req.pyrolysis_maturity_rating,
        moisture_rating=req.moisture_rating,
        soil_impact_rating=req.soil_impact_rating,
        overall_score=overall,
        review_notes=req.review_notes,
    )
    db.add(eval_record)
    await db.flush()
    return {
        "success": True,
        "id": eval_record.id,
        "overall_score": overall,
        "evaluation": {
            "id": eval_record.id,
            "overall_score": overall,
            "batch_code": eval_record.batch_code,
            "review_notes": eval_record.review_notes,
        },
        "message": f"✅ Evaluasi mutu biochar berhasil dicatat (Skor: {overall}/5.0). Umpan balik Anda membantu kontrol mutu pabrik & pengepul."
    }


@router.get("/biochar-evaluations")
async def list_biochar_evaluations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Daftar riwayat evaluasi mutu biochar yang diajukan petani."""
    rows = (await db.execute(
        select(BiocharQualityEvaluation)
        .where(BiocharQualityEvaluation.farmer_id == user.id)
        .order_by(BiocharQualityEvaluation.id.desc())
    )).scalars().all()
    return [
        {
            "id": r.id,
            "biochar_request_id": r.biochar_request_id,
            "collector_id": r.collector_id,
            "batch_code": r.batch_code,
            "grain_size_mesh_rating": r.grain_size_mesh_rating,
            "pyrolysis_maturity_rating": r.pyrolysis_maturity_rating,
            "moisture_rating": r.moisture_rating,
            "soil_impact_rating": r.soil_impact_rating,
            "overall_score": r.overall_score,
            "review_notes": r.review_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class CollectorRatingCreate(BaseModel):
    collector_id: int
    harvest_id: int | None = None
    punctuality_rating: int = Field(5, ge=1, le=5, description="Ketepatan waktu penjemputan/penerimaan (1-5)")
    payment_rating: int = Field(5, ge=1, le=5, description="Ketepatan & kelancaran pembayaran DP/pelunasan (1-5)")
    review_text: str | None = Field(None, max_length=1000)


@router.post("/collector-ratings", status_code=201)
async def submit_collector_rating(
    req: CollectorRatingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani memberikan rating performa ketepatan waktu & kelancaran pembayaran pengepul."""
    collector = (await db.execute(select(User).where(User.id == req.collector_id, User.role == UserRole.PENGEPUL))).scalar_one_or_none()
    if not collector:
        raise HTTPException(404, "Pengepul tidak ditemukan.")

    overall = round((req.punctuality_rating + req.payment_rating) / 2.0, 1)
    rating = CollectorRating(
        farmer_id=user.id,
        collector_id=req.collector_id,
        harvest_id=req.harvest_id,
        punctuality_rating=req.punctuality_rating,
        payment_rating=req.payment_rating,
        overall_rating=overall,
        review_text=req.review_text,
    )
    db.add(rating)
    await db.flush()

    # Perbarui scorecard reputasi pengepul
    rep = (await db.execute(
        select(CollectorPaymentReputation).where(CollectorPaymentReputation.collector_id == req.collector_id)
    )).scalar_one_or_none()
    if not rep:
        rep = CollectorPaymentReputation(
            collector_id=req.collector_id,
            total_transactions=1,
            on_time_settlement_count=1,
            punctuality_score=overall * 20.0,
            rating_tier="EXCELLENT" if overall >= 4.5 else ("GOOD" if overall >= 3.5 else "FAIR"),
        )
        db.add(rep)
    else:
        rep.total_transactions += 1
        # Bobot moving average
        current_score = rep.punctuality_score or 90.0
        new_score = round((current_score * 0.8) + (overall * 20.0 * 0.2), 1)
        rep.punctuality_score = new_score
        rep.rating_tier = "EXCELLENT" if new_score >= 85 else ("GOOD" if new_score >= 70 else "FAIR")
    await db.flush()

    return {
        "success": True,
        "id": rating.id,
        "overall_rating": overall,
        "rating": {
            "id": rating.id,
            "overall_rating": overall,
            "punctuality_rating": rating.punctuality_rating,
            "payment_rating": rating.payment_rating,
            "review_text": rating.review_text,
        },
        "message": f"⭐ Terima kasih! Rating {overall}/5.0 berhasil disimpan untuk {collector.full_name}."
    }


@router.get("/collector-ratings")
async def list_collector_ratings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Daftar riwayat rating performa pengepul yang telah dikirim oleh petani."""
    rows = (await db.execute(
        select(CollectorRating, User)
        .join(User, User.id == CollectorRating.collector_id)
        .where(CollectorRating.farmer_id == user.id)
        .order_by(CollectorRating.id.desc())
    )).all()
    return [
        {
            "id": r.id,
            "collector_id": r.collector_id,
            "collector_name": c.full_name or c.username,
            "harvest_id": r.harvest_id,
            "punctuality_rating": r.punctuality_rating,
            "payment_rating": r.payment_rating,
            "overall_rating": r.overall_rating,
            "review_text": r.review_text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, c in rows
    ]


# -----------------------------------------------------------------------------
# FASE 2: Konfirmasi Jadwal & Feedback QC Petani
# -----------------------------------------------------------------------------


class ScheduleConfirmRequest(BaseModel):
    bid_id: int
    decision: str = Field(..., pattern="^(APPROVE|RESCHEDULE)$", description="'APPROVE' | 'RESCHEDULE'")
    reschedule_note: str | None = Field(None, max_length=500, description="Alasan jika minta jadwal ulang")


@router.post("/schedule/confirm")
async def confirm_pickup_schedule(
    req: ScheduleConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani mengonfirmasi (Approve / Reschedule) rencana jadwal penjemputan dari pengepul."""
    bid = (await db.execute(
        select(Bid).where(Bid.id == req.bid_id, Bid.farmer_id == user.id).with_for_update()
    )).scalar_one_or_none()
    if not bid:
        # Fallback coba via listing_id
        bid = (await db.execute(
            select(Bid).join(StockListing, StockListing.id == Bid.listing_id)
            .where(Bid.id == req.bid_id, StockListing.farmer_id == user.id).with_for_update()
        )).scalar_one_or_none()

    if not bid:
        raise HTTPException(404, "Data penawaran/jadwal tidak ditemukan.")

    if req.decision == "APPROVE":
        bid.farmer_schedule_status = "APPROVED"
        bid.farmer_schedule_note = req.reschedule_note or "Petani menyetujui jadwal penjemputan resmi."
        msg = "✅ Jadwal penjemputan berhasil dikonfirmasi resmi. Pengepul siap berangkat sesuai jadwal."
    else:
        bid.farmer_schedule_status = "RESCHEDULE_REQUESTED"
        bid.farmer_schedule_note = req.reschedule_note or "Petani meminta penyesuaian jadwal penjemputan."
        msg = "📅 Permintaan jadwal ulang berhasil dikirimkan ke pengepul."

    await db.flush()
    return {
        "success": True,
        "bid_id": bid.id,
        "farmer_schedule_status": bid.farmer_schedule_status,
        "note": bid.farmer_schedule_note,
        "message": msg
    }


