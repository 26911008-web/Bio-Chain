"""Router: Collector Bidding & Market Discovery — Stock Listings, Bids, Pricing Advice & Offers Dashboard."""

from typing import Annotated, Any
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus, Mill
from ..models.trade import Bid, BidStatus, StockListing, ListingStatus
from ..models.circular import BiocharRequest, BiocharCircularRequest
from ..services import trade

router = APIRouter()


class BidCreate(BaseModel):
    listing_id: int = Field(..., gt=0)
    scheme: str = Field(..., pattern="^(jemput|antar)$")
    price_per_kg: float = Field(..., gt=0, le=10_000)
    quantity_kg: float = Field(..., gt=0, le=200_000, description="Boleh sebagian dari stok")
    pickup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    pickup_schedule_proposed: datetime | None = None
    logistics_mode: str = Field("PICKUP", pattern="^(PICKUP|DELIVER_SELF)$")
    payment_term: str = Field("COD", pattern="^(COD|DP|TEMPO_7D)$")
    note: str | None = Field(None, max_length=500)


class BidAdviceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: int = Field(..., gt=0)
    scheme: str = Field("jemput", pattern="^(jemput|antar)$")
    resale_price_per_kg: float | None = Field(None, gt=0, description="Harga jual ke pabrik (Rp/kg), opsional")
    resale_price: float | None = Field(None, gt=0, description="Alias harga jual ke pabrik")
    margin_per_kg: float = Field(default_factory=lambda: P("pasar.default_margin_per_kg"), ge=0)
    margin_pct: float | None = Field(None, ge=0, le=50,
                                     description="Margin dalam % harga jual; bila diisi menggantikan margin_per_kg")
    cost_per_km: float = Field(default_factory=lambda: P("logistik.cost_per_km"), ge=0)
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0)
    quantity_kg: float | None = Field(None, gt=0, le=200_000)

    @model_validator(mode="before")
    @classmethod
    def resolve_resale_price(cls, data: Any):
        if isinstance(data, dict):
            rp = data.get("resale_price_per_kg") or data.get("resale_price")
            if rp is None:
                rp = float(P("pabrik.base_purchase_price_rp_kg", 650.0) or 650.0)
            data["resale_price_per_kg"] = float(rp)
        return data


@router.get("/market")
async def market(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Stok petani yang masih terbuka, terurut jarak dari gudang pengepul (terfilter spesialisasi)."""
    query = select(StockListing).where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
    spec = getattr(user, "specialization_commodity", None)
    if not spec:
        u_low = f"{(user.username or '')} {(user.full_name or '')}".lower()
        if "sekam" in u_low:
            spec = "sekam_padi"
        elif "jagung" in u_low:
            spec = "tongkol_jagung"
        elif "tebu" in u_low:
            spec = "ampas_tebu"
        elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low:
            spec = "serbuk_sengon"
    if spec:
        query = query.where(StockListing.commodity == spec)

    rows = (await db.execute(query.order_by(StockListing.id.desc()).limit(200))).scalars().all()
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


@router.get("/market-grouped")
async def market_grouped(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    spec = getattr(user, "specialization_commodity", None)
    if not spec:
        u_low = f"{(user.username or '')} {(user.full_name or '')}".lower()
        if "sekam" in u_low:
            spec = "sekam_padi"
        elif "jagung" in u_low:
            spec = "tongkol_jagung"
        elif "tebu" in u_low:
            spec = "ampas_tebu"
        elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low:
            spec = "serbuk_sengon"

    q = select(StockListing).where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
    if spec:
        q = q.where(StockListing.commodity == spec)

    rows = (await db.execute(q.order_by(StockListing.id.desc()).limit(300))).scalars().all()
    origin = (user.lat, user.lon) if user.lat is not None else None
    mine = {b.listing_id: b for b in (await db.execute(
        select(Bid).where(Bid.collector_id == user.id, Bid.status == BidStatus.ACTIVE)
    )).scalars().all()}

    grouped: dict[str, dict] = {}
    for r in rows:
        c_code = r.commodity or "sekam_padi"
        if c_code not in grouped:
            grouped[c_code] = {
                "commodity": c_code,
                "total_stock_kg": 0.0,
                "direct_count": 0,
                "bidding_count": 0,
                "direct_listings": [],
                "bidding_listings": [],
            }
        item = trade.listing_dict(r, origin)
        item["my_active_bid"] = ({"bid_id": mine[r.id].id, "price_per_kg": mine[r.id].price_per_kg,
                                  "quantity_kg": mine[r.id].quantity_kg} if r.id in mine else None)
        grouped[c_code]["total_stock_kg"] = round(grouped[c_code]["total_stock_kg"] + r.remaining_kg, 2)
        if getattr(r, "transaction_mode", "DIRECT") == "BIDDING":
            grouped[c_code]["bidding_count"] += 1
            grouped[c_code]["bidding_listings"].append(item)
        else:
            grouped[c_code]["direct_count"] += 1
            grouped[c_code]["direct_listings"].append(item)

    return list(grouped.values())


@router.get("/offers-dashboard")
async def get_offers_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Dashboard Status Penawaran Pengepul Spesialis (Grouped & Sorted per Biomassa).
    Terbagi menjadi 2 Tab: 'Langsung Diambil' dan 'Lelang'.
    """
    spec = getattr(user, "specialization_commodity", None)
    if not spec:
        u_low = f"{(user.username or '')} {(user.full_name or '')}".lower()
        if "sekam" in u_low:
            spec = "sekam_padi"
        elif "jagung" in u_low:
            spec = "tongkol_jagung"
        elif "tebu" in u_low:
            spec = "ampas_tebu"
        elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low:
            spec = "serbuk_sengon"

    listings_q = select(StockListing).where(
        StockListing.status.in_(trade.OPEN_STATES),
        StockListing.remaining_kg > 1e-6
    )
    listings = (await db.execute(listings_q.order_by(StockListing.id.desc()))).scalars().all()

    # Preload farmers
    f_ids = list({l.farmer_id for l in listings if l.farmer_id})
    farmers_map = {}
    if f_ids:
        f_res = await db.execute(select(User).where(User.id.in_(f_ids)))
        farmers_map = {u.id: u for u in f_res.scalars().all()}

    # Preload all mills
    mills_res = await db.execute(select(Mill))
    mills_map = {m.id: m for m in mills_res.scalars().all()}

    # Preload bids placed by this collector
    my_bids_res = await db.execute(select(Bid).where(Bid.collector_id == user.id))
    my_bids_by_listing = {}
    for b in my_bids_res.scalars().all():
        if b.listing_id not in my_bids_by_listing:
            my_bids_by_listing[b.listing_id] = []
        my_bids_by_listing[b.listing_id].append(b)

    # Preload all bids for listings to count competing bidders
    all_bids_res = await db.execute(select(Bid))
    all_bids_by_listing = {}
    for b in all_bids_res.scalars().all():
        all_bids_by_listing.setdefault(b.listing_id, []).append(b)

    # Preload unverified direct harvest offers
    direct_harvests_q = select(Harvest).where(
        Harvest.status == HarvestStatus.REPORTED,
        Harvest.collector_id == user.id
    )
    direct_harvests = (await db.execute(direct_harvests_q.order_by(Harvest.id.desc()))).scalars().all()

    # Preload all verified harvests for this collector
    verified_harvests_q = select(Harvest).where(
        Harvest.status == HarvestStatus.VERIFIED,
        Harvest.collector_id == user.id
    )
    verified_harvests = (await db.execute(verified_harvests_q.order_by(Harvest.id.desc()))).scalars().all()

    # Preload biochar requests for poktan backhaul
    biochar_reqs = (await db.execute(
        select(BiocharCircularRequest)
        .where(BiocharCircularRequest.status.in_(["SUBMITTED", "APPROVED", "DISPATCHED_TO_COLLECTOR"]))
        .order_by(BiocharCircularRequest.id.desc())
    )).scalars().all()

    langsung_diambil = []
    lelang = []
    diantar_petani = []

    # Map verified harvests
    for h in verified_harvests:
        f = farmers_map.get(h.farmer_id) if h.farmer_id else None
        target_mill = mills_map.get(h.mill_id) if h.mill_id else None
        item = {
            "id": h.id,
            "source_type": "harvest",
            "is_verified": True,
            "status_badge": "Stok Gudang (Siap Delivery)",
            "farmer_name": f.full_name if f else (f.username if f else f"Petani #{h.farmer_id}"),
            "farmer_phone": f.phone if f else "-",
            "farmer_kecamatan": getattr(f, "kecamatan", None) or getattr(target_mill, "kecamatan", None) or "-",
            "farmer_lat": f.lat if f and f.lat is not None else None,
            "farmer_lon": f.lon if f and f.lon is not None else None,
            "commodity_code": h.commodity or "sekam_padi",
            "biomass_type": h.commodity or "sekam_padi",
            "biomass_name": (h.commodity or "sekam_padi").replace("_", " ").title(),
            "quantity_kg": h.verified_kg or h.quantity_kg,
            "moisture_pct": h.moisture,
            "ash_pct": h.ash,
            "grade": h.grade.value if h.grade and hasattr(h.grade, 'value') else (h.grade or "A"),
            "delivery_scheme": "JEMPUT",
            "delivery_scheme_label": "Gudang Pengepul",
            "price_per_kg": getattr(h, "agreed_price_per_kg", None) or h.base_price_per_kg or 450.0,
            "total_estimated_rp": (h.verified_kg or h.quantity_kg) * (getattr(h, "agreed_price_per_kg", None) or h.base_price_per_kg or 450.0),
            "pickup_date": getattr(h, "pickup_date", None) or "-",
            "payment_scheme": "CASH",
            "notes": getattr(h, "notes", None) or "Biomassa tersimpan di gudang transit.",
            "target_factory_id": h.mill_id,
            "target_factory_name": target_mill.name if target_mill else "Pabrik Utama",
            "target_factory_phone": getattr(target_mill, "phone", "-"),
            "factory_price_estimate": getattr(target_mill, "contract_price_per_kg", 650.0),
            "factory_distance_km": 14.5,
            "factory_delivery_mode": "Pabrik Jemput Armada",
            "created_at": h.created_at.isoformat() if getattr(h, "created_at", None) else None,
            "actions": {
                "can_plan_pickup": False,
                "can_verify": False,
                "can_bid": False,
                "can_deliver": True,
            }
        }
        langsung_diambil.append(item)

    # Map direct reported harvests
    for h in direct_harvests:
        f = farmers_map.get(h.farmer_id) if h.farmer_id else None
        target_mill = mills_map.get(h.mill_id) if h.mill_id else None
        item = {
            "id": h.id,
            "source_type": "harvest",
            "is_verified": False,
            "status_badge": "Belum Ditimbang",
            "farmer_name": f.full_name if f else (f.username if f else f"Petani #{h.farmer_id}"),
            "farmer_phone": f.phone if f else "-",
            "farmer_kecamatan": getattr(f, "kecamatan", None) or getattr(target_mill, "kecamatan", None) or "-",
            "farmer_lat": f.lat if f and f.lat is not None else None,
            "farmer_lon": f.lon if f and f.lon is not None else None,
            "commodity_code": h.commodity or "sekam_padi",
            "biomass_type": h.commodity or "sekam_padi",
            "biomass_name": (h.commodity or "sekam_padi").replace("_", " ").title(),
            "quantity_kg": h.quantity_kg,
            "moisture_pct": h.moisture,
            "ash_pct": h.ash,
            "grade": h.grade.value if h.grade and hasattr(h.grade, 'value') else (h.grade or "A"),
            "delivery_scheme": "JEMPUT",
            "delivery_scheme_label": "Dijemput Pengepul",
            "price_per_kg": getattr(h, "agreed_price_per_kg", None) or h.base_price_per_kg or 450.0,
            "total_estimated_rp": h.quantity_kg * (getattr(h, "agreed_price_per_kg", None) or h.base_price_per_kg or 450.0),
            "pickup_date": getattr(h, "pickup_date", None) or "-",
            "payment_scheme": "CASH",
            "notes": getattr(h, "notes", None) or "-",
            "target_factory_id": h.mill_id,
            "target_factory_name": target_mill.name if target_mill else "Pabrik Utama",
            "target_factory_phone": getattr(target_mill, "phone", "-"),
            "factory_price_estimate": getattr(target_mill, "contract_price_per_kg", 650.0),
            "factory_distance_km": 14.5,
            "factory_delivery_mode": "Pabrik Jemput Armada",
            "created_at": h.created_at.isoformat() if getattr(h, "created_at", None) else None,
            "actions": {
                "can_plan_pickup": True,
                "can_verify": True,
                "can_bid": False,
                "can_deliver": False,
            }
        }
        langsung_diambil.append(item)

    # Map listings
    for l in listings:
        f = farmers_map.get(l.farmer_id)
        is_bidding = getattr(l, "transaction_mode", "BIDDING") == "BIDDING" or (getattr(l, "allow_jemput", True) or not getattr(l, "allow_antar", False))
        my_bids = my_bids_by_listing.get(l.id, [])
        all_bids = all_bids_by_listing.get(l.id, [])
        active_my_bid = next((b for b in my_bids if b.status == BidStatus.ACTIVE), None)
        highest_bid = max([b.price_per_kg for b in all_bids], default=l.floor_price or 400.0) if all_bids else (l.floor_price or 400.0)

        hrg = l.ask_price_jemput or l.ask_price_antar or l.floor_price or 450.0
        skema = "JEMPUT" if l.ask_price_jemput else "ANTAR"

        target_mill = mills_map.get(l.factory_target_id) if getattr(l, 'factory_target_id', None) else None
        fac_price = target_mill.contract_price_per_kg if target_mill else 650.0

        item = {
            "id": l.id,
            "source_type": "listing",
            "is_verified": False,
            "status_badge": "Lelang Aktif" if is_bidding else "Langsung",
            "farmer_name": f.full_name if f else (f.username if f else f"Petani #{l.farmer_id}"),
            "farmer_phone": f.phone if f else "-",
            "farmer_kecamatan": f.kecamatan if f else "-",
            "farmer_lat": f.lat if f and f.lat is not None else None,
            "farmer_lon": f.lon if f and f.lon is not None else None,
            "commodity_code": l.commodity or "sekam_padi",
            "biomass_type": l.commodity or "sekam_padi",
            "biomass_name": (l.commodity or "sekam_padi").replace("_", " ").title(),
            "quantity_kg": l.remaining_kg,
            "moisture_pct": l.moisture_pct,
            "ash_pct": None,
            "grade": l.grade_estimate or "A",
            "delivery_scheme": skema,
            "delivery_scheme_label": "Dijemput Pengepul" if skema == "JEMPUT" else "Diantar Petani",
            "price_per_kg": hrg,
            "total_estimated_rp": l.remaining_kg * hrg,
            "pickup_date": (l.auction_expiry.strftime("%Y-%m-%d") if getattr(l, "auction_expiry", None) else (l.expires_at.strftime("%Y-%m-%d") if getattr(l, "expires_at", None) else "-")),
            "payment_scheme": getattr(l, "payment_scheme", None) or getattr(l, "payment_status", None) or "CASH",
            "notes": getattr(l, "notes", None) or "-",
            "target_factory_id": getattr(l, 'factory_target_id', None),
            "target_factory_name": target_mill.name if target_mill else "Pabrik Terdaftar",
            "target_factory_phone": target_mill.phone if target_mill else "-",
            "factory_price_estimate": fac_price,
            "factory_distance_km": getattr(l, 'factory_distance_km', 18.2) or 18.2,
            "factory_delivery_mode": getattr(l, 'factory_delivery_mode', 'Pabrik Jemput Armada') or 'Pabrik Jemput Armada',
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "is_bidding": is_bidding,
            "bidding_details": {
                "floor_price": l.floor_price or 400.0,
                "highest_bid": highest_bid,
                "total_bids": len(all_bids),
                "my_bid": {
                    "id": active_my_bid.id,
                    "price_per_kg": active_my_bid.price_per_kg,
                    "quantity_kg": active_my_bid.quantity_kg,
                    "scheme": (active_my_bid.scheme.value if hasattr(active_my_bid.scheme, "value") else str(active_my_bid.scheme)) if active_my_bid else None,
                    "status": (active_my_bid.status.value if hasattr(active_my_bid.status, "value") else str(active_my_bid.status)) if active_my_bid else None,
                } if active_my_bid else None,
            } if is_bidding else None,
            "actions": {
                "can_plan_pickup": skema == "JEMPUT" and not is_bidding,
                "can_verify": False,
                "can_bid": is_bidding,
                "can_deliver": False,
            }
        }

        if is_bidding:
            lelang.append(item)
        elif skema == "ANTAR":
            diantar_petani.append(item)
        else:
            langsung_diambil.append(item)

    total_unverified = len([x for x in langsung_diambil if not x.get("is_verified")])
    total_verified = len([x for x in langsung_diambil if x.get("is_verified")])

    return {
        "specialization_commodity": spec,
        "specialization_name": spec.replace("_", " ").title() if spec else "Semua Komoditas",
        "total_direct": len(langsung_diambil),
        "total_auction": len(lelang),
        "total_diantar": len(diantar_petani),
        "total_unverified": total_unverified,
        "total_verified": total_verified,
        "langsung_diambil": langsung_diambil,
        "lelang": lelang,
        "diantar_petani": diantar_petani,
        "tabs": {
            "langsung_diambil": langsung_diambil,
            "lelang": lelang,
            "diantar_petani": diantar_petani,
        }
    }
