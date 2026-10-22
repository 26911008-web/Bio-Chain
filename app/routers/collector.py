"""Router: Pengepul (📦) — Endpoints khusus pengepul/collector."""

from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, QualityGrade
from ..models.ledger import CustodyStage
from ..engines.quality import FeedstockSample, farmgate_price, score_sample
from ..models.trade import Bid, BidStatus, StockListing
from ..models.factory_ops import DeliveryRequest
from ..models.route import Route, RouteStatus, RouteStop
from ..services import factory_ops, trade
from ..services.qr_sign import new_qr_code
from ..services.custody import find_replay, load_harvest, pct_diff, transition

from ..security.url import EvidenceUrl
from ..services.privacy import PROXY_PHONE_PREFIX, has_real_phone, mask_phone

router = APIRouter()


class VerifyHarvestRequest(BaseModel):
    harvest_id: int
    weighed_kg: float = Field(..., gt=0, le=50000, description="Hasil timbangan pengepul (dasar harga)")
    moisture: float = Field(..., ge=0, le=60)
    # F9: hanya kadar air (moisture meter) wajib di lapangan; abu/VM/FC diisi bila ada uji lab/NIR
    ash: float | None = Field(None, ge=0, le=40)
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = None
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000, description="Bukti foto serah-terima (opsional)")
    beli_untuk_dikeringkan: bool = Field(
        False, description="Mutu di bawah batas tolak tetap dibeli (harga basis kering) karena pengepul akan "
                           "mengeringkan/menyortir sendiri; risiko jamur ditanggung pengepul dan tercatat.")


class CancelPurchaseRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class PriceQuoteRequest(BaseModel):
    weighed_kg: float = Field(..., gt=0, le=50000)
    moisture: float = Field(..., ge=0, le=60)
    contamination: float = Field(0, ge=0, le=50)
    ash: float | None = Field(None, ge=0, le=40, description="Opsional - bila tidak diukur dipakai acuan menu Parameter")
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    harvest_id: int | None = Field(None, description="Isi untuk panen hasil lelang (harga kontrak)")


class RejectHarvestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    harvest_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    category: str = Field("lainnya", pattern="^(basah|berjamur|kontaminan|selisih_berat|stok_tidak_ada|lainnya)$",
                          description="Penyebab terstruktur → defect rate di laporan bulanan petani")
    client_event_id: str | None = Field(None, max_length=64)
    client_recorded_at: datetime | None = None


@router.get("/available-harvests")
async def list_available_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    kecamatan: str | None = None,
):
    """Lihat laporan sekam dari petani yang siap diverifikasi/diambil."""
    query = select(Harvest).where(Harvest.status == HarvestStatus.REPORTED,
                                  Harvest.collector_id.is_(None) | (Harvest.collector_id == user.id))
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

    # Lot hasil lelang milik saya + status DP → tombol DP langsung di antrean (mengikat kesepakatan)
    from ..models.compliance import FarmerDownPayment
    own_ids = [h.id for h in harvests if h.collector_id == user.id]
    dp_map = {d.harvest_id: d for d in (await db.execute(
        select(FarmerDownPayment).where(FarmerDownPayment.harvest_id.in_(own_ids)))).scalars()} if own_ids else {}
    results_list = []
    for h in harvests:
        farmer = farmers_map.get(h.farmer_id)
        dp = dp_map.get(h.id)
        results_list.append({
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "farmer_id": h.farmer_id,
            "farmer_name": farmer.full_name if farmer else f"Petani #{h.farmer_id}",
            # F12 minimisasi: nomor disamarkan di daftar lintas-pengguna; nomor lengkap via /harvests/{id}/contact
            "farmer_phone": mask_phone(farmer.phone) if farmer else None,
            "farmer_without_phone": bool(farmer and not has_real_phone(farmer.phone)),
            "kecamatan": farmer.kecamatan if farmer else None,
            "qr_code": h.qr_code,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
            "farmer_moisture_est": h.farmer_moisture_est, "farmer_grade_est": h.farmer_grade_est,
            "is_auction": h.listing_id is not None and h.collector_id == user.id,
            "agreed_price_per_kg": h.agreed_price_per_kg if h.collector_id == user.id else None,
            "dp": {"amount_rp": int(dp.amount_rp), "status": dp.status, "receipt_code": dp.receipt_code} if dp else None,
        })
    return results_list


@router.post("/verify")
async def verify_harvest(
    req: VerifyHarvestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Timbang + uji mutu sekam (Engine ②). Harga ke petani dihitung dari timbangan pengepul,
    bukan estimasi petani. Idempoten terhadap client_event_id (aman diulang dari antrean offline)."""
    replay = await find_replay(db, req.client_event_id)
    harvest = await load_harvest(db, req.harvest_id)
    if replay is None and harvest.status != HarvestStatus.REPORTED:
        raise HTTPException(409, f"Harvest sudah berstatus '{harvest.status.value}' — sudah diproses pengepul lain.")
    if harvest.collector_id is not None and harvest.collector_id != user.id:
        raise HTTPException(403, "Harvest ini hasil lelang pengepul lain.")

    quality = score_sample(FeedstockSample(
        moisture=req.moisture, ash=req.ash, volatile_matter=req.volatile_matter, fixed_carbon=req.fixed_carbon,
        contamination=req.contamination, pyrolysis_temp_c=req.pyrolysis_temp_c,
    ))
    estimate_gap = pct_diff(harvest.quantity_kg, req.weighed_kg)
    note = None
    if abs(estimate_gap) > P("sirkular.estimate_tolerance_pct"):
        note = (f"Estimasi petani {harvest.quantity_kg:g} kg vs timbangan {req.weighed_kg:g} kg "
                f"(selisih {estimate_gap:+.1f}%)")
    off_spec = quality["grade"] == "TOLAK"
    if off_spec and replay is None and not req.beli_untuk_dikeringkan:
        raise HTTPException(422, f"Mutu TOLAK (kadar air {req.moisture:g}% / kontaminan {req.contamination:g}%): "
                                 "Tolak agar sekam tetap di petani untuk dikeringkan/disortir, atau centang "
                                 "'beli untuk dikeringkan' (harga basis kering, risiko ditanggung pengepul).")
    price_grade = "C" if off_spec else quality["grade"]     # dibeli di bawah spek: harga basis kering, bukan 0
    if harvest.agreed_price_per_kg:
        # Hasil lelang: harga kontrak; hanya dipotong bila lebih basah dari kadar air yang diiklankan petani
        listing = await db.get(StockListing, harvest.listing_id) if harvest.listing_id else None
        base_price = harvest.agreed_price_per_kg
        pricing = farmgate_price(base_price, req.weighed_kg, req.moisture, req.contamination, price_grade, 1.0,
                                 reference_moisture=listing.moisture_pct if listing and listing.moisture_pct else None,
                                 wetter_only=True, method="basis_kering" if off_spec else None)
    else:
        base_price = P("harga_mutu.base_price_per_kg")
        pricing = farmgate_price(base_price, req.weighed_kg, req.moisture, req.contamination, price_grade,
                                 quality["price_multiplier"], method="basis_kering" if off_spec else None)
    if off_spec:
        note = "; ".join(x for x in (note, "Dibeli di bawah spek untuk dikeringkan/disortir pengepul") if x)
    total_price = pricing["total_price"]
    multiplier = round(pricing["price_per_kg"] / base_price, 4) if base_price else 0.0

    event = await transition(
        db, req.harvest_id, HarvestStatus.REPORTED, HarvestStatus.VERIFIED, user, CustodyStage.COLLECTOR_WEIGH,
        weight_kg=req.weighed_kg, client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at,
        note=note, evidence_photo_url=req.evidence_photo_url, collector_id=user.id, verified_kg=req.weighed_kg, moisture=req.moisture, ash=req.ash,
        volatile_matter=req.volatile_matter, fixed_carbon=req.fixed_carbon, contamination=req.contamination,
        grade=quality["grade"], quality_score=quality["score"], verified_at=datetime.now(timezone.utc),
        base_price_per_kg=base_price, incentive_multiplier=multiplier, total_price=total_price,
    )
    harvest = await load_harvest(db, req.harvest_id)
    return {
        "harvest_id": harvest.id,
        "grade": quality["grade"],
        "score": quality["score"],
        "weighed_kg": harvest.verified_kg,
        "farmer_estimate_kg": harvest.quantity_kg,
        "estimate_gap_pct": round(estimate_gap, 2),
        "total_price": harvest.total_price,
        "quality_detail": quality,
        "replayed": replay is not None,
        "custody_event_id": event.id,
        "verification_code": event.verification_code,
        "price_basis": "harga lelang" if harvest.agreed_price_per_kg else (
            "basis kering" if pricing["method"] == "basis_kering" else "harga dasar × pengali mutu"),
        "pricing": pricing,
        "message": f"Sekam {harvest.verified_kg:g} kg dinilai Grade {quality['grade']} (skor {quality['score']})",
    }


@router.post("/reject")
async def reject_harvest(
    req: RejectHarvestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tolak laporan sekam sebelum diangkut (mis. basah / terkontaminasi)."""
    harvest = await load_harvest(db, req.harvest_id)
    if harvest.collector_id is not None and harvest.collector_id != user.id:
        raise HTTPException(403, "Harvest ini hasil lelang pengepul lain.")
    event = await transition(
        db, req.harvest_id, HarvestStatus.REPORTED, HarvestStatus.REJECTED, user, CustodyStage.COLLECTOR_REJECT,
        client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at, note=req.reason,
        collector_id=user.id, rejected_reason=req.reason, rejected_at=datetime.now(timezone.utc),
        reject_category=req.category,
    )
    return {"harvest_id": req.harvest_id, "status": "rejected", "custody_event_id": event.id}


@router.post("/harvests/{harvest_id}/cancel-purchase")
async def cancel_purchase(
    harvest_id: int,
    body: CancelPurchaseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Batalkan pembelian: lelang yang belum ditimbang (stok petani dikembalikan) atau jemputan truk pabrik
    yang belum dimuat (ongkos jarak kosong dibebankan bila truk sudah berangkat)."""
    from ..services.logistics import cancel_purchase as _cancel
    return await _cancel(db, user, harvest_id, body.reason)


@router.post("/price-quote")
async def price_quote(
    body: PriceQuoteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Simulasi harga di depan petani SEBELUM timbang resmi: cukup berat + kadar air (+ kontaminan).
    Abu/VM/FC opsional - di lapangan biasanya hanya moisture meter yang tersedia."""
    ash = body.ash if body.ash is not None else P("rendemen.ref_ash")
    fc = body.fixed_carbon if body.fixed_carbon is not None else P("harga_mutu.fc_best")
    vm = body.volatile_matter if body.volatile_matter is not None else max(0.0, 100 - ash - fc)
    quality = score_sample(FeedstockSample(moisture=body.moisture, ash=ash, volatile_matter=vm, fixed_carbon=fc,
                                           contamination=body.contamination))
    base, ref, wetter_only, mult = P("harga_mutu.base_price_per_kg"), None, False, quality["price_multiplier"]
    if body.harvest_id:
        h = await load_harvest(db, body.harvest_id)
        if h.collector_id not in (None, user.id):
            raise HTTPException(404, "Harvest tidak ditemukan")
        if h.agreed_price_per_kg:
            listing = await db.get(StockListing, h.listing_id) if h.listing_id else None
            base, wetter_only, mult = h.agreed_price_per_kg, True, 1.0
            ref = listing.moisture_pct if listing and listing.moisture_pct else None
    pricing = farmgate_price(base, body.weighed_kg, body.moisture, body.contamination, quality["grade"], mult,
                             reference_moisture=ref, wetter_only=wetter_only)
    measured = [k for k in ("ash", "volatile_matter", "fixed_carbon") if getattr(body, k) is not None]
    return {"grade": quality["grade"], "score": quality["score"], "pricing": pricing,
            "measured_fields": ["moisture", "contamination", *measured],
            "estimated_fields": [k for k in ("ash", "volatile_matter", "fixed_carbon") if k not in measured],
            "warnings": quality["warnings"]}


@router.get("/returns")
async def my_returns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Kasus retur atas sekam yang saya jual ke pabrik (lot QC / muatan rute yang ditolak atau disortir)."""
    from ..models.factory_ops import ReturnCase
    from ..services.logistics import return_dict
    from ..services.logistics import act_as_system
    await act_as_system(db)      # filter kepemilikan dilakukan di query di bawah
    q = (select(ReturnCase)
         .outerjoin(Harvest, Harvest.id == ReturnCase.harvest_id)
         .outerjoin(DeliveryRequest, DeliveryRequest.id == ReturnCase.request_id)
         .where((Harvest.collector_id == user.id) | (DeliveryRequest.collector_id == user.id))
         .order_by(ReturnCase.id.desc()).limit(200))
    return [return_dict(r) for r in (await db.execute(q)).scalars().all()]


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
            func.sum(func.coalesce(Harvest.verified_kg, Harvest.quantity_kg)),
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


# ---------------------------------------------------------------- Pasar B2B: lihat stok, menawar, penasihat harga
class BidCreate(BaseModel):
    listing_id: int = Field(..., gt=0)
    scheme: str = Field(..., pattern="^(jemput|antar)$")
    price_per_kg: float = Field(..., gt=0, le=10_000)
    quantity_kg: float = Field(..., gt=0, le=200_000, description="Boleh sebagian dari stok")
    pickup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


class BidAdviceRequest(BaseModel):
    listing_id: int = Field(..., gt=0)
    scheme: str = Field("jemput", pattern="^(jemput|antar)$")
    resale_price_per_kg: float = Field(..., gt=0, description="Harga jual ke pabrik (Rp/kg)")
    margin_per_kg: float = Field(default_factory=lambda: P("pasar.default_margin_per_kg"), ge=0)
    margin_pct: float | None = Field(None, ge=0, le=50,
                                     description="Margin dalam % harga jual; bila diisi menggantikan margin_per_kg")
    cost_per_km: float = Field(default_factory=lambda: P("logistik.cost_per_km"), ge=0)
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0)
    quantity_kg: float | None = Field(None, gt=0, le=200_000)


@router.get("/market")
async def market(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Stok petani yang masih terbuka, terurut jarak dari gudang pengepul."""
    rows = (await db.execute(
        select(StockListing)
        .where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
        .order_by(StockListing.id.desc()).limit(200)
    )).scalars().all()
    origin = (user.lat, user.lon) if user.lat is not None else None
    mine = {b.listing_id: b for b in (await db.execute(select(Bid).where(
        Bid.collector_id == user.id, Bid.status == BidStatus.ACTIVE))).scalars().all()}
    out = []
    for r in rows:
        d = trade.listing_dict(r, origin)
        d["my_active_bid"] = ({"bid_id": mine[r.id].id, "price_per_kg": mine[r.id].price_per_kg,
                               "quantity_kg": mine[r.id].quantity_kg} if r.id in mine else None)
        out.append(d)
    return sorted(out, key=lambda d: d.get("distance_km", 1e9))


@router.post("/bids", status_code=201)
async def create_bid(
    req: BidCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    try:
        bid = await trade.place_bid(db, user, req.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"bid_id": bid.id, "status": "active", "scheme": bid.scheme.value, "price_per_kg": bid.price_per_kg,
            "quantity_kg": bid.quantity_kg}


@router.get("/bids")
async def my_bids(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    rows = (await db.execute(select(Bid).where(Bid.collector_id == user.id).order_by(Bid.id.desc()).limit(100))).scalars().all()
    return [{"bid_id": b.id, "listing_id": b.listing_id, "scheme": b.scheme.value, "price_per_kg": b.price_per_kg,
             "quantity_kg": b.quantity_kg, "accepted_kg": b.accepted_kg, "status": b.status.value} for b in rows]


@router.post("/bids/{bid_id}/withdraw")
async def withdraw_bid(
    bid_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    res = await db.execute(update(Bid).where(Bid.id == bid_id, Bid.collector_id == user.id,
                                             Bid.status == BidStatus.ACTIVE)
                           .values(status=BidStatus.WITHDRAWN, decided_at=datetime.now(timezone.utc)))
    if res.rowcount != 1:
        raise HTTPException(409, "Tawaran tidak aktif atau bukan milik Anda.")
    return {"bid_id": bid_id, "status": "withdrawn"}


@router.post("/bid-advisor")
async def bid_advisor(
    req: BidAdviceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tawaran maksimum yang masih untung (netback) dengan biaya logistik marginal dari solver rute."""
    margin = req.margin_per_kg if req.margin_pct is None else req.resale_price_per_kg * req.margin_pct / 100
    try:
        out = await trade.bid_advice(db, user, req.listing_id, req.scheme, req.resale_price_per_kg,
                                     margin, req.cost_per_km, req.vehicle_m3, req.quantity_kg)
        out["margin_per_kg"] = round(margin, 1)
        out["margin_pct"] = round(margin / req.resale_price_per_kg * 100, 2)
        return out
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# ---------------------------------------------------------------- B2B Procurement: Delivery Request ke pabrik
class DeliveryRequestCreate(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=1_000_000)
    moisture_est: float = Field(..., ge=0, le=60)
    ash_est: float | None = Field(None, ge=0, le=60)
    grade_est: str | None = Field(None, pattern="^(A|B|C)$")
    proposed_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    proposed_price_per_kg: float = Field(..., gt=0, le=20_000)
    harvest_ids: list[int] = Field(default_factory=list, max_length=500,
                                   description="Harvest petani (sudah Anda timbang) yang ikut dikirim → dompet biochar")
    note: str | None = Field(None, max_length=500)


class NegotiationAction(BaseModel):
    action: str = Field(..., pattern="^(accept|counter|reject|cancel)$")
    price_per_kg: float | None = Field(None, gt=0, le=20_000)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


@router.get("/factory-price")
async def factory_price(
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    moisture: float = 11.0,
    ash: float | None = None,
):
    """Harga rekomendasi pabrik (target) untuk kadar air tertentu — dasar ajuan yang transparan."""
    if not 0 <= moisture <= 60:
        raise HTTPException(422, "Kadar air 0–60%")
    return factory_ops.factory_price_preview(moisture, ash)


@router.post("/delivery-requests", status_code=201)
async def create_delivery_request(
    req: DeliveryRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    r = await factory_ops.submit_request(db, user, req.model_dump())
    return factory_ops.request_dict(r)


@router.get("/delivery-requests")
async def my_delivery_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    rows = (await db.execute(select(DeliveryRequest).where(DeliveryRequest.collector_id == user.id)
                             .order_by(DeliveryRequest.id.desc()).limit(100))).scalars().all()
    return [factory_ops.request_dict(r) for r in rows]


@router.post("/delivery-requests/{request_id}/respond")
async def respond_delivery_request(
    request_id: int,
    body: NegotiationAction,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Jawab tawaran balik pabrik: accept | counter | reject, atau cancel ajuan."""
    try:
        r = await factory_ops.respond(db, user, request_id, body.action, body.price_per_kg, body.date, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.request_dict(r)


@router.get("/attachable-harvests")
async def attachable_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Harvest petani yang sudah Anda timbang & belum terlampir di ajuan — bisa dikirim ke pabrik (→ dompet)."""
    active_routes = (
        select(RouteStop.harvest_id)
        .join(Route, RouteStop.route_id == Route.id)
        .where(
            RouteStop.harvest_id.is_not(None),
            Route.status.in_([RouteStatus.PLANNED, RouteStatus.IN_PROGRESS]),
        )
    )
    rows = (await db.execute(select(Harvest, User.full_name).join(User, User.id == Harvest.farmer_id)
                             .where(Harvest.collector_id == user.id, Harvest.status == HarvestStatus.VERIFIED,
                                    Harvest.delivery_request_id.is_(None),
                                    ~Harvest.id.in_(active_routes))
                             .order_by(Harvest.id.desc()).limit(200))).all()
    return [{"id": h.id, "farmer": name, "verified_kg": h.verified_kg, "moisture": h.moisture, "grade":
             h.grade.value if hasattr(h.grade, "value") else h.grade} for h, name in rows]



@router.get("/settlements")
async def my_settlements(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tagihan saya ke pabrik (jalur QC & jalur rute): menunggu harga / terutang / dibayar."""
    from sqlalchemy.orm import aliased
    from ..models.factory_ops import CollectorSettlement
    FarmerUser = aliased(User, name="farmer_user")
    q = (select(CollectorSettlement, FarmerUser.full_name.label("farmer_name"))
         .outerjoin(Harvest, Harvest.id == CollectorSettlement.harvest_id)
         .outerjoin(FarmerUser, FarmerUser.id == Harvest.farmer_id)
         .where(CollectorSettlement.collector_id == user.id)
         .order_by(CollectorSettlement.id.desc()).limit(300))
    rows = (await db.execute(q)).all()
    return [{**factory_ops.settlement_dict(s), "farmer_name": fname} for s, fname in rows]


@router.get("/settlements/{settlement_id}/history")
async def my_settlement_history(
    settlement_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Jejak audit tagihan milik pengepul yang sedang login."""
    from ..models.factory_ops import CollectorSettlement
    s = await db.get(CollectorSettlement, settlement_id)
    if s is None or s.collector_id != user.id:
        raise HTTPException(404, "Tagihan tidak ditemukan.")
    return await factory_ops.settlement_history(db, settlement_id)


class PickupPlanRequest(BaseModel):
    bid_ids: list[int] | None = None
    vehicle_m3: float | None = Field(None, gt=0, le=1000)
    cost_per_km: float | None = Field(None, ge=0)
    time_budget_ms: int = Field(500, ge=10, le=2000)


@router.post("/pickup-plan")
async def pickup_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    req: PickupPlanRequest | None = None,
):
    """Rencana rute penjemputan optimal untuk tawaran yang dimenangkan pengepul berskema jemput."""
    from ..models.trade import Bid, BidStatus, DeliveryScheme, StockListing
    from ..models.harvest import Harvest, HarvestStatus
    from ..engines.routing import plan_routes
    from ..schemas.routing import RouteRequest

    depot = {
        "id": f"PGP{user.id:04d}",
        "name": user.full_name,
        "lat": user.lat if user.lat is not None else -7.700,
        "lon": user.lon if user.lon is not None else 110.350,
    }

    q = (
        select(Bid, StockListing, User, Harvest)
        .join(StockListing, StockListing.id == Bid.listing_id)
        .join(User, User.id == Bid.farmer_id)
        .outerjoin(Harvest, Harvest.bid_id == Bid.id)
        .where(
            Bid.collector_id == user.id,
            Bid.status == BidStatus.ACCEPTED,
            Bid.scheme == DeliveryScheme.JEMPUT,
            (Harvest.id.is_(None) | (Harvest.status == HarvestStatus.REPORTED)),
        )
    )
    if req and req.bid_ids:
        q = q.where(Bid.id.in_(req.bid_ids))

    rows = (await db.execute(q.order_by(Bid.id.asc()))).all()

    if not rows:
        return {
            "routes": [],
            "summary": {
                "mills": 0, "total_ton": 0.0, "vehicles_trips": 0, "total_km": 0.0,
                "total_cost": 0, "cost_per_ton": 0, "cost_per_kg": 0.0,
                "baseline_km": 0.0, "saving_pct": 0.0,
                "max_ton_per_trip": 0.0, "algorithm": "None",
            },
            "computation_details": {
                "method": "Capacitated Vehicle Routing Problem (CVRP) — Clarke & Wright 1964",
                "message": "Tidak ada tawaran diterima berskema jemput yang menunggu penjemputan.",
                "steps": [],
                "references": [
                    "Clarke, G. & Wright, J.W. (1964). Scheduling of vehicles from a central depot to a number of delivery points.",
                ],
            },
        }

    mills = []
    for bid, listing, farmer, h in rows:
        lat = listing.lat or farmer.lat or -7.745
        lon = listing.lon or farmer.lon or 110.362
        qty_kg = bid.accepted_kg if bid.accepted_kg > 0 else bid.quantity_kg
        mills.append({
            "id": f"BID-{bid.id}",
            "name": f"{farmer.full_name} (#{bid.id})",
            "lat": lat,
            "lon": lon,
            "stock_ton": qty_kg / 1000.0,
        })

    v_m3 = (req.vehicle_m3 if req and req.vehicle_m3 else P("logistik.vehicle_m3"))
    c_km = (req.cost_per_km if req and req.cost_per_km else P("logistik.cost_per_km"))
    t_budget = (req.time_budget_ms if req and req.time_budget_ms else int(P("logistik.time_budget_ms")))

    route_req = RouteRequest(
        vehicle_m3=v_m3,
        bulk_density_kg_m3=P("logistik.bulk_density_kg_m3"),
        cost_per_km=c_km,
        mode="auto",
        time_budget_ms=t_budget,
    )
    from ..concurrency import run_cpu
    res = await run_cpu(plan_routes, depot, mills, route_req)      # CPU-bound: jangan bekukan event loop
    total_ton = res["summary"]["total_ton"]
    total_cost = res["summary"]["total_cost"]
    res["summary"]["cost_per_kg"] = round(total_cost / (total_ton * 1000), 2) if total_ton > 0 else 0.0
    return res



# ======================================================================================================
# F7 — Petani tanpa HP: pengepul mendaftarkan & melaporkan atas nama petani (persetujuan lisan dicatat)
# ======================================================================================================
import logging as _logging
import secrets as _secrets
import uuid as _uuid

from sqlalchemy.exc import IntegrityError as _IntegrityError

from ..models.compliance import FarmerPayment
from ..models.harvest import Mill
from ..models.ledger import CustodyEvent
from ..services import payments as _payments
from ..services.custody import trusted_device_time
from ..services.phone import normalize_phone
from ..services.privacy import record_consents

_audit = _logging.getLogger("biochain.audit")


class ProxyFarmerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    # Disetarakan dengan pendaftaran petani mandiri (auth.RegisterRequest): nama, HP, kecamatan, kabupaten, lokasi
    full_name: str = Field(..., min_length=2, max_length=100)
    kecamatan: str | None = Field(None, max_length=100)
    kabupaten: str | None = Field(None, max_length=100)
    lat: float | None = Field(None, ge=-11, le=6, description="Lokasi sawah/gudang petani (GPS HP pengepul)")
    lon: float | None = Field(None, ge=95, le=141)
    desa: str | None = Field(None, max_length=100, description="Desa/dusun untuk membedakan nama yang sama")
    phone: str | None = Field(None, max_length=30, description="Opsional — HP keluarga/ketua kelompok tani")
    consent_given: bool = Field(..., description="Petani menyetujui (lisan) data dicatat oleh pengepul")


class ProxyHarvestRequest(BaseModel):
    # Field sama dengan laporan petani mandiri (farmer.HarvestReportRequest)
    farmer_id: int
    quantity_kg: float = Field(..., gt=0, le=50000)
    mill_id: int | None = None
    moisture_est: float | None = Field(None, ge=0, le=60)
    grade_est: str | None = Field(None, pattern="^[ABCD]$")
    photo_url: EvidenceUrl | None = None
    client_event_id: str | None = Field(None, max_length=64)
    client_recorded_at: datetime | None = None


class PayFarmerRequest(BaseModel):
    method: str = Field(..., description="tunai | transfer | qris | ewallet")
    reference: str | None = Field(None, max_length=80)
    evidence_photo_url: EvidenceUrl | None = None
    client_event_id: str | None = Field(None, max_length=64)


def _proxy_dict(u: User) -> dict:
    return {"id": u.id, "full_name": u.full_name, "kecamatan": u.kecamatan,
            "phone": u.phone if has_real_phone(u.phone) else None, "username": u.username}


@router.post("/proxy-farmers", status_code=201)
async def create_proxy_farmer(req: ProxyFarmerRequest, db: Annotated[AsyncSession, Depends(get_db)],
                              user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Daftarkan petani yang tidak punya HP. Akun tidak bisa dipakai login sampai nomor HP & password diatur admin."""
    if not req.consent_given:
        raise HTTPException(422, "Tanyakan dulu persetujuan petani bahwa datanya dicatat (UU PDP).")
    phone = None
    if req.phone:
        phone = normalize_phone(req.phone)
        if phone is None:
            raise HTTPException(422, "Nomor HP tidak valid (boleh dikosongkan).")
        if (await db.execute(select(User.id).where(User.phone == phone))).first():
            raise HTTPException(409, "Nomor HP sudah terdaftar — gunakan akun petani tersebut.")
    from .auth import hash_password
    from ..concurrency import run_cpu
    name = req.full_name.strip() + (f" ({req.desa.strip()})" if req.desa else "")
    farmer = User(full_name=name[:100], role=UserRole.PETANI, is_active=True, kecamatan=req.kecamatan or user.kecamatan,
                  kabupaten=req.kabupaten or user.kabupaten, lat=req.lat, lon=req.lon, managed_by_id=user.id,
                  phone=phone or f"{PROXY_PHONE_PREFIX}{_uuid.uuid4().hex[:12].upper()}",
                  password_hash=await run_cpu(hash_password, _secrets.token_urlsafe(24)))
    db.add(farmer)
    await db.flush()
    await record_consents(db, farmer.id, {"layanan_inti": True}, method="lisan_via_pengepul", recorded_by_id=user.id)
    await db.commit()
    _audit.info("proxy_farmer_created", extra={"collector_id": user.id, "farmer_id": farmer.id})
    return _proxy_dict(farmer)


@router.get("/proxy-farmers")
async def list_proxy_farmers(db: Annotated[AsyncSession, Depends(get_db)],
                             user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    rows = (await db.execute(select(User).where(User.managed_by_id == user.id, User.anonymized_at.is_(None))
                             .order_by(User.full_name))).scalars().all()
    return [_proxy_dict(u) for u in rows]


@router.post("/proxy-harvest", status_code=201)
async def proxy_harvest(req: ProxyHarvestRequest, db: Annotated[AsyncSession, Depends(get_db)],
                        user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Lapor stok atas nama petani binaan (tanpa HP). Idempoten (client_event_id); nota QR dicetak untuk petani."""
    uid = user.id
    replay = await find_replay(db, req.client_event_id)
    if replay is not None:
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": h.farmer_id,
                "replayed": True, "message": "ℹ️ Laporan ini sudah tercatat sebelumnya."}
    farmer = await db.get(User, req.farmer_id)
    if farmer is None or farmer.managed_by_id != uid:
        raise HTTPException(403, "Hanya untuk petani binaan Anda (didaftarkan lewat 'Petani tanpa HP').")
    if req.mill_id is not None and not (await db.execute(select(Mill.id).where(Mill.id == req.mill_id))).first():
        raise HTTPException(422, "mill_id tidak dikenal")
    h_uuid = str(_uuid.uuid4())
    # collector_id = pelapor: lot binaan langsung ditangani pengepul ini (juga syarat RLS harvests di PostgreSQL)
    h = Harvest(uuid=h_uuid, farmer_id=farmer.id, mill_id=req.mill_id, quantity_kg=req.quantity_kg, collector_id=uid,
                status=HarvestStatus.REPORTED, qr_code=new_qr_code(h_uuid), photo_url=req.photo_url,
                farmer_moisture_est=req.moisture_est, farmer_grade_est=req.grade_est,
                reported_at=trusted_device_time(req.client_recorded_at)[0])
    db.add(h)
    await db.flush()
    db.add(CustodyEvent(harvest_id=h.id, stage=CustodyStage.FARMER_REPORT.value, from_status=None,
                        to_status=HarvestStatus.REPORTED.value, weight_kg=req.quantity_kg, actor_id=uid,
                        actor_role=UserRole.PENGEPUL.value, client_event_id=req.client_event_id,
                        client_recorded_at=req.client_recorded_at,
                        note=f"Dilaporkan pengepul atas nama petani tanpa HP (#{farmer.id})"))
    try:
        await db.commit()
    except _IntegrityError:
        await db.rollback()
        replay = await find_replay(db, req.client_event_id)
        if replay is None:
            raise
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": h.farmer_id,
                "replayed": True, "message": "ℹ️ Laporan ini sudah tercatat sebelumnya."}
    return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": farmer.id,
            "farmer_name": farmer.full_name, "replayed": False,
            "message": f"✅ {req.quantity_kg:g} kg dilaporkan atas nama {farmer.full_name}. Cetak/foto nota QR untuk petani."}


@router.get("/harvests/{harvest_id}/contact")
async def farmer_contact(harvest_id: int, db: Annotated[AsyncSession, Depends(get_db)],
                         user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Nomor HP lengkap petani untuk mengatur penjemputan — akses dicatat (akuntabilitas PDP)."""
    h = (await db.execute(select(Harvest).where(Harvest.id == harvest_id))).scalar_one_or_none()
    if h is None:
        raise HTTPException(404, "Harvest tidak ditemukan")
    if h.collector_id not in (None, user.id):
        raise HTTPException(403, "Lot ini sudah ditangani pengepul lain.")
    farmer = await db.get(User, h.farmer_id)
    _audit.info("farmer_contact_viewed", extra={"collector_id": user.id, "harvest_id": h.id, "farmer_id": h.farmer_id})
    no_phone = not has_real_phone(farmer.phone)
    return {"harvest_id": h.id, "farmer_name": farmer.full_name, "phone": None if no_phone else farmer.phone,
            "without_phone": no_phone, "managed_by_me": farmer.managed_by_id == user.id,
            "kecamatan": farmer.kecamatan}


@router.get("/unpaid-harvests")
async def unpaid_harvests(db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Lot yang sudah saya timbang tetapi belum tercatat dibayar ke petani (F8)."""
    return await _payments.unpaid_for_collector(db, user)


@router.post("/harvests/{harvest_id}/pay-farmer", status_code=201)
async def pay_farmer(harvest_id: int, req: PayFarmerRequest, db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Catat pembayaran ke petani + terbitkan kuitansi BYR (Rupiah bulat, NUMERIC). Idempoten (client_event_id)."""
    return await _payments.pay_farmer(db, user, harvest_id, req.method, req.reference, req.evidence_photo_url,
                                      req.client_event_id)


class DownPaymentRequest(BaseModel):
    amount_rp: float = Field(..., gt=0, le=1_000_000_000)
    method: str = Field(..., pattern="^(tunai|transfer|qris|ewallet)$")
    reference: str | None = Field(None, max_length=80)
    client_event_id: str | None = Field(None, max_length=64)


@router.post("/harvests/{harvest_id}/pay-dp", status_code=201)
async def pay_dp(harvest_id: int, req: DownPaymentRequest, db: Annotated[AsyncSession, Depends(get_db)],
                 user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Uang muka ke petani (kuitansi DP-…); dipotong otomatis saat pelunasan BYR."""
    return await _payments.pay_down_payment(db, user, harvest_id, req.amount_rp, req.method, req.reference,
                                            req.client_event_id)


@router.get("/charges")
async def my_charges(db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Potongan logistik atas nama saya (ongkos jarak kosong batal/stok tidak ada)."""
    from ..models.factory_ops import LogisticsCharge
    from ..services.logistics import charge_dict
    rows = (await db.execute(select(LogisticsCharge).where(LogisticsCharge.collector_id == user.id)
                             .order_by(LogisticsCharge.id.desc()).limit(100))).scalars().all()
    return [charge_dict(c) for c in rows]


@router.get("/farmer-payments")
async def my_farmer_payments(db: Annotated[AsyncSession, Depends(get_db)],
                             user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    rows = (await db.execute(select(FarmerPayment).where(FarmerPayment.collector_id == user.id)
                             .order_by(FarmerPayment.id.desc()).limit(200))).scalars().all()
    return [_payments.payment_dict(p) for p in rows]
