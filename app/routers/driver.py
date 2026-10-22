import uuid
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.route import Route, RouteStop, RouteStatus, StopStatus
from ..models.harvest import Harvest, HarvestStatus
from ..models.circular import BiocharDistribution, BiocharRequest
from ..models.ledger import CustodyEvent, CustodyStage
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
    model_config = ConfigDict(extra="ignore")

    client_point_id: str | None = Field(None, max_length=64)
    recorded_at: datetime | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=100_000)
    speed_mps: float | None = Field(None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: any):
        if isinstance(data, dict):
            if not data.get("client_point_id"):
                data["client_point_id"] = f"pt_{uuid.uuid4().hex[:12]}"
            if not data.get("recorded_at"):
                data["recorded_at"] = datetime.now(timezone.utc)
        return data


class TrackUpload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    route_id: int
    points: list[TrackPointIn] = Field(default_factory=list, max_length=2000)
    # Flexible single ping GPS support
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    accuracy_m: float | None = None
    speed_mps: float | None = None

    @model_validator(mode="before")
    @classmethod
    def wrap_single_point(cls, data: any):
        if isinstance(data, dict):
            pts = data.get("points")
            if not pts:
                if data.get("lat") is not None and data.get("lon") is not None:
                    data["points"] = [{
                        "client_point_id": data.get("client_point_id") or f"pt_{uuid.uuid4().hex[:12]}",
                        "recorded_at": data.get("recorded_at") or datetime.now(timezone.utc),
                        "lat": data["lat"],
                        "lon": data["lon"],
                        "accuracy_m": data.get("accuracy_m"),
                        "speed_mps": data.get("speed_mps"),
                    }]
                else:
                    data["points"] = []
        return data


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
        .where(Route.logistics_carrier == "FACTORY_FLEET")
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
    com_map = {}
    if harvest_ids:
        h_rows = (await db.execute(select(Harvest.id, Harvest.qr_code, Harvest.commodity)
                                  .where(Harvest.id.in_(harvest_ids)))).all()
        qr_map = {r[0]: r[1] for r in h_rows}
        com_map = {r[0]: r[2] for r in h_rows}

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
            "commodity": com_map.get(s.harvest_id, "sekam_padi"),
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
    if getattr(route, "logistics_carrier", "FACTORY_FLEET") != "FACTORY_FLEET":
        raise HTTPException(403, "Rute ini adalah armada mandiri pengepul (COLLECTOR_SELF) dan tidak dapat dieksekusi oleh driver armada pabrik.")
    if route.status == RouteStatus.IN_PROGRESS:
        return {"message": "Rute sudah berjalan.", "route_id": route.id, "already_started": True}
    if route.status != RouteStatus.PLANNED:
        raise HTTPException(409, f"Rute berstatus '{route.status.value}', tidak bisa dimulai.")

    route.status = RouteStatus.IN_PROGRESS
    route.started_at = datetime.now(timezone.utc)

    return {"message": "🚛 Rute dimulai! Selamat berkendara.", "route_id": route.id}


@router.get("/job-inbox")
async def get_driver_job_inbox(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Inbox penugasan armada pabrik (Factory Fleet Only).
    Hanya penugasan berstatus 'FACTORY_FLEET' (Diambil oleh Pabrik) yang tampil di sini.
    """
    routes = (await db.execute(
        select(Route)
        .where(Route.driver_id == user.id)
        .where(Route.logistics_carrier == "FACTORY_FLEET")
        .order_by(Route.id.desc())
        .limit(20)
    )).scalars().all()

    items = []
    for r in routes:
        stops = (await db.execute(
            select(RouteStop, Harvest)
            .outerjoin(Harvest, Harvest.id == RouteStop.harvest_id)
            .where(RouteStop.route_id == r.id)
            .order_by(RouteStop.stop_order)
        )).all()
        commodities = list({h.commodity for s, h in stops if h and h.commodity})
        comm_name = commodities[0].replace("_", " ").title() if commodities else "Biomassa"

        items.append({
            "route_id": r.id,
            "trip_code": f"TRIP-{r.id:04d}",
            "vehicle_plate": r.vehicle_plate,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "carrier": r.logistics_carrier,
            "commodity": comm_name,
            "commodity_code": commodities[0] if commodities else None,
            "total_ton": r.total_ton,
            "total_km": r.total_km,
            "stops_count": len(stops),
            "planned_at": r.planned_at.isoformat() if r.planned_at else None,
        })
    return items


@router.post("/confirm-pickup")
async def confirm_pickup(
    req: PickupConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Konfirmasi pengambilan biomassa di satu stop via QR scan.

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
    """Supir tiba tetapi biomassa tidak bisa diambil (stok tidak ada, dibatalkan, basah, jalan putus).
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
    if not req.points:
        raise HTTPException(422, "Minimal sertakan satu titik GPS (points[] atau lat/lon)")
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


# ---------------------------------------------------------------- Omni 022: QR Checkpoint Verification & Reverse Logistics
class CheckpointScanRequest(BaseModel):
    qr_token: str = Field(..., min_length=4)
    checkpoint_type: str = Field("PICKUP", pattern="^(PICKUP|FACTORY_INBOUND|FACTORY_OUTBOUND|FARMER_DROP)$")
    lat: float | None = None
    lon: float | None = None
    notes: str | None = None


class BackhaulDropConfirm(BaseModel):
    distribution_id: int
    farmer_id: int | None = None
    delivered_kg: float = Field(..., gt=0)
    evidence_photo_url: EvidenceUrl | None = None
    notes: str | None = None


@router.post("/checkpoint-scan")
async def checkpoint_scan(
    req: CheckpointScanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER, UserRole.PENGEPUL))],
):
    """Verifikasi QR Code checkpoint di titik jemput, gerbang pabrik, atau serah terima muatan balik.

    Mendukung validasi dua arah: token biomassa masuk (Harvest) dan token muatan balik abu bottom ash (BiocharDistribution).
    """
    token = req.qr_token.strip()
    now = datetime.now(timezone.utc)

    # 1. Coba cocokkan dengan token panen biomassa
    harvest = (await db.execute(
        select(Harvest).where((Harvest.qr_verification_token == token) | (Harvest.qr_code == token))
    )).scalar_one_or_none()

    if harvest:
        farmer = await db.get(User, harvest.farmer_id) if harvest.farmer_id else None
        db.add(CustodyEvent(
            harvest_id=harvest.id,
            stage=CustodyStage.DRIVER_PICKUP.value if req.checkpoint_type == "PICKUP" else CustodyStage.FACTORY_RECEIVE.value,
            from_status=harvest.status.value,
            to_status=harvest.status.value,
            weight_kg=harvest.actual_weighed_qty or harvest.verified_kg or harvest.quantity_kg,
            actor_id=user.id,
            actor_role=user.role.value,
            lat=req.lat,
            lon=req.lon,
            note=f"QR Checkpoint [{req.checkpoint_type}]: Token valid. {req.notes or ''}".strip(),
        ))
        await db.flush()
        return {
            "success": True,
            "type": "HARVEST",
            "harvest_id": harvest.id,
            "commodity": harvest.commodity or "sekam_padi",
            "farmer_name": farmer.full_name if farmer else f"Petani #{harvest.farmer_id}",
            "claimed_qty": harvest.farmer_claimed_qty or harvest.quantity_kg,
            "actual_weighed_qty": harvest.actual_weighed_qty or harvest.verified_kg,
            "status": harvest.status.value,
            "checkpoint": req.checkpoint_type,
            "message": f"✅ Checkpoint {req.checkpoint_type} biomassa terverifikasi.",
        }

    # 2. Coba cocokkan dengan token muatan balik abu bottom ash
    distribution = (await db.execute(
        select(BiocharDistribution).where((BiocharDistribution.qr_dispatch_token == token) | (BiocharDistribution.dispatch_code == token))
    )).scalar_one_or_none()

    if distribution:
        if req.checkpoint_type == "FARMER_DROP":
            distribution.status = "DELIVERED_TO_FARMER"
            distribution.completed_at = now
            await db.flush()
        return {
            "success": True,
            "type": "BIOCHAR_BACKHAUL",
            "distribution_id": distribution.id,
            "dispatch_code": distribution.dispatch_code,
            "vehicle_plate": distribution.vehicle_plate,
            "total_weight_kg": distribution.total_weight_kg,
            "total_bags": distribution.total_bags,
            "status": distribution.status,
            "checkpoint": req.checkpoint_type,
            "message": f"✅ Checkpoint {req.checkpoint_type} muatan balik abu bottom ash terverifikasi.",
        }

    raise HTTPException(404, "QR token tidak valid atau tidak terdaftar di sistem.")


@router.get("/backhaul-tasks")
async def backhaul_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER, UserRole.PENGEPUL))],
):
    """Daftar penugasan muatan balik abu bottom ash dari pabrik untuk diantar ke petani/pengepul."""
    rows = (await db.execute(
        select(BiocharDistribution)
        .where((BiocharDistribution.driver_id == user.id) | (BiocharDistribution.driver_id.is_(None)))
        .order_by(BiocharDistribution.id.desc())
        .limit(50)
    )).scalars().all()
    return [
        {
            "id": d.id,
            "dispatch_code": d.dispatch_code,
            "vehicle_plate": d.vehicle_plate,
            "total_bags": d.total_bags,
            "total_weight_kg": d.total_weight_kg,
            "volume_m3": d.volume_m3,
            "loading_instructions": d.loading_instructions,
            "qr_dispatch_token": d.qr_dispatch_token,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]


@router.post("/confirm-backhaul-drop")
async def confirm_backhaul_drop(
    req: BackhaulDropConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Konfirmasi penyerahan muatan balik abu bottom ash ke sawah/lokasi petani."""
    dist = (await db.execute(select(BiocharDistribution).where(BiocharDistribution.id == req.distribution_id))).scalar_one_or_none()
    if not dist:
        raise HTTPException(404, "Distribusi abu bottom ash tidak ditemukan")

    dist.status = "DELIVERED_TO_FARMER"
    dist.completed_at = datetime.now(timezone.utc)
    if req.evidence_photo_url:
        dist.slip_url = req.evidence_photo_url

    # Update status linked BiocharRequests if applicable
    if req.farmer_id:
        b_req = (await db.execute(
            select(BiocharRequest)
            .where(BiocharRequest.farmer_id == req.farmer_id, BiocharRequest.status.in_(["REQUESTED", "ALLOCATED", "LOADED_BACKHAUL"]))
            .order_by(BiocharRequest.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        if b_req:
            b_req.status = "DELIVERED"
            b_req.delivered_at = datetime.now(timezone.utc)

    await db.flush()
    return {
        "success": True,
        "distribution_id": dist.id,
        "status": dist.status,
        "delivered_kg": req.delivered_kg,
        "message": f"✅ Muatan balik abu bottom ash {req.delivered_kg} kg berhasil diserahkan ke petani."
    }
