"""Service pasar B2B sekam: listing petani → tawaran pengepul → petani memilih → harvest + custody.

Penentuan harga & logistik:
- Reserve price per skema dari petani (Myerson 1981, Math. Oper. Res. 6:58-73): tawaran di bawahnya ditolak.
- Penasihat tawaran pengepul (netback / landed-cost pricing):
      tawaran_maks = harga_jual_ke_pabrik − biaya_logistik_marginal_per_kg − margin
  biaya_logistik_marginal = (km rute dengan listing − km rute tanpa listing) × Rp/km ÷ kg, dengan rute
  dihitung oleh solver CVRP Engine ⑤ (Toth & Vigo 2014, Vehicle Routing: Problems, Methods, and
  Applications, SIAM) — konsep biaya penyisipan (insertion cost; Solomon 1987, Oper. Res. 35:254-265).
- Perbandingan bagi petani: nilai bersih/kg = harga − ongkos antar sendiri (skema antar).
Penerimaan sebagian bersifat atomik (compare-and-swap pada remaining_kg), sehingga dua penerimaan serentak
tidak pernah melebihi stok.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from ..engines.routing import plan_routes, road_km
from ..params import P
from .qr_sign import new_qr_code
from ..models.harvest import Harvest, HarvestStatus, Mill
from ..models.ledger import CustodyEvent, CustodyStage
from ..models.trade import Bid, BidStatus, DeliveryScheme, ListingStatus, StockListing
from ..models.user import User, UserRole
from ..schemas.routing import RouteRequest
from .custody import TransitionConflict

OPEN_STATES = (ListingStatus.OPEN, ListingStatus.PARTIAL)


def _v(e):
    return e.value if hasattr(e, "value") else e


def reserve_for(listing: StockListing, scheme: DeliveryScheme) -> float | None:
    if scheme == DeliveryScheme.JEMPUT:
        return listing.ask_price_jemput if listing.allow_jemput else None
    return listing.ask_price_antar if listing.allow_antar else None


async def listing_location(db: AsyncSession, farmer: User, mill_id: int | None) -> tuple[float | None, float | None]:
    if mill_id is not None:
        m = (await db.execute(select(Mill).where(Mill.id == mill_id))).scalar_one_or_none()
        if m is None:
            raise LookupError("mill_id tidak dikenal")
        return m.lat, m.lon
    return farmer.lat, farmer.lon


async def create_listing(db: AsyncSession, farmer: User, data: dict) -> StockListing:
    if not data["allow_jemput"] and not data["allow_antar"]:
        raise ValueError("Pilih minimal satu skema: jemput atau antar.")
    for scheme in ("jemput", "antar"):
        if data[f"allow_{scheme}"] and not data.get(f"ask_price_{scheme}"):
            raise ValueError(f"Isi harga harapan untuk skema {scheme}.")
    lat, lon = await listing_location(db, farmer, data.get("mill_id"))
    listing = StockListing(
        farmer_id=farmer.id, mill_id=data.get("mill_id"), quantity_kg=data["quantity_kg"],
        remaining_kg=data["quantity_kg"], moisture_pct=data.get("moisture_pct"), grade_estimate=data.get("grade_estimate"),
        allow_jemput=data["allow_jemput"], allow_antar=data["allow_antar"],
        ask_price_jemput=data.get("ask_price_jemput") if data["allow_jemput"] else None,
        ask_price_antar=data.get("ask_price_antar") if data["allow_antar"] else None,
        lat=lat, lon=lon, evidence_photo_url=data.get("evidence_photo_url"), status=ListingStatus.OPEN,
        expires_at=datetime.now(timezone.utc) + timedelta(days=data.get("expires_in_days", 7)),
    )
    db.add(listing)
    await db.flush()
    return listing


async def _open_listing(db: AsyncSession, listing_id: int) -> StockListing:
    listing = (await db.execute(select(StockListing).where(StockListing.id == listing_id)
                                .execution_options(populate_existing=True))).scalar_one_or_none()
    if listing is None:
        raise LookupError("Listing tidak ditemukan")
    if listing.status not in OPEN_STATES or listing.remaining_kg <= 1e-6:
        raise TransitionConflict("Barang lelang ini sudah habis/terjual ke pengepul lain dan lelang telah ditutup.")
    if listing.expires_at and listing.expires_at.replace(tzinfo=listing.expires_at.tzinfo or timezone.utc) < datetime.now(timezone.utc):
        raise TransitionConflict("Listing sudah kedaluwarsa.")
    return listing


async def place_bid(db: AsyncSession, collector: User, data: dict) -> Bid:
    listing = await _open_listing(db, data["listing_id"])
    scheme = DeliveryScheme(data["scheme"])
    reserve = reserve_for(listing, scheme)
    if reserve is None:
        raise ValueError(f"Petani tidak membuka skema {scheme.value} untuk listing ini.")
    if data["price_per_kg"] < reserve:
        raise ValueError(f"Tawaran Rp{data['price_per_kg']:,.0f}/kg di bawah harga minimum petani "
                         f"(Rp{reserve:,.0f}/kg, skema {scheme.value}).")
    if data["quantity_kg"] > listing.remaining_kg + 1e-9:
        raise ValueError(f"Jumlah tawaran melebihi sisa stok ({listing.remaining_kg:g} kg).")
    # Tawaran baru menggantikan tawaran aktif sebelumnya dari pengepul yang sama pada skema yang sama
    await db.execute(update(Bid).where(Bid.listing_id == listing.id, Bid.collector_id == collector.id,
                                       Bid.scheme == scheme, Bid.status == BidStatus.ACTIVE)
                     .values(status=BidStatus.WITHDRAWN, decided_at=datetime.now(timezone.utc)))
    bid = Bid(listing_id=listing.id, collector_id=collector.id, farmer_id=listing.farmer_id, scheme=scheme,
              price_per_kg=data["price_per_kg"],
              quantity_kg=data["quantity_kg"], pickup_date=data.get("pickup_date"), note=data.get("note"),
              est_logistic_cost_per_kg=data.get("est_logistic_cost_per_kg"), status=BidStatus.ACTIVE)
    db.add(bid)
    await db.flush()
    return bid


def farmer_transport_cost_per_kg(listing: StockListing, collector: User, qty_kg: float,
                                 cost_per_km: float | None = None) -> float | None:
    """Ongkos petani mengantar sendiri (pulang-pergi) per kg — dasar perbandingan skema antar."""
    if None in (listing.lat, listing.lon, collector.lat, collector.lon) or qty_kg <= 0:
        return None
    cost_per_km = P("pasar.farmer_cost_per_km") if cost_per_km is None else cost_per_km
    trips = math.ceil(qty_kg / P("pasar.farmer_truck_kg"))
    km = road_km((listing.lat, listing.lon), (collector.lat, collector.lon))
    return trips * 2 * km * cost_per_km / qty_kg


async def bids_for_farmer(db: AsyncSession, farmer: User, listing_id: int) -> dict:
    listing = (await db.execute(select(StockListing).where(StockListing.id == listing_id,
                                                           StockListing.farmer_id == farmer.id))).scalar_one_or_none()
    if listing is None:
        raise LookupError("Listing tidak ditemukan")
    rows = (await db.execute(select(Bid, User).join(User, User.id == Bid.collector_id)
                             .where(Bid.listing_id == listing.id).order_by(Bid.id.desc()))).all()
    out = []
    for bid, collector in rows:
        qty = min(bid.quantity_kg, listing.remaining_kg) or bid.quantity_kg
        transport = (farmer_transport_cost_per_kg(listing, collector, qty)
                     if bid.scheme == DeliveryScheme.ANTAR else 0.0)
        out.append({
            "bid_id": bid.id, "collector": collector.full_name, "collector_id": collector.id,
            "scheme": _v(bid.scheme), "price_per_kg": bid.price_per_kg, "quantity_kg": bid.quantity_kg,
            "accepted_kg": bid.accepted_kg, "pickup_date": bid.pickup_date, "status": _v(bid.status),
            "farmer_transport_cost_per_kg": None if transport is None else round(transport, 1),
            "net_to_farmer_per_kg": None if transport is None else round(bid.price_per_kg - transport, 1),
            "net_to_farmer_total": None if transport is None else round((bid.price_per_kg - transport) * qty),
        })
    active = [b for b in out if b["status"] == "active" and b["net_to_farmer_per_kg"] is not None]
    best = max(active, key=lambda b: b["net_to_farmer_per_kg"], default=None)
    for b in out:
        b["highest_net"] = best is not None and b["bid_id"] == best["bid_id"]
    return {
        "listing": listing_dict(listing), "bids": out,
        "computation_details": {
            "net_to_farmer": "jemput: harga tawaran; antar: harga tawaran − ongkos antar petani",
            "ongkos_antar": f"⌈kg/{P('pasar.farmer_truck_kg'):g}⌉ × 2 × km jalan × "
                            f"Rp{P('pasar.farmer_cost_per_km'):,.0f}/km ÷ kg (menu Parameter → Pasar B2B)",
            "keputusan": "Petani memilih sendiri; 'highest_net' hanya penanda nilai bersih tertinggi.",
        },
    }


async def accept_bid(db: AsyncSession, farmer: User, listing_id: int, bid_id: int, qty_kg: float) -> dict:
    listing = (await db.execute(select(StockListing).where(StockListing.id == listing_id,
                                                           StockListing.farmer_id == farmer.id))).scalar_one_or_none()
    if listing is None:
        raise LookupError("Listing tidak ditemukan")
    bid = (await db.execute(select(Bid).where(Bid.id == bid_id, Bid.listing_id == listing_id))).scalar_one_or_none()
    if bid is None:
        raise LookupError("Tawaran tidak ditemukan pada listing ini")
    if _v(bid.status) != BidStatus.ACTIVE.value:
        raise TransitionConflict(f"Tawaran berstatus '{_v(bid.status)}'.")
    if qty_kg > bid.quantity_kg + 1e-9:
        raise ValueError(f"Jumlah melebihi tawaran pengepul ({bid.quantity_kg:g} kg).")

    now = datetime.now(timezone.utc)
    if db.bind.dialect.name == "postgresql" and await _has_accept_fn(db):
        # PostgreSQL: satu fungsi PL/pgSQL mengunci listing lalu tawaran (SELECT ... FOR UPDATE), memvalidasi
        # di bawah kunci, dan menulis semuanya (migrasi 013). Pesan kesalahan berawalan kode → HTTP.
        try:
            async with db.begin_nested():
                await db.execute(text("SELECT * FROM public.accept_bid_atomic(:l, :b, :f, :q)"),
                                 {"l": listing_id, "b": bid_id, "f": farmer.id, "q": qty_kg})
        except DBAPIError as e:
            msg = str(getattr(e.orig, "args", [e])[0]) if getattr(e, "orig", None) else str(e)
            for code, exc in (("not_found:", LookupError), ("conflict:", TransitionConflict), ("invalid:", ValueError)):
                if code in msg:
                    raise exc(msg.split(code, 1)[1].split("\n")[0].strip()) from e
            raise
        listing = (await db.execute(select(StockListing).where(StockListing.id == listing_id)
                                    .execution_options(populate_existing=True))).scalar_one()
        await db.refresh(bid)
        return await _award_harvest(db, farmer, listing, bid, qty_kg, now)

    # SQLite: compare-and-swap berurutan (writer tunggal → setara atomik)
    # 1. Kurangi stok secara atomik (compare-and-swap): gagal bila stok sudah diambil penerimaan lain
    res = await db.execute(
        update(StockListing)
        .where(StockListing.id == listing_id, StockListing.remaining_kg >= qty_kg - 1e-9,
               StockListing.status.in_(OPEN_STATES))
        .values(remaining_kg=StockListing.remaining_kg - qty_kg, version=StockListing.version + 1)
        .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Sisa stok tidak mencukupi atau listing sudah ditutup — muat ulang data.")
    # 2. Kunci tawaran (hanya sekali diterima)
    res = await db.execute(update(Bid).where(Bid.id == bid_id, Bid.status == BidStatus.ACTIVE)
                           .values(status=BidStatus.ACCEPTED, accepted_kg=qty_kg, decided_at=now)
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Tawaran sudah diputuskan oleh transaksi lain.")
    listing = (await db.execute(select(StockListing).where(StockListing.id == listing_id)
                                .execution_options(populate_existing=True))).scalar_one()
    closed = listing.remaining_kg <= 1e-6
    listing.status = ListingStatus.CLOSED if closed else ListingStatus.PARTIAL
    if closed:
        await db.execute(update(Bid).where(Bid.listing_id == listing_id, Bid.status == BidStatus.ACTIVE)
                         .values(status=BidStatus.REJECTED, decided_at=now))
    return await _award_harvest(db, farmer, listing, bid, qty_kg, now)


_ACCEPT_FN: bool | None = None


async def _has_accept_fn(db: AsyncSession) -> bool:
    """Fungsi accept_bid_atomic ada bila migrasi 013 sudah dijalankan; tanpa itu tetap memakai CAS."""
    global _ACCEPT_FN
    if _ACCEPT_FN is None:
        _ACCEPT_FN = bool((await db.execute(text("SELECT to_regproc('public.accept_bid_atomic') IS NOT NULL"))).scalar())
    return _ACCEPT_FN


async def _award_harvest(db: AsyncSession, farmer: User, listing: StockListing, bid: Bid, qty_kg: float,
                         now: datetime) -> dict:
    # 3. Kontrak menjadi harvest yang masuk alur custody (timbang → angkut → pabrik)
    h_uuid = str(uuid.uuid4())
    harvest = Harvest(uuid=h_uuid, farmer_id=farmer.id, mill_id=listing.mill_id, quantity_kg=qty_kg,
                      status=HarvestStatus.REPORTED, qr_code=new_qr_code(h_uuid), collector_id=bid.collector_id,
                      listing_id=listing.id, bid_id=bid.id, agreed_price_per_kg=bid.price_per_kg,
                      delivery_scheme=_v(bid.scheme), photo_url=listing.evidence_photo_url, reported_at=now)
    db.add(harvest)
    await db.flush()
    db.add(CustodyEvent(harvest_id=harvest.id, stage=CustodyStage.FARMER_REPORT.value, from_status=None,
                        to_status=HarvestStatus.REPORTED.value, weight_kg=qty_kg, actor_id=farmer.id,
                        actor_role=UserRole.PETANI.value,
                        note=f"Lelang: listing #{listing.id}, tawaran #{bid.id}, {_v(bid.scheme)} "
                             f"@Rp{bid.price_per_kg:,.0f}/kg"))
    await db.flush()
    return {"harvest_id": harvest.id, "qr_code": harvest.qr_code, "listing_status": _v(listing.status),
            "remaining_kg": listing.remaining_kg, "accepted_kg": qty_kg, "price_per_kg": bid.price_per_kg,
            "scheme": _v(bid.scheme), "contract_value_rp": round(qty_kg * bid.price_per_kg)}


async def cancel_listing(db: AsyncSession, farmer: User, listing_id: int) -> None:
    res = await db.execute(update(StockListing)
                           .where(StockListing.id == listing_id, StockListing.farmer_id == farmer.id,
                                  StockListing.status.in_(OPEN_STATES))
                           .values(status=ListingStatus.CANCELLED, version=StockListing.version + 1)
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict("Listing tidak ditemukan atau sudah ditutup.")
    await db.execute(update(Bid).where(Bid.listing_id == listing_id, Bid.status == BidStatus.ACTIVE)
                     .values(status=BidStatus.REJECTED, decided_at=datetime.now(timezone.utc)))


def listing_dict(l: StockListing, origin: tuple[float, float] | None = None) -> dict:
    d = {"id": l.id, "farmer_id": l.farmer_id, "mill_id": l.mill_id, "quantity_kg": l.quantity_kg,
         "remaining_kg": round(l.remaining_kg, 3), "moisture_pct": l.moisture_pct, "grade_estimate": l.grade_estimate,
         "schemes": {"jemput": l.ask_price_jemput if l.allow_jemput else None,
                     "antar": l.ask_price_antar if l.allow_antar else None},
         "status": _v(l.status), "evidence_photo_url": l.evidence_photo_url,
         "expires_at": l.expires_at.isoformat() if l.expires_at else None}
    if origin and None not in (*origin, l.lat, l.lon):
        d["distance_km"] = round(road_km(origin, (l.lat, l.lon)), 1)
    return d


async def bid_advice(db: AsyncSession, collector: User, listing_id: int, scheme: str, resale_price_per_kg: float,
                     margin_per_kg: float, cost_per_km: float, vehicle_m3: float, quantity_kg: float | None) -> dict:
    """Tawaran maksimum yang masih untung = harga jual − biaya logistik marginal − margin."""
    listing = await _open_listing(db, listing_id)
    scheme_e = DeliveryScheme(scheme)
    reserve = reserve_for(listing, scheme_e)
    if reserve is None:
        raise ValueError(f"Petani tidak membuka skema {scheme} untuk listing ini.")
    qty = min(quantity_kg or listing.remaining_kg, listing.remaining_kg)
    if qty <= 0:
        raise ValueError("Sisa stok listing 0 kg.")
    details = {"formula": "tawaran_maks = harga_jual − biaya_logistik_marginal/kg − margin/kg",
               "saran": "titik tengah surplus [reserve, tawaran_maks] — solusi tawar Nash berdaya tawar setara "
                        "(Nash 1950, Econometrica 18:155-162)"}

    if scheme_e == DeliveryScheme.ANTAR:
        logistic = 0.0
        details["logistik"] = "skema antar: petani menanggung pengiriman ke gudang (setara DAP)"
    else:
        if None in (collector.lat, collector.lon, listing.lat, listing.lon):
            raise ValueError("Koordinat gudang pengepul / lokasi listing belum diisi.")
        # Komitmen jemput yang belum diangkut = titik yang sudah pasti dikunjungi
        committed = (await db.execute(select(Harvest, StockListing).join(StockListing, StockListing.id == Harvest.listing_id)
                                      .where(Harvest.collector_id == collector.id, Harvest.delivery_scheme == "jemput",
                                             Harvest.status.in_([HarvestStatus.REPORTED, HarvestStatus.VERIFIED]))
                                      )).all()
        points = [{"id": f"H{h.id}", "name": f"Harvest #{h.id}", "lat": l.lat, "lon": l.lon,
                   "stock_ton": h.quantity_kg / 1000} for h, l in committed if l.lat is not None]
        depot = {"lat": collector.lat, "lon": collector.lon, "name": "Gudang pengepul"}
        req = RouteRequest(vehicle_m3=vehicle_m3, cost_per_km=cost_per_km, mode="auto", time_budget_ms=150)
        base_km = plan_routes(depot, points, req)["summary"]["total_km"] if points else 0.0
        cand = {"id": f"L{listing.id}", "name": f"Listing #{listing.id}", "lat": listing.lat, "lon": listing.lon,
                "stock_ton": qty / 1000}
        with_plan = plan_routes(depot, points + [cand], req)
        marginal_km = max(0.0, with_plan["summary"]["total_km"] - base_km)
        logistic = marginal_km * cost_per_km / qty
        details.update({
            "logistik": "biaya penyisipan rute CVRP (Engine ⑤): km(dengan listing) − km(tanpa listing)",
            "titik_komitmen": len(points), "km_tanpa_listing": round(base_km, 1),
            "km_dengan_listing": with_plan["summary"]["total_km"], "km_marginal": round(marginal_km, 1),
            "solver": with_plan["summary"]["algorithm"],
        })
    max_bid = resale_price_per_kg - logistic - margin_per_kg
    return {
        "listing_id": listing.id, "scheme": scheme, "quantity_kg": qty,
        "logistic_cost_per_kg": round(logistic, 1), "max_bid_per_kg": round(max_bid, 1),
        "farmer_reserve_per_kg": reserve, "feasible": max_bid >= reserve,
        "suggested_bid_per_kg": round(max(reserve, min(max_bid, reserve + 0.5 * (max_bid - reserve))), 0)
        if max_bid >= reserve else None,
        "computation_details": details,
    }
