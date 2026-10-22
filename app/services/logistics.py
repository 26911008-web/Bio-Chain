"""Service: siklus hidup rute di lapangan — stop gagal, pembatalan, jejak GPS store-and-forward, emisi, retur.

Kondisi lapangan yang ditangani:
- Supir tiba tetapi sekam tidak ada / basah / jalan tak bisa dilalui → stop GAGAL, rute tetap bisa diselesaikan,
  harvest kembali bebas untuk dijadwalkan ulang (indeks unik hanya untuk stop hidup).
- Pengepul membatalkan penjualan saat truk sudah jalan → stop dibatalkan + ongkos jarak kosong (deadhead)
  dibebankan ke pengepul; barang yang SUDAH di truk tidak bisa dibatalkan (harus lewat penolakan/retur pabrik).
- Pabrik membatalkan rute → stop yang belum dijemput dibatalkan; muatan yang sudah naik tetap diantar.
- Sinyal hilang → titik GPS dikirim belakangan dalam batch; `client_point_id` unik membuat kiriman ulang aman,
  dan emisi dihitung ulang bila jejak tiba setelah rute selesai.
- Muatan ditolak di gerbang / QC (seluruh lot atau sebagian karung) → kasus retur dengan disposisi & penanggung biaya.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..data import DEPOT
from ..engines.emission import TrackPoint, emissions_from_plan, emissions_from_track
from ..engines.routing import road_km
from ..models.factory_ops import ReturnCase, ReturnDisposition, ReturnReason
from ..models.harvest import Harvest, HarvestStatus, Mill
from ..models.ledger import CustodyStage
from ..models.route import LIVE_STOP_STATUSES, Route, RouteStatus, RouteStop, RouteTrackPoint, StopStatus
from ..models.trade import Bid, BidStatus, ListingStatus, StockListing
from ..models.user import User
from ..params import P
from .custody import TransitionConflict, transition

FAIL_REASONS = ("stok_tidak_ada", "dibatalkan_pengepul", "mutu_buruk", "akses_jalan", "penggilingan_tutup",
                "truk_penuh", "lainnya")


def _v(e):
    return e.value if hasattr(e, "value") else e


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def act_as_system(db: AsyncSession) -> None:
    """Tulis lintas pemilik (mis. pengepul membatalkan stop di rute pabrik) SETELAH otorisasi di aplikasi.
    PostgreSQL: identitas RLS transaksi ini menjadi 'system' (SET LOCAL, hilang di akhir transaksi)."""
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT set_config('app.role', 'system', true)"))


# ---------------------------------------------------------------- stop gagal & pembatalan
async def fail_stop(db: AsyncSession, driver: User, stop_id: int, reason: str, note: str | None,
                    lat: float | None, lon: float | None, recorded_at: datetime | None) -> dict:
    stop = (await db.execute(select(RouteStop).join(Route, RouteStop.route_id == Route.id)
                             .where(RouteStop.id == stop_id, Route.driver_id == driver.id)
                             .execution_options(populate_existing=True))).scalar_one_or_none()
    if stop is None:
        raise LookupError("Stop tidak ditemukan pada rute Anda")
    if stop.stop_status == StopStatus.FAILED.value:
        return {"stop_id": stop.id, "stop_status": stop.stop_status, "already_recorded": True}
    route = await db.get(Route, stop.route_id)
    if _v(route.status) != RouteStatus.IN_PROGRESS.value:
        raise TransitionConflict("Mulai rute terlebih dahulu sebelum melaporkan stop gagal.")
    res = await db.execute(update(RouteStop)
                           .where(RouteStop.id == stop.id, RouteStop.stop_status == StopStatus.PENDING.value)
                           .values(stop_status=StopStatus.FAILED.value, fail_reason=reason, fail_note=note,
                                   failed_at=recorded_at or datetime.now(timezone.utc),
                                   lat_arrived=lat, lon_arrived=lon)
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise TransitionConflict(f"Stop berstatus '{stop.stop_status}', tidak bisa ditandai gagal.")
    charge, dp = None, None
    if reason in ("stok_tidak_ada", "dibatalkan_pengepul") and stop.harvest_id:
        h = await db.get(Harvest, stop.harvest_id)
        if h is not None and h.collector_id:
            # Truk sudah sampai tapi barang tidak ada / dibatalkan: jarak pulang-pergi ke titik ini sia-sia →
            # ditanggung pengepul pemilik lot (dipotong dari tagihan pabrik berikutnya).
            charge = await open_charge(db, driver, "stop_gagal", h.collector_id, route.id, stop.id, h.id, stop.mill_id,
                                       f"Stop gagal ({reason}) — {note or '-'}")
            if reason == "stok_tidak_ada":
                from .payments import settle_dp_on_cancel
                dp = await settle_dp_on_cancel(db, h.id, "wajib_dikembalikan",
                                               f"Stok tidak ada saat truk tiba (stop #{stop.id})")
    return {"stop_id": stop.id, "stop_status": StopStatus.FAILED.value, "already_recorded": False,
            "harvest_id": stop.harvest_id, "charge": charge, "down_payment": dp,
            "message": "Stop ditandai gagal. Panen kembali ke antrean pabrik untuk dijadwalkan ulang."}


def charge_dict(c) -> dict:
    return {"id": c.id, "kind": c.kind, "collector_id": c.collector_id, "route_id": c.route_id, "stop_id": c.stop_id,
            "harvest_id": c.harvest_id, "km": c.km, "amount_rp": int(c.amount_rp), "status": c.status,
            "settlement_id": c.settlement_id, "reason": c.reason,
            "created_at": c.created_at.isoformat() if c.created_at else None}


async def open_charge(db: AsyncSession, actor: User, kind: str, collector_id: int, route_id: int | None,
                      stop_id: int | None, harvest_id: int | None, mill_id: int | None, reason: str) -> dict | None:
    from ..models.factory_ops import LogisticsCharge
    mill = await db.get(Mill, mill_id) if mill_id else None
    if mill is None:
        return None
    km = 2 * road_km((DEPOT["lat"], DEPOT["lon"]), (mill.lat, mill.lon))
    fee = round(km * P("logistik.cancel_fee_per_km"))
    if fee <= 0:
        return None
    await act_as_system(db)                                 # supir/pengepul menulis potongan atas nama sistem
    c = LogisticsCharge(kind=kind, collector_id=collector_id, route_id=route_id, stop_id=stop_id, harvest_id=harvest_id,
                        km=round(km, 2), amount_rp=fee, reason=reason, created_by_id=actor.id)
    db.add(c)
    await db.flush()
    return charge_dict(c)


async def cancel_route(db: AsyncSession, actor: User, route_id: int, reason: str) -> dict:
    route = (await db.execute(select(Route).where(Route.id == route_id)
                              .execution_options(populate_existing=True))).scalar_one_or_none()
    if route is None:
        raise LookupError("Rute tidak ditemukan")
    status = _v(route.status)
    if status not in (RouteStatus.PLANNED.value, RouteStatus.IN_PROGRESS.value):
        raise TransitionConflict(f"Rute berstatus '{status}' tidak dapat dibatalkan.")
    now = datetime.now(timezone.utc)
    res = await db.execute(update(RouteStop)
                           .where(RouteStop.route_id == route.id, RouteStop.stop_status == StopStatus.PENDING.value)
                           .values(stop_status=StopStatus.CANCELLED.value, fail_reason="dibatalkan_pabrik",
                                   fail_note=reason, failed_at=now)
                           .execution_options(synchronize_session=False))
    picked = (await db.execute(select(func.count()).select_from(RouteStop).where(
        RouteStop.route_id == route.id, RouteStop.stop_status == StopStatus.PICKED_UP.value))).scalar_one()
    route.cancel_reason, route.cancelled_by_id, route.cancelled_at = reason, actor.id, now
    if picked == 0:
        route.status = RouteStatus.CANCELLED
        msg = "Rute dibatalkan. Semua panen kembali ke antrean."
    else:
        msg = (f"{res.rowcount} stop dibatalkan. {picked} stop sudah dimuat: supir tetap mengantar muatan ke pabrik "
               "lalu menyelesaikan rute.")
    return {"route_id": route.id, "route_status": _v(route.status), "cancelled_stops": res.rowcount,
            "picked_up_stops": picked, "message": msg}


async def cancel_purchase(db: AsyncSession, collector: User, harvest_id: int, reason: str) -> dict:
    """Pengepul membatalkan pembelian/penjualan sebuah panen.

    - REPORTED hasil lelang (belum ditimbang): tawaran → cancelled, stok listing petani dikembalikan,
      harvest → REJECTED (alasan dicatat). Petani bisa menjual ke pengepul lain.
    - VERIFIED dan dijadwalkan di rute pabrik: stop → cancelled. Bila truk sudah berangkat, ongkos jarak kosong
      pulang-pergi ke titik itu dibebankan ke pengepul (`cancel_fee_rp`). Panen tetap milik pengepul (VERIFIED).
    - COLLECTED (sudah di truk) / DELIVERED: ditolak — barang sudah berpindah tangan; gunakan alur retur pabrik.
    """
    h = (await db.execute(select(Harvest).where(Harvest.id == harvest_id)
                          .execution_options(populate_existing=True))).scalar_one_or_none()
    if h is None:
        raise LookupError("Harvest tidak ditemukan")
    if h.collector_id != collector.id:
        raise LookupError("Harvest tidak ditemukan")          # jangan bocorkan keberadaan milik pengepul lain
    status = _v(h.status)
    await act_as_system(db)
    if status == HarvestStatus.REPORTED.value:
        if h.bid_id is None:
            raise TransitionConflict("Bukan pembelian lelang — gunakan 'Tolak' untuk laporan biasa.")
        res = await db.execute(update(Bid).where(Bid.id == h.bid_id, Bid.status == BidStatus.ACCEPTED)
                               .values(status=BidStatus.CANCELLED, decided_at=datetime.now(timezone.utc))
                               .execution_options(synchronize_session=False))
        if res.rowcount != 1:
            raise TransitionConflict("Tawaran sudah tidak berstatus diterima.")
        from .payments import settle_dp_on_cancel
        dp = await settle_dp_on_cancel(db, h.id, "hangus_untuk_petani",
                                       f"Pengepul membatalkan pembelian sepihak: {reason}")
        listing = (await db.execute(select(StockListing).where(StockListing.id == h.listing_id)
                                    .execution_options(populate_existing=True))).scalar_one_or_none()
        restored = 0.0
        if listing is not None and _v(listing.status) != ListingStatus.CANCELLED.value:
            restored = min(h.quantity_kg, listing.quantity_kg - listing.remaining_kg)
            new_remaining = listing.remaining_kg + restored
            await db.execute(update(StockListing).where(StockListing.id == listing.id)
                             .values(remaining_kg=new_remaining, version=StockListing.version + 1,
                                     status=(ListingStatus.OPEN if new_remaining >= listing.quantity_kg - 1e-6
                                             else ListingStatus.PARTIAL))
                             .execution_options(synchronize_session=False))
        await transition(db, h.id, HarvestStatus.REPORTED, HarvestStatus.REJECTED, collector,
                         CustodyStage.COLLECTOR_REJECT, note=f"Pembelian dibatalkan pengepul: {reason}",
                         rejected_reason=f"dibatalkan_pengepul: {reason}", rejected_at=datetime.now(timezone.utc),
                         reject_category="dibatalkan_pengepul")
        return {"harvest_id": h.id, "outcome": "lelang_dibatalkan", "listing_restored_kg": restored,
                "down_payment": dp,
                "message": f"Pembelian dibatalkan; {restored:g} kg dikembalikan ke listing petani."
                           + (f" DP Rp{dp['amount_rp']:,} menjadi hak petani (kompensasi batal sepihak)." if dp else "")}
    if status == HarvestStatus.VERIFIED.value:
        stop = (await db.execute(select(RouteStop).where(
            RouteStop.harvest_id == h.id, RouteStop.stop_status == StopStatus.PENDING.value)
            .execution_options(populate_existing=True))).scalar_one_or_none()
        if stop is None:
            raise TransitionConflict("Panen ini tidak sedang dijadwalkan dijemput; tidak ada yang dibatalkan.")
        route = await db.get(Route, stop.route_id)
        fee, km = 0.0, 0.0
        if _v(route.status) == RouteStatus.IN_PROGRESS.value:
            mill = await db.get(Mill, stop.mill_id) if stop.mill_id else None
            if mill is not None:
                km = 2 * road_km((DEPOT["lat"], DEPOT["lon"]), (mill.lat, mill.lon))
                fee = round(km * P("logistik.cancel_fee_per_km"))
        res = await db.execute(update(RouteStop)
                               .where(RouteStop.id == stop.id, RouteStop.stop_status == StopStatus.PENDING.value)
                               .values(stop_status=StopStatus.CANCELLED.value, fail_reason="dibatalkan_pengepul",
                                       fail_note=f"{reason} | ongkos batal Rp{fee:,.0f} ({km:.1f} km)",
                                       failed_at=datetime.now(timezone.utc))
                               .execution_options(synchronize_session=False))
        if res.rowcount != 1:
            raise TransitionConflict("Stop baru saja dijemput supir — tidak bisa dibatalkan, gunakan alur retur.")
        charge = None
        if fee > 0:
            charge = await open_charge(db, collector, "batal_pembelian", collector.id, route.id, stop.id, h.id,
                                       stop.mill_id, f"Batal saat truk di jalan: {reason}")
        return {"harvest_id": h.id, "outcome": "stop_dibatalkan", "route_id": route.id, "charge": charge,
                "route_status": _v(route.status), "cancel_fee_rp": fee, "deadhead_km": round(km, 2),
                "message": ("Stop dibatalkan sebelum truk berangkat (tanpa ongkos)." if fee == 0 else
                            f"Stop dibatalkan saat truk di jalan: ongkos jarak kosong Rp{fee:,.0f} dibebankan.")}
    raise TransitionConflict(f"Harvest berstatus '{status}': barang sudah di truk/pabrik. Gunakan alur retur.")


# ---------------------------------------------------------------- GPS store & forward
async def ingest_track(db: AsyncSession, driver: User, route_id: int, points: list[dict]) -> dict:
    route = (await db.execute(select(Route).where(Route.id == route_id, Route.driver_id == driver.id))
             ).scalar_one_or_none()
    if route is None:
        raise LookupError("Rute tidak ditemukan")
    if _v(route.status) == RouteStatus.PLANNED.value:
        raise TransitionConflict("Rute belum dimulai.")
    ids = [p["client_point_id"] for p in points]
    existing = set((await db.execute(select(RouteTrackPoint.client_point_id)
                                     .where(RouteTrackPoint.client_point_id.in_(ids)))).scalars().all())
    rows = [{"route_id": route.id, "driver_id": driver.id, "client_point_id": p["client_point_id"],
             "recorded_at": _utc(p["recorded_at"]), "lat": p["lat"], "lon": p["lon"],
             "accuracy_m": p.get("accuracy_m"), "speed_mps": p.get("speed_mps")}
            for p in points if p["client_point_id"] not in existing]
    rows = list({r["client_point_id"]: r for r in rows}.values())     # duplikat di dalam batch yang sama
    inserted = 0
    if rows:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        stmt = dialect_insert(RouteTrackPoint).values(rows).on_conflict_do_nothing(index_elements=["client_point_id"])
        res = await db.execute(stmt)
        inserted = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else len(rows)
    recomputed = None
    if _v(route.status) == RouteStatus.COMPLETED.value and inserted:
        recomputed = await finalize_route_emissions(db, route)       # jejak tiba setelah rute selesai
    return {"route_id": route.id, "received": len(points), "inserted": inserted,
            "duplicates_ignored": len(points) - inserted, "emissions_recomputed": recomputed is not None}


async def finalize_route_emissions(db: AsyncSession, route: Route) -> dict:
    stops = (await db.execute(select(RouteStop).where(RouteStop.route_id == route.id)
                              .order_by(RouteStop.stop_order))).scalars().all()
    picked = [s for s in stops if s.stop_status == StopStatus.PICKED_UP.value]
    delivered_kg = sum((s.actual_ton or s.planned_ton or 0) * 1000 for s in picked)
    pts = (await db.execute(select(RouteTrackPoint).where(RouteTrackPoint.route_id == route.id))).scalars().all()
    track = [TrackPoint(_utc(p.recorded_at), p.lat, p.lon, p.accuracy_m) for p in pts]
    pickups = [(_utc(s.pickup_at), (s.actual_ton or s.planned_ton or 0) * 1000) for s in picked if s.pickup_at]
    res = emissions_from_track(track, pickups) if len(track) >= 2 else None
    if res is None or res["total_km"] <= 0:
        # Tanpa jejak GPS: depot → stop yang benar-benar didatangi (dijemput/gagal) → depot, jarak jalan estimasi
        mill_ids = [s.mill_id for s in stops if s.mill_id and s.stop_status in ("picked_up", "failed")]
        mills = {m.id: m for m in (await db.execute(select(Mill).where(Mill.id.in_(mill_ids)))).scalars().all()}
        path = [(DEPOT["lat"], DEPOT["lon"])]
        loads, load = [], 0.0
        for s in stops:
            m = mills.get(s.mill_id)
            if m is None:
                continue
            loads.append(load)
            path.append((m.lat, m.lon))
            if s.stop_status == "picked_up":
                load += (s.actual_ton or s.planned_ton or 0) * 1000
        loads.append(load)
        path.append((DEPOT["lat"], DEPOT["lon"]))
        legs = [(road_km(a, b), ld) for (a, b), ld in zip(zip(path, path[1:]), loads)]
        res = emissions_from_plan(legs, delivered_kg)
    else:
        route.actual_km = res["total_km"]
    route.fuel_l, route.co2e_wtw_kg = res["fuel_l"], res["co2e_wtw_kg"]
    route.co2e_per_ton_kg, route.co2_kg = res["co2e_kg_per_ton_husk"], res["co2e_wtw_kg"]
    route.emission_detail = res
    await db.flush()
    return res


# ---------------------------------------------------------------- retur
async def open_return(db: AsyncSession, actor: User, *, stage: str, reason_code: str, quantity_kg: float,
                      harvest_id: int | None = None, request_id: int | None = None, qc_id: int | None = None,
                      moisture: float | None = None, location: str = "pabrik", note: str | None = None,
                      evidence_photo_url: str | None = None) -> ReturnCase:
    rc = ReturnCase(harvest_id=harvest_id, request_id=request_id, qc_id=qc_id, stage=stage,
                    reason_code=ReturnReason(reason_code), moisture=moisture, quantity_kg=quantity_kg,
                    location=location, disposition=ReturnDisposition.PENDING, status="terbuka",
                    evidence_photo_url=evidence_photo_url, note=note, opened_by_id=actor.id)
    db.add(rc)
    await db.flush()
    return rc


def reason_from_quality(moisture: float | None, contamination: float | None) -> str:
    if moisture is not None and moisture > P("harga_mutu.moisture_reject"):
        return ReturnReason.BASAH.value
    if contamination is not None and contamination > P("harga_mutu.contamination_reject"):
        return ReturnReason.KONTAMINAN.value
    return ReturnReason.LAINNYA.value


async def resolve_return(db: AsyncSession, actor: User, case_id: int, disposition: str, cost_bearer: str | None,
                         handling_cost_rp: float | None, note: str | None) -> ReturnCase:
    if disposition == ReturnDisposition.PENDING.value:
        raise ValueError("Pilih disposisi akhir (bukan 'menunggu').")
    res = await db.execute(update(ReturnCase).where(ReturnCase.id == case_id, ReturnCase.status == "terbuka")
                           .values(disposition=ReturnDisposition(disposition), cost_bearer=cost_bearer,
                                   handling_cost_rp=handling_cost_rp, resolution_note=note, status="selesai",
                                   resolved_by_id=actor.id, resolved_at=datetime.now(timezone.utc))
                           .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        if await db.get(ReturnCase, case_id) is None:
            raise LookupError("Kasus retur tidak ditemukan")
        raise TransitionConflict("Kasus retur sudah diselesaikan.")
    return (await db.execute(select(ReturnCase).where(ReturnCase.id == case_id)
                             .execution_options(populate_existing=True))).scalar_one()


def return_dict(r: ReturnCase) -> dict:
    return {"id": r.id, "harvest_id": r.harvest_id, "request_id": r.request_id, "qc_id": r.qc_id,
            "stage": r.stage, "reason_code": _v(r.reason_code), "moisture": r.moisture,
            "quantity_kg": r.quantity_kg, "location": r.location, "disposition": _v(r.disposition),
            "cost_bearer": r.cost_bearer, "handling_cost_rp": r.handling_cost_rp, "status": r.status,
            "note": r.note, "resolution_note": r.resolution_note, "evidence_photo_url": r.evidence_photo_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None}
