"""Router: Pabrik (🏭) — Endpoints analytics-heavy untuk pabrik/end-user."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.circular import BiocharDistribution, BiocharRequest
from ..models.conversion import CarbonCredit
from ..engines.carbon import CarbonInput, calculate_carbon_reduction
from ..engines.forecaster import ForecastInput, forecast_supply
from ..engines.quality import FeedstockSample, biochar_yield_db, score_sample, yield_curve
from ..engines.blending import BlendRequest, default_feedstocks, optimize_blend
from ..engines.factory_econ import LOSS_KINDS
from ..params import P
from ..models.ledger import CustodyStage
from ..models.route import LIVE_STOP_STATUSES, Route, RouteStop, RouteStatus
from ..models.harvest import Mill
from ..models.factory_ops import ReturnCase
from ..services import logistics
from ..concurrency import run_cpu
from ..data import DEPOT
from ..engines.energy import EnergyAnalysisRequest, analyze as analyze_energy
from ..models.energy import EnergyMeterReading
from ..engines.factory_econ import PricingRequest, recommend_price
from ..models.factory_ops import (
    CollectorSettlement, DeliveryRequest, InboundQC, ManufacturingBatch,
    QCDecision, RequestStatus, ReturnCase, ReturnReason, ReturnDisposition
)
from ..services import factory_ops
from ..services.custody import convert_and_allocate, load_harvest, mass_balance, shrinkage_fields, transition
from ..security.url import EvidenceUrl

router = APIRouter()

_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)
# Aksi yang mengubah timbangan / stok hanya oleh operator pabrik (admin tidak, demi pemisahan tugas).
_pabrik_only = require_role(UserRole.PABRIK)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)


class EnergyReadingIn(BaseModel):
    facility: str = Field(..., min_length=2, max_length=100)
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    kwh: float = Field(..., ge=0)
    building_kwh: float | None = Field(None, ge=0)
    production_ton: float = Field(0, ge=0)
    peak_kw: float | None = Field(None, ge=0)
    operating_hours: float | None = Field(None, gt=0, le=744)
    cost_rp: float | None = Field(None, ge=0)
    floor_area_m2: float = Field(..., gt=0)
    building_type: str = Field("ac", pattern="^(ac|non_ac)$")
    note: str | None = Field(None, max_length=500)


class DispatchRequest(BaseModel):
    driver_id: int
    harvest_ids: list[int] = Field(..., min_length=1, max_length=50)
    vehicle_plate: str | None = Field(None, max_length=20)
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0, le=200)
    vehicle_payload_kg: float | None = Field(None, gt=0, le=40_000,
                                             description="Muatan maksimum truk ini; kosong = parameter logistik")
    logistics_carrier: str = Field("FACTORY_FLEET", pattern="^(FACTORY_FLEET|COLLECTOR_SELF)$")


class FleetVehicle(BaseModel):
    driver_id: int
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0, le=200)
    vehicle_payload_kg: float | None = Field(None, gt=0, le=40_000, description="Kosong = parameter logistik")
    vehicle_plate: str | None = Field(None, max_length=20)


class FleetDispatchRequest(BaseModel):
    harvest_ids: list[int] = Field(..., min_length=1, max_length=200)
    vehicles: list[FleetVehicle] = Field(..., min_length=1, max_length=30)
    time_limit_ms: int = Field(1000, ge=100, le=10_000)
    commit: bool = Field(False, description="False = pratinjau rencana; True = buat rute & tugaskan supir")


class RouteCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ReturnOpenRequest(BaseModel):
    harvest_id: int | None = None
    request_id: int | None = None
    qc_id: int | None = None
    reason_code: str = Field(..., pattern="^(basah|berjamur|kontaminan|selisih_berat|stok_tidak_ada|"
                                          "dibatalkan_pengepul|lainnya)$")
    quantity_kg: float = Field(..., gt=0, le=1_000_000)
    moisture: float | None = Field(None, ge=0, le=95)
    location: str = Field("pabrik", pattern="^(pabrik|pengepul|petani)$")
    note: str | None = Field(None, max_length=500)
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000)


class ReturnResolveRequest(BaseModel):
    disposition: str = Field(..., pattern="^(kembalikan_ke_pengirim|keringkan_ulang|turun_grade|"
                                          "bahan_bakar_boiler|musnahkan)$")
    cost_bearer: str | None = Field(None, pattern="^(petani|pengepul|pabrik)$")
    handling_cost_rp: float | None = Field(None, ge=0, le=1e10)
    note: str | None = Field(None, max_length=500)


class GoodsMovementRequest(BaseModel):
    product: str = Field(..., pattern="^(bio_pellet|biochar|bio_silika)$")
    movement: str = Field(..., pattern="^(penjualan|penyesuaian|retur_pelanggan)$")
    quantity_kg: float = Field(..., description="penjualan/retur: kg positif; penyesuaian: bertanda (+/-)")
    unit_price_rp: float | None = Field(None, ge=0)
    reference: str | None = Field(None, max_length=80, description="No. DO / faktur / berita acara")
    note: str | None = Field(None, max_length=500)


class ReceiveRequest(BaseModel):
    harvest_id: int
    received_kg: float = Field(..., gt=0, le=50000, description="Timbangan jembatan pabrik (otoritatif)")
    client_event_id: str | None = Field(None, max_length=64)
    note: str | None = Field(None, max_length=500)
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    price_per_kg: float | None = Field(None, ge=0, le=20_000,
                                       description="Harga beli ke pengepul (Rp/kg). Kosong = rekomendasi netback engine")


class FactoryRejectRequest(BaseModel):
    harvest_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    reason_code: str = Field("lainnya", pattern="^(basah|berjamur|kontaminan|selisih_berat|lainnya)$")
    moisture: float | None = Field(None, ge=0, le=95, description="Kadar air terukur di gerbang (bukti retur)")
    weighed_kg: float | None = Field(None, gt=0)
    client_event_id: str | None = Field(None, max_length=64)


class ConversionRequest(BaseModel):
    batch_code: str = Field(..., min_length=3, max_length=50)
    harvest_ids: list[int] = Field(..., min_length=1, max_length=500)
    biochar_kg: float = Field(..., gt=0)
    pyrolysis_temp_c: float | None = Field(None, ge=300, le=900)
    farmer_return_share: float | None = Field(None, ge=0, le=1,
                                              description="Default: menu Parameter → sirkular.farmer_return_share")


@router.post("/dispatch", status_code=201)
async def dispatch_route(
    req: DispatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Buat rute penjemputan untuk harvest terverifikasi dan tugaskan ke supir."""
    driver = (await db.execute(select(User).where(User.id == req.driver_id))).scalar_one_or_none()
    if not driver or driver.role != UserRole.DRIVER or not driver.is_active:
        raise HTTPException(422, "driver_id bukan supir aktif")
    harvests = (await db.execute(select(Harvest).where(Harvest.id.in_(req.harvest_ids)))).scalars().all()
    bad = sorted(set(req.harvest_ids) - {h.id for h in harvests if h.status == HarvestStatus.VERIFIED})
    if bad:
        raise HTTPException(409, f"Hanya harvest berstatus 'verified' yang bisa dijadwalkan: {bad}")
    bad_dr = [h.id for h in harvests if h.delivery_request_id is not None]
    if bad_dr:
        raise HTTPException(409, f"Harvest {bad_dr} sudah terlampir Delivery Request — kirim lewat QC, bukan rute.")

    # Anti-Cross Contamination: Dilarang menggabungkan komoditas berbeda dalam satu trip
    commodities = {h.commodity for h in harvests if h.commodity}
    if len(commodities) > 1:
        raise HTTPException(
            422,
            f"Anti-Cross Contamination: Dilarang menggabungkan komoditas berbeda dalam 1 armada ({', '.join(sorted(commodities))}). "
            "Gunakan trip terpisah per jenis komoditas untuk menjaga kemurnian mutu pirolisis."
        )

    await _ensure_not_scheduled(db, req.harvest_ids)
    order = {hid: i for i, hid in enumerate(req.harvest_ids)}
    harvests = sorted(harvests, key=lambda h: order[h.id])
    route = await _create_route(db, driver, harvests, req.vehicle_plate, req.vehicle_m3, optimizer="manual",
                                payload_kg=req.vehicle_payload_kg, logistics_carrier=req.logistics_carrier)
    stops = (await db.execute(
        select(RouteStop).where(RouteStop.route_id == route.id).order_by(RouteStop.stop_order)
    )).scalars().all()
    return {"route_id": route.id, "driver_id": driver.id, "planned_km": route.total_km,
            "planned_co2e_kg": route.co2_kg,
            "stops": [{"route_stop_id": st.id, "harvest_id": st.harvest_id, "order": st.stop_order} for st in stops]}


async def _ensure_not_scheduled(db: AsyncSession, harvest_ids: list[int]) -> None:
    busy = (await db.execute(
        select(RouteStop.harvest_id).where(RouteStop.harvest_id.in_(harvest_ids),
                                           RouteStop.stop_status.in_(LIVE_STOP_STATUSES))
    )).scalars().all()
    if busy:
        raise HTTPException(409, f"Harvest sudah ada di rute aktif: {sorted(busy)}")


def check_capacity(total_kg: float, vehicle_m3: float, payload_kg: float | None = None) -> None:
    """Biomassa ringan tapi memakan ruang: muatan dibatasi VOLUME bak (kg ÷ densitas curah) DAN berat (muatan truk).
    Melebihi salah satunya → 422 dengan saran (pecah rute / truk lebih besar)."""
    rho = P("logistik.bulk_density_kg_m3")
    cap_kg = payload_kg or P("logistik.vehicle_payload_kg")
    need_m3 = total_kg / rho
    problems = []
    if need_m3 > vehicle_m3 + 1e-6:
        problems.append(f"volume {need_m3:.1f} m³ > bak {vehicle_m3:g} m³ (densitas {rho:g} kg/m³)")
    if total_kg > cap_kg + 1e-6:
        problems.append(f"berat {total_kg:,.0f} kg > muatan maks {cap_kg:,.0f} kg")
    if problems:
        raise HTTPException(422, "Muatan melebihi kapasitas truk: " + "; ".join(problems)
                            + ". Pecah menjadi beberapa rute atau gunakan Dispatch Otomatis (OR-Tools).")


async def _create_route(db: AsyncSession, driver: User, harvests: list[Harvest], plate: str | None,
                        vehicle_m3: float, optimizer: str, payload_kg: float | None = None,
                        logistics_carrier: str = "FACTORY_FLEET") -> Route:
    """Buat rute + stop terurut; km & CO2e rencana dihitung dari koordinat penggilingan (estimasi jalan)."""
    from ..engines.emission import emissions_from_plan
    from ..engines.routing import road_km
    rho = P("logistik.bulk_density_kg_m3")
    total_kg = sum(h.verified_kg or h.quantity_kg for h in harvests)
    check_capacity(total_kg, vehicle_m3, payload_kg)
    route = Route(driver_id=driver.id, vehicle_plate=plate, status=RouteStatus.PLANNED, vehicle_m3=vehicle_m3,
                  bulk_density=rho, total_ton=round(total_kg / 1000, 3), total_m3=round(total_kg / rho, 2),
                  utilization_pct=round(100 * total_kg / rho / vehicle_m3, 1), optimizer=optimizer,
                  logistics_carrier=logistics_carrier)
    db.add(route)
    await db.flush()
    mills = {m.id: m for m in (await db.execute(
        select(Mill).where(Mill.id.in_([h.mill_id for h in harvests if h.mill_id])))).scalars().all()}
    path, legs, load = [(DEPOT["lat"], DEPOT["lon"])], [], 0.0
    for i, h in enumerate(harvests, start=1):
        kg = h.verified_kg or h.quantity_kg
        db.add(RouteStop(route_id=route.id, harvest_id=h.id, mill_id=h.mill_id, stop_order=i,
                         planned_ton=round(kg / 1000, 3), planned_m3=round(kg / rho, 2)))
        m = mills.get(h.mill_id)
        if m is not None:
            legs.append((road_km(path[-1], (m.lat, m.lon)), load))
            path.append((m.lat, m.lon))
        load += kg
    if len(path) > 1:
        legs.append((road_km(path[-1], path[0]), load))
        em = emissions_from_plan(legs, total_kg)
        route.total_km, route.co2_kg = round(em["total_km"], 2), em["co2e_wtw_kg"]
        route.total_cost = round(em["total_km"] * P("logistik.cost_per_km"))
    try:
        await db.flush()
    except IntegrityError as e:          # dispatch serentak untuk harvest yang sama (indeks unik stop hidup)
        raise HTTPException(409, "Harvest baru saja dijadwalkan oleh operator lain - muat ulang.") from e
    return route


def _v_role(u: User) -> str:
    return u.role.value if hasattr(u.role, "value") else str(u.role)


@router.post("/dispatch/optimize")
async def dispatch_optimize(
    req: FleetDispatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Alokasi panen terverifikasi ke beberapa supir sekaligus dengan Google OR-Tools (CVRP kapasitas volume,
    objektif gram CO2e). `commit=false` = pratinjau; `commit=true` = rute dibuat & ditugaskan (khusus pabrik)."""
    from ..engines.routing_ortools import OrToolsUnavailable, solve_fleet
    if req.commit and _v_role(user) != UserRole.PABRIK.value:
        raise HTTPException(403, "Hanya operator pabrik yang dapat menugaskan rute.")
    driver_ids = [v.driver_id for v in req.vehicles]
    if len(driver_ids) != len(set(driver_ids)):
        raise HTTPException(422, "Satu supir hanya satu kendaraan per rencana.")
    drivers = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(driver_ids)))).scalars().all()}
    bad = [d for d in driver_ids if d not in drivers or drivers[d].role != UserRole.DRIVER or not drivers[d].is_active]
    if bad:
        raise HTTPException(422, f"Bukan supir aktif: {bad}")
    harvests = (await db.execute(select(Harvest).where(Harvest.id.in_(req.harvest_ids)))).scalars().all()
    bad = sorted(set(req.harvest_ids) - {h.id for h in harvests if h.status == HarvestStatus.VERIFIED
                                         and h.delivery_request_id is None})
    if bad:
        raise HTTPException(409, f"Hanya harvest 'verified' tanpa Delivery Request yang bisa dijadwalkan: {bad}")
    await _ensure_not_scheduled(db, req.harvest_ids)
    mills = {m.id: m for m in (await db.execute(
        select(Mill).where(Mill.id.in_([h.mill_id for h in harvests if h.mill_id])))).scalars().all()}
    no_loc = [h.id for h in harvests if h.mill_id not in mills]
    if no_loc:
        raise HTTPException(422, f"Harvest tanpa lokasi penggilingan tidak bisa dirutekan: {no_loc}")
    pts = [{"id": h.id, "lat": mills[h.mill_id].lat, "lon": mills[h.mill_id].lon,
            "kg": h.verified_kg or h.quantity_kg} for h in harvests]
    vehicles = [{"id": v.driver_id, "m3": v.vehicle_m3, "payload_kg": v.vehicle_payload_kg} for v in req.vehicles]
    try:
        plan = await run_cpu(solve_fleet, DEPOT, pts, vehicles, req.time_limit_ms)
    except OrToolsUnavailable as e:
        raise HTTPException(503, str(e)) from e
    if req.commit:
        by_id = {h.id: h for h in harvests}
        plates = {v.driver_id: v.vehicle_plate for v in req.vehicles}
        payloads = {v.driver_id: v.vehicle_payload_kg for v in req.vehicles}
        for r in plan["routes"]:
            route = await _create_route(db, drivers[r["vehicle_id"]], [by_id[i] for i in r["stops"]],
                                        plates.get(r["vehicle_id"]), r["vehicle_m3"], optimizer="ortools",
                                        payload_kg=payloads.get(r["vehicle_id"]))
            r["route_id"] = route.id
    plan["committed"] = req.commit
    return plan


@router.get("/routes")
async def list_routes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    status: str | None = None,
    limit: int = 50,
):
    """Pantau rute: status stop (dijemput/gagal/batal), km rencana vs GPS, BBM & CO2e."""
    q = select(Route).order_by(Route.id.desc()).limit(min(max(limit, 1), 200))
    if status:
        q = q.where(Route.status == status)
    routes = (await db.execute(q)).scalars().all()
    stops = (await db.execute(select(RouteStop).where(RouteStop.route_id.in_([r.id for r in routes]))
                              .order_by(RouteStop.stop_order))).scalars().all() if routes else []
    by_route: dict[int, list] = {}
    for st in stops:
        by_route.setdefault(st.route_id, []).append(
            {"id": st.id, "order": st.stop_order, "harvest_id": st.harvest_id, "status": st.stop_status,
             "fail_reason": st.fail_reason, "fail_note": st.fail_note, "planned_ton": st.planned_ton})
    return [{"route_id": r.id, "driver_id": r.driver_id,
             "status": r.status.value if hasattr(r.status, "value") else r.status,
             "optimizer": r.optimizer, "planned_km": r.total_km, "actual_km": r.actual_km, "fuel_l": r.fuel_l,
             "co2e_wtw_kg": r.co2e_wtw_kg, "co2e_kg_per_ton_husk": r.co2e_per_ton_kg,
             "cancel_reason": r.cancel_reason, "stops": by_route.get(r.id, [])} for r in routes]


@router.post("/routes/{route_id}/cancel")
async def cancel_route(
    route_id: int,
    body: RouteCancelRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Batalkan rute: stop yang belum dijemput dibatalkan (panen kembali ke antrean). Muatan yang sudah naik
    tetap diantar supir ke pabrik."""
    return await logistics.cancel_route(db, user, route_id, body.reason)


@router.post("/receive")
async def receive_harvest(
    req: ReceiveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Timbang terima di pabrik: COLLECTED → DELIVERED, hitung susut terhadap timbangan pengepul."""
    harvest = await load_harvest(db, req.harvest_id)
    reference = harvest.verified_kg or harvest.quantity_kg
    fields = shrinkage_fields(reference, req.received_kg)
    note = "; ".join(x for x in (fields["discrepancy_note"], req.note) if x) or None
    await transition(
        db, req.harvest_id, HarvestStatus.COLLECTED, HarvestStatus.DELIVERED, user, CustodyStage.FACTORY_RECEIVE,
        weight_kg=req.received_kg, client_event_id=req.client_event_id, note=note,
        evidence_photo_url=req.evidence_photo_url, received_by_id=user.id, delivered_at=datetime.now(timezone.utc), **fields,
    )
    # Jalur rute: catat kewajiban bayar ke pengepul (sebelumnya tidak tercatat → margin pengepul tidak lengkap)
    current_harvest = await load_harvest(db, req.harvest_id)
    settlement = await factory_ops.settle_route(db, current_harvest, user, req.price_per_kg)
    warning = ("Penerimaan biomassa tanpa pengepul: tidak ada tagihan pembayaran terbuat otomatis."
               if settlement is None and current_harvest.collector_id is None else None)
    return {
        "settlement": factory_ops.settlement_dict(settlement) if settlement else None,
        "warning": warning,
        "harvest_id": req.harvest_id, "status": "delivered", "reference_kg": reference,
        "received_kg": req.received_kg, "shrinkage_kg": fields["shrinkage_kg"],
        "shrinkage_pct": fields["shrinkage_pct"], "discrepancy_flag": fields["discrepancy_flag"],
        "computation_details": {
            "formula": "susut% = (timbangan_pengepul − timbangan_pabrik) / timbangan_pengepul × 100",
            "tolerance_pct": P("sirkular.shrinkage_tolerance_pct"),
            "flag_rule": "|susut%| > toleransi → ditandai untuk auditor (penerimaan tetap dicatat)",
        },
    }


@router.post("/reject")
async def factory_reject(
    req: FactoryRejectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Tolak muatan saat tiba: COLLECTED → REJECTED (atomik; bersaing aman dengan /receive)."""
    from ..services.custody import find_replay
    replay = await find_replay(db, req.client_event_id)
    await transition(
        db, req.harvest_id, HarvestStatus.COLLECTED, HarvestStatus.REJECTED, user, CustodyStage.FACTORY_REJECT,
        weight_kg=req.weighed_kg, client_event_id=req.client_event_id, note=req.reason,
        rejected_reason=req.reason, rejected_at=datetime.now(timezone.utc), received_kg=req.weighed_kg,
    )
    case = None
    if replay is None:
        h = await load_harvest(db, req.harvest_id)
        # Muatan ditolak tetap fisik di pabrik -> kasus retur (karantina) sampai diputuskan disposisinya
        case = await logistics.open_return(
            db, user, stage="gerbang_pabrik", harvest_id=h.id, reason_code=req.reason_code,
            quantity_kg=req.weighed_kg or h.verified_kg or h.quantity_kg, moisture=req.moisture, note=req.reason)
    return {"harvest_id": req.harvest_id, "status": "rejected",
            "return_case_id": case.id if case else None}


@router.post("/conversions", status_code=201)
async def create_conversion(
    req: ConversionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat batch pirolisis dan kreditkan abu bottom ash ke dompet petani pemasok (proporsional berat terima)."""
    share = P("sirkular.farmer_return_share") if req.farmer_return_share is None else req.farmer_return_share
    return await convert_and_allocate(db, user, req.harvest_ids, req.biochar_kg, req.batch_code, share,
                                      req.pyrolysis_temp_c)


@router.get("/mass-balance/{harvest_id}")
async def get_mass_balance(
    harvest_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Jejak berat & serah-terima satu harvest dari petani sampai alokasi abu bottom ash."""
    return await mass_balance(db, harvest_id)


@router.post("/carbon/calculate")
async def carbon_calculate(
    inp: CarbonInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Hitung pengurangan emisi CO₂ (IPCC Tier 2)."""
    return calculate_carbon_reduction(inp)


@router.post("/forecast")
async def supply_forecast(
    inp: ForecastInput,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Prediksi pasokan biomassa bulanan."""
    return forecast_supply(inp)


@router.get("/forecast/30d")
async def forecast_30_days(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    harvest_area_ha: float | None = None,
):
    """Proyeksi pasokan 30 hari ke depan."""
    from datetime import date, timedelta

    harvest_area_ha = P("proyeksi.harvest_area_ha") if harvest_area_ha is None else harvest_area_ha
    today = date.today()
    points = []
    for i in range(30):
        d = today + timedelta(days=i)
        inp = ForecastInput(
            harvest_area_ha=harvest_area_ha,
            month=d.month,
            year=d.year,
        )
        result = forecast_supply(inp)
        daily = result.predicted_supply_ton / 30  # rough daily estimate
        points.append({
            "date": d.isoformat(),
            "predicted": round(daily, 1),
            "pred_husk_ton": round(daily, 1),
            "low": round(result.confidence_low / 30, 1),
            "high": round(result.confidence_high / 30, 1),
        })
    return {
        "points": points,
        "harvest_area_ha": harvest_area_ha,
        "total_predicted_ton": round(sum(p["predicted"] for p in points), 1),
    }


@router.post("/quality/score")
async def quality_score(
    sample: FeedstockSample,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Evaluasi kualitas feedstock masuk."""
    return score_sample(sample)


@router.get("/quality/yield-curve")
async def quality_yield(
    user: Annotated[User, Depends(_pabrik_dep)],
    ash: float | None = None,
):
    """Kurva rendemen biochar vs suhu pirolisis (abu default = acuan di menu Parameter)."""
    return yield_curve(ash)


@router.post("/blend/recommend")
async def blend_recommend(
    req: BlendRequest,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Optimasi campuran feedstock (Engine ③)."""
    if not req.feedstocks:
        req.feedstocks = default_feedstocks()
    return optimize_blend(req)


@router.get("/biochar-redemptions")
async def biochar_redemptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    status: str = "diajukan",
):
    """Antrean pengambilan abu bottom ash petani untuk sawah."""
    from ..services.circular import list_redemptions
    return await list_redemptions(db, status)


class HandoverRequest(BaseModel):
    kg: float | None = Field(None, gt=0, le=100_000, description="Kg aktual diserahkan (default = diajukan)")
    note: str | None = Field(None, max_length=300)


@router.post("/biochar-redemptions/{redemption_id}/handover")
async def handover_biochar(
    redemption_id: int,
    body: HandoverRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Serahkan karung abu bottom ash ke petani → ledger redemption (negatif) ditulis sekarang."""
    from ..services.circular import handover
    return await handover(db, user, redemption_id, body.kg, body.note)


# → factory_esg.py: ESG, klaim karbon, efisiensi & biaya tambahan pabrik.

@router.get("/supply/overview")
async def supply_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Overview supply saat ini dari semua petani."""
    result = await db.execute(
        select(
            Harvest.status,
            func.count(Harvest.id),
            func.sum(Harvest.quantity_kg),
        )
        .group_by(Harvest.status)
    )
    rows = result.all()
    return {
        "by_status": [
            {"status": r[0].value if hasattr(r[0], "value") else str(r[0]), "count": r[1], "total_kg": round(r[2] or 0, 1)}
            for r in rows
        ]
    }


# ---------------------------------------------------------------- ⑩ Energi (histori dari database)
@router.get("/energy/facilities")
async def energy_facilities(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    rows = (await db.execute(
        select(EnergyMeterReading.facility, func.count(EnergyMeterReading.id),
               func.min(EnergyMeterReading.period), func.max(EnergyMeterReading.period))
        .group_by(EnergyMeterReading.facility))).all()
    return [{"facility": f, "months": n, "from": a, "to": b} for f, n, a, b in rows]


@router.get("/energy/analysis")
async def energy_analysis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    facility: str | None = None,
    months: int = 24,
    baseline_months: int = 12,
):
    """IKE, SEC, baseline ISO 50006, anomali/pemborosan & rekomendasi dari histori di database."""
    if facility is None:   # default deterministik: fasilitas dengan histori terpanjang
        facility = (await db.execute(
            select(EnergyMeterReading.facility).group_by(EnergyMeterReading.facility)
            .order_by(func.count(EnergyMeterReading.id).desc(), EnergyMeterReading.facility).limit(1)
        )).scalar_one_or_none()
    rows = (await db.execute(
        select(EnergyMeterReading).where(EnergyMeterReading.facility == facility)
        .order_by(EnergyMeterReading.period.desc()).limit(min(max(months, 6), 240))
    )).scalars().all()
    if len(rows) < 6:
        raise HTTPException(422, "Minimal 6 bulan histori energi diperlukan untuk analisis.")
    rows = rows[::-1]
    latest = rows[-1]
    req = EnergyAnalysisRequest(
        facility=facility, floor_area_m2=latest.floor_area_m2, building_type=latest.building_type,
        baseline_months=min(max(baseline_months, 6), len(rows)),
        readings=[{"period": r.period, "kwh": r.kwh, "building_kwh": r.building_kwh,
                   "production_ton": r.production_ton, "peak_kw": r.peak_kw,
                   "operating_hours": r.operating_hours, "cost_rp": r.cost_rp} for r in rows])
    out = analyze_energy(req)
    out["data_source"] = {"table": "energy_readings", "rows": len(rows),
                          "demo_rows": sum(r.source == "demo" for r in rows),
                          "notes": {r.period: r.note for r in rows if r.note}}
    return out


@router.post("/energy/readings", status_code=201)
async def upsert_energy_reading(
    body: EnergyReadingIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat/perbarui pembacaan meter bulanan (satu baris per fasilitas per bulan)."""
    row = (await db.execute(select(EnergyMeterReading).where(
        EnergyMeterReading.facility == body.facility, EnergyMeterReading.period == body.period))).scalar_one_or_none()
    data = body.model_dump()
    if row is None:
        row = EnergyMeterReading(**data, source="manual", recorded_by_id=user.id)
        db.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
        row.source, row.recorded_by_id = "manual", user.id
    await db.flush()
    return {"id": row.id, "facility": row.facility, "period": row.period}


# ---------------------------------------------------------------- ⑪ Procurement, QC masuk, manufaktur sirkular
class NegotiationActionF(BaseModel):
    action: str = Field(..., pattern="^(accept|counter|reject)$")
    price_per_kg: float | None = Field(None, gt=0, le=20_000)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


class InboundQCIn(BaseModel):
    request_id: int
    gross_kg: float = Field(..., gt=0, le=1_000_000)
    tare_kg: float = Field(0, ge=0)
    moisture: float = Field(..., ge=0, le=60)
    ash: float = Field(..., ge=0, le=60)
    volatile_matter: float = Field(..., ge=0, le=100)
    fixed_carbon: float = Field(..., ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    rejected_kg: float = Field(0, ge=0, description="Karung disortir keluar (basah/berjamur): tidak dibayar, dikarantina")
    rejected_reason: str | None = Field(None, pattern="^(basah|berjamur|kontaminan|lainnya)$")
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000)
    note: str | None = Field(None, max_length=500)


class BatchInputIn(BaseModel):
    qc_id: int
    kg: float = Field(..., gt=0)


class BatchCostIn(BaseModel):
    item: str = Field(..., min_length=2, max_length=40)
    amount_rp: float = Field(..., ge=0)
    cost_type: str = Field("variabel", pattern="^(variabel|tetap)$")
    product: str | None = Field(None, pattern="^(bio_pellet|biochar|bio_silika)$",
                                description="Isi bila biaya terpisah satu produk; kosong = biaya bersama")
    driver_qty: float | None = Field(None, ge=0)
    driver_unit: str | None = Field(None, max_length=20)
    rate: float | None = Field(None, ge=0)


class BatchIn(BaseModel):
    batch_code: str = Field(..., min_length=3, max_length=50)
    inputs: list[BatchInputIn] = Field(..., min_length=1, max_length=200)
    outputs: dict[str, float] = Field(..., description="kg per produk: bio_pellet, biochar, bio_silika")
    losses: dict[str, float] = Field(default_factory=dict,
                                     description="kg per jenis: air, volatil_syngas, residu_ekstraksi, susut_proses")
    costs: list[BatchCostIn] = Field(default_factory=list, max_length=100)
    operating_hours: float | None = Field(None, gt=0, le=744)
    pyrolysis_temp_c: float | None = Field(None, ge=300, le=800)
    pellet_share: float | None = Field(None, ge=0, le=1)
    silica_share_of_biochar: float | None = Field(None, ge=0, le=1)
    silica_route: str | None = Field(None, pattern="^(biochar|abu_pembakaran|sekam_langsung)$")
    silica_husk_share: float | None = Field(None, ge=0, le=1)
    prices: dict[str, float] | None = Field(None, description="Harga jual batch ini (Rp/kg); kosong = menu Parameter")
    note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        ids = [i.qc_id for i in self.inputs]
        if len(ids) != len(set(ids)):
            raise ValueError("Lot QC ganda pada input batch")
        bad = set(self.outputs) - {"bio_pellet", "biochar", "bio_silika"}
        if bad or any(v < 0 for v in self.outputs.values()):
            raise ValueError("outputs hanya bio_pellet/biochar/bio_silika dengan kg ≥ 0")
        bad = set(self.losses) - set(LOSS_KINDS)          # satu sumber: engine + CHECK migrasi 016 (termasuk bio_oil)
        if bad or any(v < 0 for v in self.losses.values()):
            raise ValueError(f"losses hanya {'/'.join(LOSS_KINDS)}, kg ≥ 0")
        if self.prices and (set(self.prices) - {"bio_pellet", "biochar", "bio_silika"}
                            or any(v < 0 for v in self.prices.values())):
            raise ValueError("prices hanya bio_pellet/biochar/bio_silika dengan Rp/kg ≥ 0")
        return self


@router.post("/pricing/recommend")
async def pricing_recommend(
    req: PricingRequest,
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Rekomendasi harga beli biomassa: lantai / target / plafon + rincian netback & sensitivitas kadar air."""
    return recommend_price(req)


@router.get("/delivery-requests")
async def delivery_inbox(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
    status: str | None = None,
):
    q = select(DeliveryRequest, User.full_name).join(User, User.id == DeliveryRequest.collector_id)
    if status:
        q = q.where(DeliveryRequest.status == status)
    rows = (await db.execute(q.order_by(DeliveryRequest.id.desc()).limit(200))).all()
    return [{**factory_ops.request_dict(r), "collector": name} for r, name in rows]


@router.post("/delivery-requests/{request_id}/respond")
async def respond_delivery(
    request_id: int,
    body: NegotiationActionF,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Umpan balik pabrik: terima (jadwal & harga), tawar balik, atau tolak."""
    try:
        r = await factory_ops.respond(db, user, request_id, body.action, body.price_per_kg, body.date, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.request_dict(r)


@router.post("/qc", status_code=201)
async def record_inbound_qc(
    body: InboundQCIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Input Quality Control: timbang (bruto − tara), uji proksimat, keputusan & harga akhir (basis kering)."""
    try:
        qc = await factory_ops.inbound_qc(db, user, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.qc_dict(qc)


@router.get("/qc/lots")
async def qc_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    available_only: bool = True,
):
    q = select(InboundQC).order_by(InboundQC.id.desc()).limit(200)
    if available_only:
        q = q.where(InboundQC.remaining_kg > 0)
    return [factory_ops.qc_dict(x) for x in (await db.execute(q)).scalars().all()]


@router.post("/batches", status_code=201)
async def create_batch(
    body: BatchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Catat batch manufaktur sirkular: konsumsi lot, output 3 produk + loss, biaya → mass balance & unit economics."""
    try:
        b = await factory_ops.create_batch(db, user, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.batch_dict(b)


@router.get("/batches")
async def list_batches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    limit: int = 50,
):
    rows = (await db.execute(select(ManufacturingBatch).order_by(ManufacturingBatch.id.desc())
                             .limit(min(max(limit, 1), 200)))).scalars().all()
    return [factory_ops.batch_dict(b) for b in rows]


# ---------------------------------------------------------------- pembayaran ke pengepul (kedua jalur)
class SettlementPrice(BaseModel):
    price_per_kg: float = Field(..., ge=0, le=20_000)
    reason: str = Field(..., min_length=5, max_length=300)


class SettlementPay(BaseModel):
    payment_reference: str = Field(..., min_length=3, max_length=80, description="No. transfer / bukti bayar")


@router.get("/settlements")
async def list_settlements(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    status: str | None = None,
):
    FarmerUser = aliased(User, name="farmer_user")
    q = (select(CollectorSettlement, User.full_name, FarmerUser.full_name.label("farmer_name"))
         .join(User, User.id == CollectorSettlement.collector_id)
         .outerjoin(Harvest, Harvest.id == CollectorSettlement.harvest_id)
         .outerjoin(FarmerUser, FarmerUser.id == Harvest.farmer_id))
    if status:
        q = q.where(CollectorSettlement.status == status)
    rows = (await db.execute(q.order_by(CollectorSettlement.id.desc()).limit(300))).all()
    return [{**factory_ops.settlement_dict(s), "collector": name, "farmer_name": fname} for s, name, fname in rows]


@router.post("/settlements/{settlement_id}/price")
async def price_settlement(
    settlement_id: int, body: SettlementPrice,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Tetapkan harga untuk pembayaran 'menunggu harga' (atau koreksi sebelum dibayar)."""
    return factory_ops.settlement_dict(await factory_ops.set_settlement_price(db, settlement_id, body.price_per_kg,
                                                                              user, body.reason))


@router.post("/settlements/{settlement_id}/pay")
async def pay_settlement(
    settlement_id: int, body: SettlementPay,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    return factory_ops.settlement_dict(await factory_ops.mark_settlement_paid(db, settlement_id, body.payment_reference, actor=user))


@router.get("/settlements/{settlement_id}/history")
async def settlement_history(
    settlement_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Jejak audit perubahan harga dan status tagihan (pabrik/admin/auditor)."""
    s = await db.get(CollectorSettlement, settlement_id)
    if s is None:
        raise HTTPException(404, "Tagihan tidak ditemukan.")
    return await factory_ops.settlement_history(db, settlement_id)


@router.get("/arrivals")
async def route_arrivals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Biomassa jalur rute yang sudah dijemput supir dan menunggu timbang terima pabrik."""
    FarmerUser = aliased(User, name="farmer_u")
    CollectorUser = aliased(User, name="collector_u")
    q = (select(Harvest, FarmerUser.full_name.label("farmer_name"), CollectorUser.full_name.label("collector_name"))
         .outerjoin(FarmerUser, FarmerUser.id == Harvest.farmer_id)
         .outerjoin(CollectorUser, CollectorUser.id == Harvest.collector_id)
         .where(Harvest.status == HarvestStatus.COLLECTED)
         .order_by(Harvest.id).limit(200))
    rows = (await db.execute(q)).all()
    return [{
        "harvest_id": h.id,
        "collector_id": h.collector_id,
        "collector_name": cname,
        "farmer_id": h.farmer_id,
        "farmer_name": fname,
        "verified_kg": h.verified_kg,
        "moisture": h.moisture,
        "ash": h.ash,
        "grade": h.grade,
    } for h, fname, cname in rows]


@router.get("/inventory/ddmrp-buffers")
async def get_factory_ddmrp_buffers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """DDMRP Buffer Stock Status (Ptak & Smith, 2019) untuk Manajemen Persediaan Pabrik."""
    from ..engines.factory_econ import calculate_ddmrp_buffers
    from ..models.factory_ops import InboundQC, QCDecision
    total_stock_kg = (await db.execute(
        select(func.coalesce(func.sum(InboundQC.remaining_kg), 0.0))
        .where(InboundQC.remaining_kg > 0, InboundQC.decision != QCDecision.REJECT)
    )).scalar() or 0.0
    return calculate_ddmrp_buffers(float(total_stock_kg))


@router.post("/quality/spc-check")
async def quality_spc_check(
    moisture: float = Query(..., ge=0, le=100),
    ash: float = Query(..., ge=0, le=100),
    volatile_matter: float = Query(..., ge=0, le=100),
    fixed_carbon: float = Query(..., ge=0, le=100),
    contamination: float = Query(0.0, ge=0, le=100),
    user: Annotated[User, Depends(_audit_read)] = None,
):
    """Six Sigma SPC Shewhart 3-Sigma & Proximate Closure Check."""
    from ..engines.factory_econ import check_proximate_spc
    return check_proximate_spc(moisture, ash, volatile_matter, fixed_carbon, contamination)


# ---------------------------------------------------------------- retur / karantina
@router.get("/returns")
async def list_returns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    status: str | None = None,
):
    q = select(ReturnCase).order_by(ReturnCase.id.desc()).limit(300)
    if status:
        q = q.where(ReturnCase.status == status)
    return [logistics.return_dict(r) for r in (await db.execute(q)).scalars().all()]


@router.post("/returns", status_code=201)
async def open_return_case(
    body: ReturnOpenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Buka kasus retur manual (mis. jamur ditemukan di gudang setelah diterima)."""
    if not (body.harvest_id or body.request_id or body.qc_id):
        raise HTTPException(422, "Isi salah satu: harvest_id, request_id, atau qc_id.")
    rc = await logistics.open_return(db, user, stage="gudang_pabrik", harvest_id=body.harvest_id,
                                     request_id=body.request_id, qc_id=body.qc_id, reason_code=body.reason_code,
                                     quantity_kg=body.quantity_kg, moisture=body.moisture, location=body.location,
                                     note=body.note, evidence_photo_url=body.evidence_photo_url)
    return logistics.return_dict(rc)


@router.post("/returns/{case_id}/resolve")
async def resolve_return_case(
    case_id: int,
    body: ReturnResolveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Putuskan disposisi: kembalikan ke pengirim, keringkan ulang, turun grade, bahan bakar boiler, musnahkan."""
    try:
        rc = await logistics.resolve_return(db, user, case_id, body.disposition, body.cost_bearer,
                                            body.handling_cost_rp, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return logistics.return_dict(rc)


# ---------------------------------------------------------------- stok produk jadi
@router.get("/inventory")
async def inventory(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Saldo stok produk (biochar material baterai, bio-silika, bio-pellet) = jumlah mutasi (produksi - alokasi sirkular petani - penjualan +/- koreksi)."""
    return {"balance_kg": await factory_ops.inventory_balance(db)}


@router.post("/inventory/movements", status_code=201)
async def inventory_movement(
    body: GoodsMovementRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    try:
        return await factory_ops.record_goods_movement(db, user, body.product, body.movement, body.quantity_kg,
                                                       body.unit_price_rp, body.reference, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# ---------------------------------------------------------------- Green Scorecard (karbon, sirkularitas, green chemistry)
@router.get("/green-scorecard")
async def green_scorecard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    since: str | None = None,
):
    """Neraca karbon bersih (pembakaran terbuka dihindari + sekuestrasi biochar − angkut − listrik),
    indikator ekonomi sirkular, dan E-factor lini silika — dihitung dari batch, rute, dan retur NYATA.
    `since` = YYYY-MM-DD (opsional)."""
    from ..services.esg import green_scorecard_for
    start = None
    if since:
        try:
            start = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise HTTPException(422, "since harus YYYY-MM-DD") from e
    return await green_scorecard_for(db, start)


# → factory_optimization.py: Optimasi produk multi-output (HiGHS) dari stok multi-biomassa.

# ---------------------------------------------------------------- Omni 022: Factory Biochar Backhaul Dispatch
class DispatchBiocharRequest(BaseModel):
    collector_id: int
    driver_id: int | None = None
    route_id: int | None = None
    total_weight_kg: float = Field(..., gt=0, le=100_000)
    vehicle_plate: str | None = "B 9123 BIO"
    total_bags: int = Field(0, ge=0)
    loading_instructions: str | None = "Simpan di partisi belakang bak truk, pastikan terpal tertutup rapat bebas kontaminasi."


@router.post("/dispatch-biochar", status_code=201)
async def dispatch_biochar(
    req: DispatchBiocharRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Pabrik menerbitkan surat jalan dan muatan balik abu bottom ash / sirkular untuk diangkut armada driver/pengepul."""
    dispatch_code = f"DSP-{uuid.uuid4().hex[:8].upper()}"
    qr_token = f"QR-DSP-{uuid.uuid4().hex}"
    # Density biochar ~300 kg/m3
    vol_m3 = round(req.total_weight_kg / 300.0, 2)

    dist = BiocharDistribution(
        dispatch_code=dispatch_code,
        factory_id=user.id,
        collector_id=req.collector_id,
        driver_id=req.driver_id,
        route_id=req.route_id,
        vehicle_plate=req.vehicle_plate,
        total_bags=req.total_bags or int(req.total_weight_kg / 25),  # asumsi karung 25 kg
        total_weight_kg=req.total_weight_kg,
        volume_m3=vol_m3,
        loading_instructions=req.loading_instructions,
        qr_dispatch_token=qr_token,
        status="DISPATCHED",
    )
    db.add(dist)
    await db.flush()
    return {
        "id": dist.id,
        "dispatch_code": dist.dispatch_code,
        "qr_dispatch_token": dist.qr_dispatch_token,
        "total_weight_kg": dist.total_weight_kg,
        "total_bags": dist.total_bags,
        "volume_m3": dist.volume_m3,
        "status": dist.status,
        "message": f"✅ Surat jalan {dist.dispatch_code} berhasil diterbitkan ({dist.total_weight_kg} kg abu bottom ash)."
    }


@router.get("/biochar-dispatches")
async def list_biochar_dispatches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Daftar riwayat surat jalan muatan balik abu bottom ash yang telah diterbitkan pabrik."""
    rows = (await db.execute(
        select(BiocharDistribution, User)
        .outerjoin(User, User.id == BiocharDistribution.collector_id)
        .order_by(BiocharDistribution.id.desc())
        .limit(100)
    )).all()
    return [
        {
            "id": d.id,
            "dispatch_code": d.dispatch_code,
            "collector_name": c.full_name if c else f"Pengepul #{d.collector_id}",
            "vehicle_plate": d.vehicle_plate,
            "total_weight_kg": d.total_weight_kg,
            "total_bags": d.total_bags,
            "volume_m3": d.volume_m3,
            "qr_dispatch_token": d.qr_dispatch_token,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        }
        for d, c in rows
    ]


# -----------------------------------------------------------------------------
# FASE 2 & 3: Inbound Operations & Production Blending
# (Extracted to app/routers/factory_inbound.py and factory_production.py)
# -----------------------------------------------------------------------------
from .factory_inbound import router as inbound_router
from .factory_production import router as production_router

router.include_router(inbound_router)
router.include_router(production_router)

# Dipisah dari berkas ini (audit 23 Okt 2026, CLAUDE.md §3.1)
from .factory_esg import router as esg_router                    # noqa: E402
from .factory_optimization import router as optimization_router  # noqa: E402
from .factory_supply import router as supply_router              # noqa: E402

router.include_router(esg_router)
router.include_router(optimization_router)
router.include_router(supply_router)


# → factory_supply.py: Dashboard pasokan terkelompok, umpan balik pengepul, stok pengepul & ledger biochar sirkular.
