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
from ..models.route import Route, RouteStop, RouteStatus
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyStage
from ..services.custody import find_replay, load_harvest, transition

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
            "pickup_at": s.pickup_at.isoformat() if s.pickup_at else None,
        })

    completed_stops = sum(1 for s in stops if s.qr_scanned)
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
    if route.status != RouteStatus.PLANNED:
        raise HTTPException(400, "Rute sudah dimulai atau selesai")

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
    if stop.harvest_id:
        harvest = await load_harvest(db, stop.harvest_id)
        if harvest.qr_code != req.qr_code:
            raise HTTPException(400, "QR code tidak cocok dengan harvest")
        await transition(
            db, harvest.id, HarvestStatus.VERIFIED, HarvestStatus.COLLECTED, user, CustodyStage.DRIVER_PICKUP,
            weight_kg=picked_kg, client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at,
            lat=req.lat, lon=req.lon, evidence_photo_url=req.photo_url,
            picked_up_kg=picked_kg, collected_at=datetime.now(timezone.utc),
        )

    stop.qr_scanned = True
    stop.pickup_at = req.client_recorded_at or datetime.now(timezone.utc)
    stop.actual_ton = req.actual_ton if req.actual_ton is not None else stop.planned_ton
    stop.lat_arrived = req.lat
    stop.lon_arrived = req.lon
    stop.pickup_photo = req.photo_url

    return {
        "message": "✅ Pickup dikonfirmasi!",
        "stop_id": stop.id,
        "stop_order": stop.stop_order,
        "already_confirmed": False,
    }


@router.post("/complete-route")
async def complete_route(
    route_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.DRIVER))],
):
    """Selesaikan rute setelah semua pickup dikonfirmasi."""
    result = await db.execute(
        select(Route).where(Route.id == route_id, Route.driver_id == user.id)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Rute tidak ditemukan")
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(409, f"Rute berstatus '{route.status.value}', tidak bisa diselesaikan.")
    pending = (await db.execute(
        select(RouteStop.stop_order).where(RouteStop.route_id == route.id, RouteStop.qr_scanned.is_(False))
    )).scalars().all()
    if pending:
        raise HTTPException(409, f"Masih ada stop yang belum di-scan: {sorted(pending)}")

    route.status = RouteStatus.COMPLETED
    route.completed_at = datetime.now(timezone.utc)

    return {"message": "🎉 Rute selesai! Terima kasih.", "route_id": route.id}
