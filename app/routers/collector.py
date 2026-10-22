"""Router: Pengepul (📦) — Endpoints khusus pengepul/collector."""

from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, QualityGrade
from ..models.ledger import CustodyStage
from ..engines.quality import FeedstockSample, score_sample
from ..models.trade import Bid, BidStatus, StockListing
from ..models.factory_ops import DeliveryRequest
from ..models.route import Route, RouteStatus, RouteStop
from ..services import factory_ops, trade
from ..services.custody import find_replay, load_harvest, pct_diff, transition

from ..security.url import EvidenceUrl

router = APIRouter()


class VerifyHarvestRequest(BaseModel):
    harvest_id: int
    weighed_kg: float = Field(..., gt=0, le=50000, description="Hasil timbangan pengepul (dasar harga)")
    moisture: float = Field(..., ge=0, le=60)
    ash: float = Field(..., ge=0, le=40)
    volatile_matter: float = Field(..., ge=0, le=100)
    fixed_carbon: float = Field(..., ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = None
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000, description="Bukti foto serah-terima (opsional)")


class RejectHarvestRequest(BaseModel):
    harvest_id: int
    reason: str = Field(..., min_length=3, max_length=500)
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
    if harvest.agreed_price_per_kg:
        # Hasil lelang: harga kesepakatan × berat timbang (mutu sudah tercermin saat menawar)
        base_price, multiplier = harvest.agreed_price_per_kg, 1.0
    else:
        base_price, multiplier = P("harga_mutu.base_price_per_kg"), quality["price_multiplier"]
    total_price = round(req.weighed_kg * base_price * multiplier)

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
        "price_basis": "harga lelang" if harvest.agreed_price_per_kg else "harga dasar × pengali mutu",
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
    )
    return {"harvest_id": req.harvest_id, "status": "rejected", "custody_event_id": event.id}


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
    listing_id: int
    scheme: str = Field(..., pattern="^(jemput|antar)$")
    price_per_kg: float = Field(..., gt=0, le=10_000)
    quantity_kg: float = Field(..., gt=0, description="Boleh sebagian dari stok")
    pickup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


class BidAdviceRequest(BaseModel):
    listing_id: int
    scheme: str = Field("jemput", pattern="^(jemput|antar)$")
    resale_price_per_kg: float = Field(..., gt=0, description="Harga jual ke pabrik (Rp/kg)")
    margin_per_kg: float = Field(default_factory=lambda: P("pasar.default_margin_per_kg"), ge=0)
    cost_per_km: float = Field(default_factory=lambda: P("logistik.cost_per_km"), ge=0)
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0)
    quantity_kg: float | None = Field(None, gt=0)


@router.get("/market")
async def market(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Stok petani yang masih terbuka, terurut jarak dari gudang pengepul."""
    rows = (await db.execute(select(StockListing).where(StockListing.status.in_(trade.OPEN_STATES))
                             .order_by(StockListing.id.desc()).limit(200))).scalars().all()
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
    try:
        return await trade.bid_advice(db, user, req.listing_id, req.scheme, req.resale_price_per_kg,
                                      req.margin_per_kg, req.cost_per_km, req.vehicle_m3, req.quantity_kg)
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
    res = plan_routes(depot=depot, mills=mills, req=route_req)
    total_ton = res["summary"]["total_ton"]
    total_cost = res["summary"]["total_cost"]
    res["summary"]["cost_per_kg"] = round(total_cost / (total_ton * 1000), 2) if total_ton > 0 else 0.0
    return res
