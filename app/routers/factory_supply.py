"""Sub-router pabrik: Dashboard pasokan terkelompok, umpan balik pengepul, stok pengepul & ledger biochar sirkular.

Dipisah dari app/routers/factory.py (audit 23 Okt 2026, CLAUDE.md §3.1) dan di-mount olehnya.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import HarvestStatus

router = APIRouter()

_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)
# Aksi yang mengubah timbangan / stok hanya oleh operator pabrik (admin tidak, demi pemisahan tugas).
_pabrik_only = require_role(UserRole.PABRIK)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)



router = APIRouter()


# -----------------------------------------------------------------------------
# FASE 4: Grouped Monitoring Dashboard & Circular Ledgers
# -----------------------------------------------------------------------------
@router.get("/dashboard/biomass-grouped")
async def get_biomass_grouped_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Ringkasan metrik analitik gerbang, inventaris ramp, dan keuangan terkelompok per jenis biomassa."""
    from ..models.industrial import GateReception, LoadingRamp, FactoryInvoice

    receptions = (await db.execute(select(GateReception))).scalars().all()
    ramps = (await db.execute(select(LoadingRamp))).scalars().all()
    invoices = (await db.execute(select(FactoryInvoice))).scalars().all()

    all_types = set()
    for g in receptions:
        all_types.add(g.biomass_type)
    for r in ramps:
        all_types.add(r.biomass_type)
    for inv in invoices:
        all_types.add(inv.biomass_type)

    if not all_types:
        all_types = {"sekam_padi", "tongkol_jagung", "serbuk_sengon", "tempurung_kelapa"}

    grouped_data = []
    for b_type in sorted(all_types):
        b_rec = [g for g in receptions if g.biomass_type == b_type]
        b_ramps = [r for r in ramps if r.biomass_type == b_type]
        b_invs = [inv for inv in invoices if inv.biomass_type == b_type]

        tot_in = sum(g.net_weight for g in b_rec)
        tot_acc = sum(g.accepted_qty_kg for g in b_rec)
        tot_rej = sum(g.rejected_qty_kg for g in b_rec)
        rej_rate = round((tot_rej / tot_in * 100), 1) if tot_in > 0 else 0.0

        avg_mc = round(sum(g.tested_mc_pct for g in b_rec) / len(b_rec), 1) if b_rec else 0.0
        avg_ash = round(sum(g.tested_ash_pct for g in b_rec) / len(b_rec), 1) if b_rec else 0.0
        avg_lhv = round(sum(g.tested_lhv_kcal for g in b_rec) / len(b_rec), 0) if b_rec else 0.0

        stock_ramp = sum(r.current_stock_kg for r in b_ramps)
        cap_ramp = sum(r.max_capacity_kg for r in b_ramps)

        tot_invoiced = sum(inv.total_amount_rp for inv in b_invs)
        tot_paid = sum(inv.dp_paid_amount for inv in b_invs if inv.status == "PAID") + sum(inv.dp_paid_amount for inv in b_invs if inv.status != "PAID")
        tot_unpaid = sum(inv.remaining_amount for inv in b_invs if inv.status != "PAID")

        grouped_data.append({
            "biomass_type": b_type,
            "display_name": b_type.replace("_", " ").title(),
            "incoming_trips": len(b_rec),
            "total_incoming_kg": tot_in,
            "total_accepted_kg": tot_acc,
            "total_rejected_kg": tot_rej,
            "rejection_rate_pct": rej_rate,
            "avg_mc_pct": avg_mc,
            "avg_ash_pct": avg_ash,
            "avg_lhv_kcal": avg_lhv,
            "ramp_stock_kg": stock_ramp,
            "ramp_capacity_kg": cap_ramp,
            "total_invoiced_rp": tot_invoiced,
            "total_paid_rp": tot_paid,
            "total_unpaid_rp": tot_unpaid,
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": grouped_data,
        "grouped": {d["biomass_type"]: d for d in grouped_data},
    }


@router.get("/collector-feedback-logs")
async def list_collector_feedback_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    collector_id: int | None = None,
):
    """Log umpan balik mutu gerbang, alasan penolakan, dan rekomendasi perbaikan untuk pengepul."""
    from ..models.industrial import GateReception
    from ..models.user import User

    query = (
        select(GateReception, User)
        .join(User, User.id == GateReception.collector_id)
        .order_by(GateReception.id.desc())
    )
    if collector_id:
        query = query.where(GateReception.collector_id == collector_id)

    rows = (await db.execute(query.limit(100))).all()
    feedback_logs = []
    for g, col in rows:
        recs = []
        if g.tested_mc_pct > 20.0:
            recs.append(f"Kadar air tinggi ({g.tested_mc_pct}%). Jemur ulang atau simpan di tempat kering berventilasi sebelum dikirim.")
        if g.tested_ash_pct > 15.0 and "sekam" in g.biomass_type:
            recs.append(f"Kadar abu biomassa tinggi ({g.tested_ash_pct}%). Hindari penumpukan langsung di tanah dan bersihkan pasir.")
        if g.contamination_pct > 5.0:
            recs.append(f"Tingkat kontaminasi fisik ({g.contamination_pct}%) tinggi. Ayak biomassa untuk memisahkan kerikil dan benda asing.")
        if not recs and g.qc_decision == "ACCEPTED":
            recs.append("Mutu biomassa prima, memenuhi standar grade premium pabrik.")

        feedback_logs.append({
            "reception_id": g.id,
            "ticket_number": g.ticket_number,
            "collector_id": col.id,
            "collector_name": col.full_name,
            "vehicle_plate": g.vehicle_plate,
            "biomass_type": g.biomass_type,
            "net_weight_kg": g.net_weight,
            "qc_decision": g.qc_decision,
            "accepted_qty_kg": g.accepted_qty_kg,
            "rejected_qty_kg": g.rejected_qty_kg,
            "rejection_reason": g.rejection_reason,
            "tested_mc_pct": g.tested_mc_pct,
            "tested_ash_pct": g.tested_ash_pct,
            "tested_lhv_kcal": g.tested_lhv_kcal,
            "actionable_feedback": " ".join(recs),
            "created_at": g.created_at.isoformat() if g.created_at else None,
        })

    return feedback_logs


# -----------------------------------------------------------------------------
# FASE 5: Cross-Collector Stocks, Anti-Double Booking & Closed-Loop Biochar
# -----------------------------------------------------------------------------
class ReserveStockRequest(BaseModel):
    harvest_ids: list[int] = Field(default_factory=list)
    listing_ids: list[int] = Field(default_factory=list)


@router.get("/collector-stocks")
async def list_collector_stocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    biomass_type: str | None = None,
):
    """Katalog stok biomassa lintas pengepul spesialis, terkelompok (grouped) per jenis biomassa."""
    from ..models.harvest import Harvest
    from ..models.trade import StockListing
    from ..services import trade

    # Query verified harvests in collector possession
    h_query = (
        select(Harvest, User)
        .join(User, User.id == Harvest.collector_id)
        .where(Harvest.status == HarvestStatus.VERIFIED, Harvest.delivery_request_id.is_(None))
    )
    if biomass_type:
        h_query = h_query.where(Harvest.commodity == biomass_type)
    harvest_rows = (await db.execute(h_query.order_by(Harvest.id.desc()))).all()

    # Query open listings
    l_query = (
        select(StockListing, User)
        .join(User, User.id == StockListing.farmer_id)
        .where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
    )
    if biomass_type:
        l_query = l_query.where(StockListing.commodity == biomass_type)
    listing_rows = (await db.execute(l_query.order_by(StockListing.id.desc()))).all()

    # Grouping per jenis biomassa
    grouped = {}
    for h, collector in harvest_rows:
        b_type = h.commodity or "sekam_padi"
        if b_type not in grouped:
            grouped[b_type] = {
                "biomass_type": b_type,
                "biomass_name": b_type.replace("_", " ").title(),
                "total_stock_kg": 0.0,
                "available_stock_kg": 0.0,
                "locked_stock_kg": 0.0,
                "items": [],
            }
        qty = h.verified_kg or h.quantity_kg
        is_locked = bool(h.is_locked)
        grouped[b_type]["total_stock_kg"] += qty
        if is_locked:
            grouped[b_type]["locked_stock_kg"] += qty
        else:
            grouped[b_type]["available_stock_kg"] += qty

        grouped[b_type]["items"].append({
            "id": h.id,
            "source_type": "harvest",
            "collector_id": collector.id,
            "collector_name": collector.full_name or collector.username,
            "collector_phone": collector.phone,
            "commodity": b_type,
            "quantity_kg": qty,
            "moisture_pct": h.moisture,
            "ash_pct": h.ash,
            "grade": h.grade.value if h.grade and hasattr(h.grade, 'value') else (h.grade or "A"),
            "price_per_kg": h.agreed_price_per_kg or h.base_price_per_kg or 450.0,
            "is_locked": is_locked,
            "locked_by_mill_id": h.locked_by_mill_id,
        })

    for l, farmer in listing_rows:
        b_type = l.commodity or "sekam_padi"
        if b_type not in grouped:
            grouped[b_type] = {
                "biomass_type": b_type,
                "biomass_name": b_type.replace("_", " ").title(),
                "total_stock_kg": 0.0,
                "available_stock_kg": 0.0,
                "locked_stock_kg": 0.0,
                "items": [],
            }
        qty = l.remaining_kg
        is_locked = bool(l.is_locked)
        grouped[b_type]["total_stock_kg"] += qty
        if is_locked:
            grouped[b_type]["locked_stock_kg"] += qty
        else:
            grouped[b_type]["available_stock_kg"] += qty

        hrg = l.ask_price_jemput or l.ask_price_antar or l.floor_price or 450.0
        grouped[b_type]["items"].append({
            "id": l.id,
            "source_type": "listing",
            "farmer_id": farmer.id,
            "farmer_name": farmer.full_name or farmer.username,
            "farmer_phone": farmer.phone,
            "commodity": b_type,
            "quantity_kg": qty,
            "moisture_pct": l.moisture_pct,
            "ash_pct": None,
            "grade": l.grade_estimate or "A",
            "price_per_kg": hrg,
            "is_locked": is_locked,
            "locked_by_mill_id": l.locked_by_mill_id,
        })

    return {
        "grouped": grouped,
        "total_biomass_types": len(grouped),
        "grand_total_stock_kg": sum(g["total_stock_kg"] for g in grouped.values()),
    }


@router.post("/reserve-stock")
async def reserve_stock(
    req: ReserveStockRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Kunci stok biomassa saat pabrik menerbitkan rencana pengiriman (Anti-Double Booking)."""
    from ..models.harvest import Harvest
    from ..models.trade import StockListing

    now = datetime.now(timezone.utc)
    if req.harvest_ids:
        harvests = (await db.execute(
            select(Harvest).where(Harvest.id.in_(req.harvest_ids)).with_for_update()
        )).scalars().all()
        for h in harvests:
            if h.is_locked and h.locked_by_mill_id != user.id:
                raise HTTPException(409, f"Harvest #{h.id} ({h.commodity}) sedang dikunci oleh pabrik lain!")
            h.is_locked = True
            h.locked_by_mill_id = user.id
            h.locked_at = now

    if req.listing_ids:
        listings = (await db.execute(
            select(StockListing).where(StockListing.id.in_(req.listing_ids)).with_for_update()
        )).scalars().all()
        for l in listings:
            if l.is_locked and l.locked_by_mill_id != user.id:
                raise HTTPException(409, f"Listing #{l.id} ({l.commodity}) sedang dikunci oleh pabrik lain!")
            l.is_locked = True
            l.locked_by_mill_id = user.id
            l.locked_at = now

    await db.flush()
    return {
        "success": True,
        "message": f"Berhasil mengunci {len(req.harvest_ids)} harvest dan {len(req.listing_ids)} listing stok.",
        "locked_by_mill_id": user.id,
        "locked_at": now.isoformat(),
    }


@router.post("/release-stock")
async def release_stock(
    req: ReserveStockRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Lepas kunci stok biomassa."""
    from ..models.harvest import Harvest
    from ..models.trade import StockListing

    if req.harvest_ids:
        await db.execute(
            update(Harvest)
            .where(Harvest.id.in_(req.harvest_ids), Harvest.locked_by_mill_id == user.id)
            .values(is_locked=False, locked_by_mill_id=None, locked_at=None)
        )
    if req.listing_ids:
        await db.execute(
            update(StockListing)
            .where(StockListing.id.in_(req.listing_ids), StockListing.locked_by_mill_id == user.id)
            .values(is_locked=False, locked_by_mill_id=None, locked_at=None)
        )
    await db.flush()
    return {"success": True, "message": "Kunci stok berhasil dilepas."}


@router.get("/closed-loop-biochar")
async def get_closed_loop_biochar(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Traceability sirkular abu bottom ash end-to-end: Kiln Pabrik -> Pengepul -> Armada Backhaul -> Lahan Petani."""
    from ..models.circular import BiocharRequest, BiocharDistribution, BiocharQualityEvaluation
    from ..models.industrial import ProductionBlend

    blends = (await db.execute(
        select(ProductionBlend).where(ProductionBlend.target_product == "BIOCHAR").order_by(ProductionBlend.id.desc())
    )).scalars().all()

    distributions = (await db.execute(
        select(BiocharDistribution).order_by(BiocharDistribution.id.desc())
    )).scalars().all()

    requests = (await db.execute(
        select(BiocharRequest, User)
        .join(User, User.id == BiocharRequest.farmer_id)
        .order_by(BiocharRequest.id.desc())
    )).all()

    evaluations = (await db.execute(
        select(BiocharQualityEvaluation, User)
        .join(User, User.id == BiocharQualityEvaluation.farmer_id)
        .order_by(BiocharQualityEvaluation.id.desc())
    )).all()

    trace_items = []
    for b in blends:
        trace_items.append({
            "stage": "KILN_PRODUCTION",
            "batch_code": b.blend_code,
            "product": "BIOCHAR",
            "output_kg": round(b.total_input_kg * 0.28, 1),
            "carbon_seq_tco2e": b.net_tco2e,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })

    for d in distributions:
        trace_items.append({
            "stage": "DISPATCH_COLLECTOR",
            "dispatch_code": d.dispatch_code,
            "collector_id": d.collector_id,
            "driver_id": d.driver_id,
            "vehicle_plate": d.vehicle_plate,
            "weight_kg": d.total_weight_kg,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })

    eval_map = {e.biochar_request_id: (e, u) for e, u in evaluations if e.biochar_request_id}
    farmer_traces = []
    for r, u in requests:
        ev, _ = eval_map.get(r.id, (None, None))
        farmer_traces.append({
            "request_code": r.request_code,
            "farmer_name": u.full_name or u.username,
            "requested_kg": r.requested_kg,
            "status": r.status,
            "delivery_point": r.delivery_point,
            "evaluated": ev is not None,
            "evaluation": {
                "overall_score": ev.overall_score,
                "mesh_rating": ev.grain_size_mesh_rating,
                "pyrolysis_rating": ev.pyrolysis_maturity_rating,
                "moisture_rating": ev.moisture_rating,
                "soil_impact_rating": ev.soil_impact_rating,
                "notes": ev.review_notes,
            } if ev else None,
        })

    return {
        "summary": {
            "total_biochar_produced_kg": sum(b.total_input_kg * 0.28 for b in blends),
            "total_distributed_kg": sum(d.total_weight_kg for d in distributions),
            "total_farmer_requests": len(requests),
            "total_evaluations": len(evaluations),
        },
        "kiln_batches": [b.blend_code for b in blends],
        "traces": trace_items,
        "farmer_applications": farmer_traces,
    }
