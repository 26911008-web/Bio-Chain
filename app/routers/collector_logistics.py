"""Router: Collector Logistics & Fleet Operations — CVRP Pickup Plan, Consolidated Multi-Trip Routing & Biochar Backhaul."""

from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.trade import Bid, BidStatus, DeliveryScheme, StockListing
from ..models.circular import BiocharRequest, BiocharCircularRequest
from ..engines.routing import plan_routes
from ..schemas.routing import RouteRequest
from ..concurrency import run_cpu

router = APIRouter()

FLEET_CATALOG = [
    {
        "id": "cdd_budi",
        "vehicle_type": "Truk CDD Box (5.000 kg / 30 m³)",
        "plate": "AB 8421 CS",
        "max_kg": 5000.0,
        "max_m3": 30.0,
        "driver_name": "Budi Santoso",
        "driver_phone": "0812-3456-7890",
        "driver_rating": 4.9,
        "badge": "CDD Box Andalan",
    },
    {
        "id": "engkel_joko",
        "vehicle_type": "Truk Engkel 4 Roda (3.500 kg / 20 m³)",
        "plate": "AB 8122 UY",
        "max_kg": 3500.0,
        "max_m3": 20.0,
        "driver_name": "Joko Pratama",
        "driver_phone": "0813-9876-5432",
        "driver_rating": 4.8,
        "badge": "Engkel Gesit Pedesaan",
    },
    {
        "id": "fuso_hendra",
        "vehicle_type": "Truk Fuso Heavy 6 Roda (8.500 kg / 50 m³)",
        "plate": "AB 9033 KP",
        "max_kg": 8500.0,
        "max_m3": 50.0,
        "driver_name": "Hendra Wijaya",
        "driver_phone": "0857-1122-3344",
        "driver_rating": 4.95,
        "badge": "Fuso Tonase Ekstra",
    },
    {
        "id": "l300_slamet",
        "vehicle_type": "Pick-up L300 Box (1.500 kg / 10 m³)",
        "plate": "AB 7540 DA",
        "max_kg": 1500.0,
        "max_m3": 10.0,
        "driver_name": "Slamet Riyadi",
        "driver_phone": "0821-4455-6677",
        "driver_rating": 4.75,
        "badge": "L300 Akses Gang & Sawah",
    },
]

SCHEDULE_DAYS = [
    {"day": "Senin", "label": "Senin (Gelombang 1 - Sleman Barat: Godean, Moyudan, Minggir)"},
    {"day": "Selasa", "label": "Selasa (Gelombang 2 - Sleman Tengah: Seyegan, Mlati, Tempel)"},
    {"day": "Rabu", "label": "Rabu (Gelombang 3 - Sleman Timur: Ngemplak, Kalasan, Berbah)"},
    {"day": "Kamis", "label": "Kamis (Gelombang 4 - Sleman Utara: Turi, Pakem, Cangkringan)"},
    {"day": "Jumat", "label": "Jumat (Gelombang 5 - Muatan Balik Biochar Poktan & Khusus)"},
    {"day": "Sabtu", "label": "Sabtu (Gelombang 6 - Konsolidasi Akhir Pekan)"},
]


class PickupPlanRequest(BaseModel):
    bid_ids: list[int] | None = None
    vehicle_m3: float | None = Field(None, gt=0, le=1000)
    cost_per_km: float | None = Field(None, ge=0)
    time_budget_ms: int = Field(500, ge=10, le=2000)


class ConsolidatedPickupPlanRequest(BaseModel):
    harvest_ids: list[int] = Field(..., min_length=1, max_length=200)   # matriks jarak O(n²)
    vehicle_plate: str | None = "AB 8421 CS"
    truck_max_kg: float = Field(5000.0, gt=0)
    truck_max_m3: float = Field(30.0, gt=0)
    biochar_backhaul_requests: list[int] | None = None
    vehicle_choice: str | None = None
    driver_choice: str | None = None
    schedule_day: str | None = None
    pickup_date: str | None = None
    fleet_mode: str | None = "single"


@router.post("/pickup-plan")
async def pickup_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    req: PickupPlanRequest | None = None,
):
    """Rencana rute penjemputan optimal untuk tawaran yang dimenangkan pengepul berskema jemput."""
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
            (Harvest.id.is_(None) | (Harvest.status.in_([HarvestStatus.REPORTED, HarvestStatus.VERIFIED]))),
        )
    )
    if req and req.bid_ids:
        q = q.where(Bid.id.in_(req.bid_ids))

    rows = (await db.execute(q.order_by(Bid.id.asc()))).all()

    # Sertakan juga panen langsung yang sudah TERVERIFIKASI dan berskema jemput
    spec = getattr(user, "specialization_commodity", None)
    if not spec:
        u_low = f"{(user.username or '')} {(user.full_name or '')}".lower()
        if "sekam" in u_low: spec = "sekam_padi"
        elif "jagung" in u_low: spec = "tongkol_jagung"
        elif "tebu" in u_low: spec = "ampas_tebu"
        elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low: spec = "serbuk_sengon"

    direct_q = (
        select(Harvest, User)
        .join(User, User.id == Harvest.farmer_id)
        .where(
            Harvest.status == HarvestStatus.VERIFIED,
            (Harvest.collector_id == user.id) | (Harvest.collector_id.is_(None)),
            (Harvest.delivery_scheme == "jemput") | (Harvest.logistics_mode == "PICKUP"),
            Harvest.bid_id.is_(None),
        )
    )
    if spec:
        direct_q = direct_q.where((Harvest.collector_id == user.id) | (Harvest.commodity == spec))
    direct_rows = (await db.execute(direct_q.order_by(Harvest.id.asc()))).all()

    if not rows and not direct_rows:
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
                "message": "Tidak ada penawaran atau panen terverifikasi berskema jemput yang menunggu penjemputan.",
                "steps": [],
                "references": [
                    "Clarke, G. & Wright, J.W. (1964). Scheduling of vehicles from a central depot to a number of delivery points.",
                ],
            },
        }

    farmer_ids = list({farmer.id for _, _, farmer, _ in rows} | {farmer.id for _, farmer in direct_rows})
    biochar_reqs = (await db.execute(
        select(BiocharCircularRequest).where(
            BiocharCircularRequest.farmer_id.in_(farmer_ids),
            BiocharCircularRequest.status.in_(["REQUESTED", "APPROVED_BY_COLLECTOR"])
        )
    )).scalars().all()
    farmer_biochar_map = {}
    for bcr in biochar_reqs:
        farmer_biochar_map[bcr.farmer_id] = farmer_biochar_map.get(bcr.farmer_id, 0.0) + bcr.requested_kg

    mills = []
    total_biochar_backhaul_kg = 0.0
    for bid, listing, farmer, h in rows:
        lat = listing.lat or farmer.lat or -7.745
        lon = listing.lon or farmer.lon or 110.362
        qty_kg = bid.accepted_kg if bid.accepted_kg > 0 else bid.quantity_kg
        b_drop = farmer_biochar_map.get(farmer.id, 0.0)
        total_biochar_backhaul_kg += b_drop
        mills.append({
            "id": f"BID-{bid.id}",
            "name": f"{farmer.full_name} (#{bid.id})",
            "lat": lat,
            "lon": lon,
            "stock_ton": qty_kg / 1000.0,
            "biochar_drop_kg": b_drop,
        })

    for h, farmer in direct_rows:
        lat = farmer.lat or -7.745
        lon = farmer.lon or 110.362
        b_drop = farmer_biochar_map.get(farmer.id, 0.0)
        total_biochar_backhaul_kg += b_drop
        qty_kg = h.verified_kg or h.quantity_kg
        mills.append({
            "id": f"HV-{h.id}",
            "name": f"{farmer.full_name} (Lot #{h.id})",
            "lat": lat,
            "lon": lon,
            "stock_ton": qty_kg / 1000.0,
            "biochar_drop_kg": b_drop,
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
    res = await run_cpu(plan_routes, depot, mills, route_req)
    total_ton = res["summary"]["total_ton"]
    total_cost = res["summary"]["total_cost"]
    res["summary"]["cost_per_kg"] = round(total_cost / (total_ton * 1000), 2) if total_ton > 0 else 0.0
    res["summary"]["total_biochar_backhaul_kg"] = total_biochar_backhaul_kg
    res["summary"]["biochar_backhaul_detected"] = total_biochar_backhaul_kg > 0
    return res


@router.post("/consolidated-pickup-plan")
async def consolidated_pickup_plan(
    req: ConsolidatedPickupPlanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Penyusunan rute multi-stop penjemputan biomassa petani terintegrasi muatan balik (backhaul) abu bottom ash.

    Memverifikasi constraint kapasitas ganda armada (Massa ≤ 5.000 kg dan Volume ≤ 30 m³).
    Simulasi dinamis: muatan balik abu bottom ash diturunkan di petani sementara biomassa dimuat. Biochar diproduksi pabrik untuk material baterai.
    """
    harvests = (await db.execute(
        select(Harvest).where(Harvest.id.in_(req.harvest_ids),
                              # hanya panen milik pengepul ini atau yang belum diklaim siapa pun
                              or_(Harvest.collector_id == user.id, Harvest.collector_id.is_(None)))
    )).scalars().all()
    if not harvests:
        raise HTTPException(404, "Tidak ada harvest yang valid ditemukan")

    farmer_ids = [h.farmer_id for h in harvests if h.farmer_id]
    farmers = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(farmer_ids)))).scalars().all()}

    biochar_reqs = []
    if req.biochar_backhaul_requests:
        biochar_reqs = (await db.execute(
            select(BiocharRequest).where(BiocharRequest.id.in_(req.biochar_backhaul_requests))
        )).scalars().all()

    total_biochar_kg = sum(b.requested_kg for b in biochar_reqs)
    biochar_volume_m3 = round(total_biochar_kg / 300.0, 2)

    depot = {"lat": user.lat or -6.9175, "lon": user.lon or 107.6191, "name": user.full_name or "Gudang Pengepul"}
    points = []
    total_biomass_kg = 0.0
    total_biomass_m3 = 0.0

    for h in harvests:
        f = farmers.get(h.farmer_id)
        f_lat = f.lat if f and f.lat is not None else depot["lat"] + 0.01
        f_lon = f.lon if f and f.lon is not None else depot["lon"] + 0.01
        qty_kg = h.quantity_kg
        total_biomass_kg += qty_kg
        vol_m3 = round(qty_kg / 120.0, 2)
        total_biomass_m3 += vol_m3
        
        farmer_b_kg = sum(b.requested_kg for b in biochar_reqs if b.farmer_id == h.farmer_id)
        
        points.append({
            "id": f"H{h.id}",
            "name": f"{f.full_name if f else 'Petani'} (#{h.id})",
            "lat": f_lat,
            "lon": f_lon,
            "stock_ton": qty_kg / 1000.0,
            "harvest_id": h.id,
            "farmer_name": f.full_name if f else f"Petani #{h.farmer_id}",
            "biomass_kg": qty_kg,
            "biomass_m3": vol_m3,
            "biochar_drop_kg": farmer_b_kg,
            "biochar_drop_m3": round(farmer_b_kg / 300.0, 2),
        })

    r_req = RouteRequest(vehicle_m3=req.truck_max_m3, cost_per_km=P("logistik.cost_per_km"), mode="auto", time_budget_ms=200)
    route_sol = await run_cpu(plan_routes, depot, points, r_req)   # solver CPU: jangan bekukan event loop

    pts_by_id = {pt["id"]: pt for pt in points}
    
    enriched_routes = []
    all_routes = route_sol.get("routes", [])
    if not all_routes and points:
        all_routes = [{
            "stops": [{"id": pt["id"], "name": pt["name"], "m3": pt["biomass_m3"], "ton": pt["stock_ton"]} for pt in points],
            "path": [[depot["lat"], depot["lon"]]] + [[pt["lat"], pt["lon"]] for pt in points] + [[depot["lat"], depot["lon"]]],
            "km": 25.0,
            "load_m3": total_biomass_m3,
            "load_ton": total_biomass_kg / 1000.0,
            "utilization_pct": round(min(100.0, (total_biomass_m3 / req.truck_max_m3) * 100), 1),
        }]

    user_fleet_match = None
    if req.vehicle_choice:
        user_fleet_match = next((f for f in FLEET_CATALOG if f["id"] == req.vehicle_choice or f["plate"] == req.vehicle_choice), None)

    for idx, r_raw in enumerate(all_routes):
        fleet_item = FLEET_CATALOG[idx % len(FLEET_CATALOG)]
        sched_item = SCHEDULE_DAYS[idx % len(SCHEDULE_DAYS)]

        if idx == 0 and user_fleet_match:
            plate_used = user_fleet_match["plate"]
            max_kg_used = user_fleet_match["max_kg"]
            max_m3_used = user_fleet_match["max_m3"]
            v_type_used = user_fleet_match["vehicle_type"]
            driver_used = req.driver_choice or user_fleet_match["driver_name"]
            phone_used = user_fleet_match["driver_phone"]
            rating_used = user_fleet_match["driver_rating"]
        elif idx == 0 and req.vehicle_plate:
            plate_used = req.vehicle_plate
            max_kg_used = req.truck_max_kg
            max_m3_used = req.truck_max_m3
            v_type_used = fleet_item["vehicle_type"]
            driver_used = req.driver_choice or fleet_item["driver_name"]
            phone_used = fleet_item["driver_phone"]
            rating_used = fleet_item["driver_rating"]
        else:
            plate_used = fleet_item["plate"]
            max_kg_used = fleet_item["max_kg"]
            max_m3_used = fleet_item["max_m3"]
            v_type_used = fleet_item["vehicle_type"]
            driver_used = fleet_item["driver_name"]
            phone_used = fleet_item["driver_phone"]
            rating_used = fleet_item["driver_rating"]

        day_used = (req.schedule_day if idx == 0 and req.schedule_day else sched_item["day"])

        trip_points = [pts_by_id.get(s["id"]) for s in r_raw["stops"] if pts_by_id.get(s["id"])]
        if not trip_points and points:
            trip_points = points

        trip_biochar_kg = sum(p["biochar_drop_kg"] for p in trip_points)
        trip_biochar_m3 = round(trip_biochar_kg / 300.0, 2)
        trip_biomass_kg = sum(p["biomass_kg"] for p in trip_points)
        trip_biomass_m3 = sum(p["biomass_m3"] for p in trip_points)

        curr_b_kg = trip_biochar_kg
        curr_m_kg = 0.0
        r_peak_kg = curr_b_kg
        r_peak_m3 = trip_biochar_m3

        trip_timeline = [{
            "stage": "START_DEPOT",
            "description": f"Armada {plate_used} ({driver_used}) berangkat membawa muatan balik abu bottom ash",
            "biochar_kg": curr_b_kg,
            "biomass_kg": 0.0,
            "total_weight_kg": curr_b_kg,
            "total_volume_m3": trip_biochar_m3,
        }]

        for pt in trip_points:
            curr_b_kg = max(0.0, curr_b_kg - pt["biochar_drop_kg"])
            curr_m_kg += pt["biomass_kg"]
            sw = round(curr_b_kg + curr_m_kg, 2)
            sv = round((curr_b_kg / 300.0) + (curr_m_kg / 120.0), 2)
            if sw > r_peak_kg:
                r_peak_kg = sw
            if sv > r_peak_m3:
                r_peak_m3 = sv
            trip_timeline.append({
                "stage": f"STOP_{pt['id']}",
                "location": pt["name"],
                "biochar_dropped_kg": pt["biochar_drop_kg"],
                "biomass_loaded_kg": pt["biomass_kg"],
                "current_weight_kg": sw,
                "current_volume_m3": sv,
            })

        is_r_feasible = r_peak_kg <= (max_kg_used * 1.05) and r_peak_m3 <= (max_m3_used * 1.05)

        enriched_routes.append({
            "trip_index": idx + 1,
            "trip_code": f"TRIP-{idx + 1:02d}",
            "vehicle_type": v_type_used,
            "vehicle_plate": plate_used,
            "truck_max_kg": max_kg_used,
            "truck_max_m3": max_m3_used,
            "driver_name": driver_used,
            "driver_phone": phone_used,
            "driver_rating": rating_used,
            "scheduled_day": day_used,
            "scheduled_label": sched_item["label"],
            "is_feasible": is_r_feasible,
            "peak_weight_kg": r_peak_kg,
            "peak_volume_m3": r_peak_m3,
            "weight_utilization_pct": round((r_peak_kg / max_kg_used) * 100, 1) if max_kg_used else 0,
            "volume_utilization_pct": round((r_peak_m3 / max_m3_used) * 100, 1) if max_m3_used else 0,
            "biomass_kg": round(trip_biomass_kg, 1),
            "biomass_m3": round(trip_biomass_m3, 2),
            "biochar_kg": round(trip_biochar_kg, 1),
            "biochar_m3": round(trip_biochar_m3, 2),
            "stops_count": len(trip_points),
            "km": r_raw.get("km", 10.0),
            "stops": r_raw.get("stops", []),
            "path": r_raw.get("path", []),
            "simulation_timeline": trip_timeline,
        })

    is_all_fleet_feasible = all(r["is_feasible"] for r in enriched_routes) if enriched_routes else False
    primary_trip = enriched_routes[0] if enriched_routes else None

    is_overloaded = (
        (total_biomass_m3 + biochar_volume_m3) > req.truck_max_m3
        or (total_biomass_kg + total_biochar_kg) > req.truck_max_kg
    )
    if is_overloaded:
        is_overall_feasible = False
    elif len(enriched_routes) > 1 and getattr(req, "fleet_mode", None) != "auto":
        is_overall_feasible = False
    else:
        is_overall_feasible = is_all_fleet_feasible if len(enriched_routes) > 1 else (primary_trip["is_feasible"] if primary_trip else True)

    return {
        "success": True,
        "is_feasible": is_overall_feasible,
        "is_multi_trip": len(enriched_routes) > 1,
        "trips_count": len(enriched_routes),
        "vehicle_plate": primary_trip["vehicle_plate"] if primary_trip else req.vehicle_plate,
        "truck_max_kg": primary_trip["truck_max_kg"] if primary_trip else req.truck_max_kg,
        "truck_max_m3": primary_trip["truck_max_m3"] if primary_trip else req.truck_max_m3,
        "driver_name": primary_trip["driver_name"] if primary_trip else "Budi Santoso",
        "scheduled_day": primary_trip["scheduled_day"] if primary_trip else "Senin",
        "peak_weight_kg": primary_trip["peak_weight_kg"] if primary_trip else 0.0,
        "peak_volume_m3": primary_trip["peak_volume_m3"] if primary_trip else 0.0,
        "total_biomass_kg": round(total_biomass_kg, 2),
        "total_biomass_m3": round(total_biomass_m3, 2),
        "total_biochar_backhaul_kg": total_biochar_kg,
        "total_biochar_backhaul_m3": biochar_volume_m3,
        "stops_count": len(points),
        "route_summary": route_sol.get("summary"),
        "routes": enriched_routes,
        "fleet_options": FLEET_CATALOG,
        "schedule_options": SCHEDULE_DAYS,
        "depot": depot,
        "points": points,
        "simulation_timeline": primary_trip["simulation_timeline"] if primary_trip else [],
        "warning": None if is_overall_feasible else (
            f"Kapasitas terlampaui: total muatan ({total_biomass_kg + total_biochar_kg:.0f} kg / {total_biomass_m3 + biochar_volume_m3:.1f} m³) melebihi kapasitas armada truk ({req.truck_max_kg:.0f} kg / {req.truck_max_m3:.1f} m³). Disarankan menggunakan opsi multi-armada atau rotasi hari."
        ),
    }
