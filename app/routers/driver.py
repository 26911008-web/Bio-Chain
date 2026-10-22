"""Router: Driver (🚛) — Endpoints khusus driver logistik."""

from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.route import Route, RouteStop, RouteStatus, StopStatus
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyStage
from ..services import logistics, qr_sign
from ..services.custody import find_replay, load_harvest, transition, trusted_device_time

from ..security.url import EvidenceUrl

router = APIRouter()


class PickupConfirmRequest(BaseModel):
    route_stop_id: int
    qr_code: str
    actual_ton: float | None = Field(None, ge=0, le=50, description="Catatan supir; bukan timbangan resmi")
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = Field(None, description="Waktu scan di perangkat (bisa saat offline)")


class StopFailRequest(BaseModel):
    route_stop_id: int
    reason: str = Field(..., pattern="^(stok_tidak_ada|dibatalkan_pengepul|mutu_buruk|akses_jalan|"
                                     "penggilingan_tutup|truk_penuh|lainnya)$")
    note: str | None = Field(None, max_length=500)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    client_event_id: str | None = Field(None, max_length=64)
    client_recorded_at: datetime | None = None


class TrackPointIn(BaseModel):
    client_point_id: str = Field(..., min_length=8, max_length=64)
    recorded_at: datetime
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=100_000)
    speed_mps: float | None = Field(None, ge=0, le=100)


class TrackUpload(BaseModel):
    route_id: int
    points: list[TrackPointIn] = Field(..., min_length=1, max_length=2000)


@router.get("/active-route")
async def get_active_route(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Ambil rute aktif yang sedang berjalan untuk driver ini."""
    result = await db.execute(
        select(Route)
        .where(Route.driver_id == user.id)
        .where(Route.status.in_([RouteStatus.PLANNED, RouteStatus.IN_PROGRESS]))
        .order_by(Route.planned_at.desc())
        .limit(1)
    )
    route = result.scalar_one_or_none()
    if not route:
        return {"active": False, "message": "Tidak ada rute aktif saat ini."}

    # Load stops with mill details
    stops_result = await db.execute(
        select(RouteStop)
        .where(RouteStop.route_id == route.id)
        .order_by(RouteStop.stop_order)
    )
    stops = stops_result.scalars().all()

    # H2 fix: Batch-load all mills in a single query instead of N+1
    from ..models.harvest import Mill
    mill_ids = list({s.mill_id for s in stops if s.mill_id})
    mills_map = {}
    if mill_ids:
        mills_result = await db.execute(select(Mill).where(Mill.id.in_(mill_ids)))
        mills_map = {m.id: m for m in mills_result.scalars().all()}

    harvest_ids = [s.harvest_id for s in stops if s.harvest_id]
    qr_map = {}
    if harvest_ids:
        qr_map = dict((await db.execute(select(Harvest.id, Harvest.qr_code)
                                        .where(Harvest.id.in_(harvest_ids)))).all())

    stop_list = []
    for s in stops:
        mill_info = None
        if s.mill_id:
            m = mills_map.get(s.mill_id)
            if m:
                mill_info = {"id": m.id, "name": m.name, "kecamatan": m.kecamatan, "lat": m.lat, "lon": m.lon}

        stop_list.append({
            "id": s.id,
            "order": s.stop_order,
            "mill_id": s.mill_id,
            "mill": mill_info,
            "planned_ton": s.planned_ton,
            "actual_ton": s.actual_ton,
            "picked_up": s.qr_scanned,
            "stop_status": s.stop_status,
            "fail_reason": s.fail_reason,
            "pickup_at": s.pickup_at.isoformat() if s.pickup_at else None,
            # F14: digest satu arah → HP supir mencocokkan QR di lokasi walau tanpa sinyal (kode QR tidak dikirim)
            "qr_check": qr_sign.offline_check(qr_map.get(s.harvest_id), s.id) if s.harvest_id else None,
        })

    completed_stops = sum(1 for s in stops if s.stop_status != StopStatus.PENDING.value)
    status_str = route.status.value if hasattr(route.status, 'value') else str(route.status)

    return {
        "active": True,
        "route_id": route.id,
        "status": status_str,
        "total_km": route.total_km,
        "total_stops": len(stops),
        "completed_stops": completed_stops,
        "estimated_hours": route.estimated_hours,
        "vehicle_plate": route.vehicle_plate,
        "utilization_pct": route.utilization_pct,
        "stops": stop_list,
    }


@router.post("/start-route")
async def start_route(
    route_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Mulai rute (ubah status ke IN_PROGRESS)."""
    result = await db.execute(
        select(Route).where(Route.id == route_id, Route.driver_id == user.id)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Rute tidak ditemukan")
    if route.status == RouteStatus.IN_PROGRESS:
        return {"message": "Rute sudah berjalan.", "route_id": route.id, "already_started": True}
    if route.status != RouteStatus.PLANNED:
        raise HTTPException(409, f"Rute berstatus '{route.status.value}', tidak bisa dimulai.")

    route.status = RouteStatus.IN_PROGRESS
    route.started_at = datetime.now(timezone.utc)

    return {"message": "🚛 Rute dimulai! Selamat berkendara.", "route_id": route.id}


@router.post("/confirm-pickup")
async def confirm_pickup(
    req: PickupConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Konfirmasi pengambilan sekam di satu stop via QR scan.

    Hanya stop milik rute supir ini yang sedang berjalan. Berat dari supir disimpan sebagai catatan
    (picked_up_kg); angka otoritatif tetap timbangan pengepul & pabrik. Aman diulang (offline replay).
    """
    stop = (await db.execute(
        select(RouteStop).join(Route, RouteStop.route_id == Route.id)
        .where(RouteStop.id == req.route_stop_id, Route.driver_id == user.id)
    )).scalar_one_or_none()
    if not stop:
        raise HTTPException(404, "Stop tidak ditemukan pada rute Anda")
    route = (await db.execute(select(Route).where(Route.id == stop.route_id))).scalar_one()

    if stop.stop_status in (StopStatus.FAILED.value, StopStatus.CANCELLED.value):
        raise HTTPException(409, f"Stop ini sudah '{stop.stop_status}' ({stop.fail_reason}); jangan dimuat.")
    if stop.qr_scanned or await find_replay(db, req.client_event_id):
        return {
            "message": "ℹ️ Pickup stop ini sudah dikonfirmasi sebelumnya.",
            "stop_id": stop.id,
            "stop_order": stop.stop_order,
            "already_confirmed": True,
        }
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(409, "Mulai rute terlebih dahulu sebelum konfirmasi pickup.")

    picked_kg = req.actual_ton * 1000 if req.actual_ton is not None else None
    geo_note, geo_m = None, None
    if req.lat is not None and req.lon is not None and stop.mill_id:
        from ..engines.emission import haversine_km
        from ..models.harvest import Mill
        from ..params import P
        mill = await db.get(Mill, stop.mill_id)
        if mill is not None:
            geo_m = round(haversine_km((req.lat, req.lon), (mill.lat, mill.lon)) * 1000)
            if geo_m > P("logistik.pickup_geofence_m"):
                geo_note = f"GEOFENCE: scan {geo_m} m dari titik penggilingan (batas {P('logistik.pickup_geofence_m'):g} m)"
    if stop.harvest_id:
        harvest = await load_harvest(db, stop.harvest_id)
        verdict = qr_sign.check_scan(req.qr_code, harvest.qr_code)
        if verdict == "tidak_sah":
            raise HTTPException(400, "QR tidak sah: tanda tangan tidak cocok (QR palsu atau salah ketik). Scan ulang QR asli.")
        if verdict == "beda_lot":
            raise HTTPException(400, "QR code tidak cocok dengan harvest")
        if verdict == "ok_legacy":
            from ..params import P
            if P("logistik.qr_legacy_policy") == "tolak":
                raise HTTPException(400, "QR lama (tanpa tanda tangan) tidak lagi diterima. Minta pengepul/petani "
                                         "membuka lot ini di aplikasi dan menunjukkan QR baru.")
            geo_note = "; ".join(filter(None, [geo_note, "QR_LAMA: QR tanpa tanda tangan (sebelum F14)"]))
        await transition(
            db, harvest.id, HarvestStatus.VERIFIED, HarvestStatus.COLLECTED, user, CustodyStage.DRIVER_PICKUP,
            weight_kg=picked_kg, client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at,
            lat=req.lat, lon=req.lon, evidence_photo_url=req.photo_url, note=geo_note,
            picked_up_kg=picked_kg, collected_at=datetime.now(timezone.utc),
        )

    stop.qr_scanned = True
    stop.stop_status = StopStatus.PICKED_UP.value
    stop.pickup_at = trusted_device_time(req.client_recorded_at)[0]
    stop.actual_ton = req.actual_ton if req.actual_ton is not None else stop.planned_ton
    stop.lat_arrived = req.lat
    stop.lon_arrived = req.lon
    stop.pickup_photo = req.photo_url

    return {
        "message": "✅ Pickup dikonfirmasi!" + (" ⚠️ Lokasi scan jauh dari penggilingan — ditandai untuk auditor."
                                                 if geo_note else ""),
        "stop_id": stop.id,
        "stop_order": stop.stop_order,
        "already_confirmed": False,
        "distance_to_mill_m": geo_m,
        "geofence_flag": geo_note is not None,
    }


@router.post("/stop-failed")
async def report_stop_failed(
    req: StopFailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Supir tiba tetapi sekam tidak bisa diambil (stok tidak ada, dibatalkan, basah, jalan putus).
    Stop ditutup sebagai GAGAL sehingga rute tetap bisa diselesaikan; panen kembali ke antrean pabrik."""
    return await logistics.fail_stop(db, user, req.route_stop_id, req.reason, req.note, req.lat, req.lon,
                                     req.client_recorded_at)


@router.post("/track")
async def upload_track(
    req: TrackUpload,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Unggah titik GPS yang direkam perangkat (juga saat offline). Idempoten per `client_point_id`:
    batch yang terkirim ulang tidak menggandakan titik. Jejak yang tiba setelah rute selesai memicu
    perhitungan ulang jarak & emisi."""
    return await logistics.ingest_track(db, user, req.route_id, [p.model_dump() for p in req.points])


@router.post("/complete-route")
async def complete_route(
    route_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Selesaikan rute bila tidak ada stop yang masih menunggu (dijemput, gagal, atau dibatalkan).
    Jarak nyata & emisi CO₂e (ISO 14083) dihitung dari jejak GPS yang sudah tersinkron."""
    result = await db.execute(
        select(Route).where(Route.id == route_id, Route.driver_id == user.id)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Rute tidak ditemukan")
    if route.status == RouteStatus.COMPLETED:
        return {"message": "Rute sudah selesai sebelumnya.", "route_id": route.id, "already_completed": True,
                "emissions": route.emission_detail}
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(409, f"Rute berstatus '{route.status.value}', tidak bisa diselesaikan.")
    pending = (await db.execute(
        select(RouteStop.stop_order).where(RouteStop.route_id == route.id,
                                           RouteStop.stop_status == StopStatus.PENDING.value)
    )).scalars().all()
    if pending:
        raise HTTPException(409, f"Masih ada stop yang belum di-scan atau dilaporkan gagal: {sorted(pending)}")

    route.status = RouteStatus.COMPLETED
    route.completed_at = datetime.now(timezone.utc)
    emissions = await logistics.finalize_route_emissions(db, route)
    return {"message": "🎉 Rute selesai! Terima kasih.", "route_id": route.id, "already_completed": False,
            "emissions": {k: emissions[k] for k in ("distance_source", "total_km", "empty_km", "fuel_l",
                                                    "co2e_wtw_kg", "co2e_kg_per_ton_husk", "intensity_g_per_tkm")}}
