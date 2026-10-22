"""Router: Factory Inbound Operations — Gate Reception, Weighbridge QC, Dynamic Ramps & Factory Invoices."""

from datetime import datetime, timezone, timedelta
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.industrial import GateReception, LoadingRamp, FactoryInvoice
from ..models.factory_ops import DeliveryRequest, ReturnCase, ReturnDisposition, ReturnReason, InboundQC, QCDecision, RequestStatus
from ..services import factory_ops
from ..services.custody import shrinkage_fields
import logging

_audit = logging.getLogger("biochain.audit")
_pabrik_only = require_role(UserRole.PABRIK, UserRole.ADMIN)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)

router = APIRouter()


class LoadingRampCreate(BaseModel):
    ramp_code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    biomass_type: str = Field(..., max_length=50)
    max_capacity_kg: float = Field(50000.0, gt=0)
    current_stock_kg: float = Field(0.0, ge=0)
    aggregate_mc: float = Field(12.0, ge=0, le=60)
    aggregate_ash: float = Field(15.0, ge=0, le=60)
    aggregate_lhv_kcal: float = Field(3500.0, ge=1000, le=7000)


class GateReceptionCreate(BaseModel):
    collector_id: int
    delivery_request_id: int | None = None
    vehicle_plate: str = Field(..., max_length=20)
    driver_name: str = Field(..., max_length=100)
    logistics_carrier: str = Field("FACTORY_FLEET", pattern="^(FACTORY_FLEET|COLLECTOR_SELF)$")
    biomass_type: str = Field("sekam_padi", max_length=50)
    gross_weight: float = Field(..., gt=0)
    tare_weight: float = Field(..., ge=0)
    tested_mc_pct: float = Field(..., ge=0, le=100)
    tested_ash_pct: float = Field(..., ge=0, le=100)
    tested_lhv_kcal: float = Field(3500.0, ge=0)
    contamination_pct: float = Field(0.0, ge=0, le=100)
    qc_decision: str = Field("ACCEPTED", pattern="^(ACCEPTED|PARTIALLY_ACCEPTED|REJECTED)$")
    accepted_qty_kg: float | None = None
    rejected_qty_kg: float | None = None
    rejection_reason: str | None = None
    qc_photo_url: str | None = None
    allocated_ramp_id: int | None = None
    payment_scheme: str = Field("CASH", pattern="^(CASH|DP|TOP)$")
    unit_price_rp: float = Field(450.0, gt=0)
    dp_paid_amount: float = Field(0.0, ge=0)
    due_days: int = Field(14, ge=1, le=90)


class InvoicePaymentRequest(BaseModel):
    amount_rp: float = Field(..., gt=0)
    payment_method: str = Field("TRANSFER", description="'TRANSFER' | 'CASH' | 'GIRO'")
    reference_note: str | None = Field(None, max_length=200)


@router.get("/loading-ramps")
async def list_loading_ramps(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Daftar loading ramp fisik dan agregat mutu stok terkini."""
    ramps = (await db.execute(
        select(LoadingRamp).order_by(LoadingRamp.ramp_code.asc())
    )).scalars().all()

    if not ramps:
        defaults = [
            LoadingRamp(ramp_code="RAMP-01", name="Ramp Biomassa 01 (Granular/Sekam)", biomass_type="sekam_padi", max_capacity_kg=60000.0, current_stock_kg=15000.0, aggregate_mc=13.5, aggregate_ash=17.0, aggregate_lhv_kcal=3450.0),
            LoadingRamp(ramp_code="RAMP-02", name="Ramp Biomassa 02 (Cacah/Tongkol)", biomass_type="tongkol_jagung", max_capacity_kg=45000.0, current_stock_kg=8000.0, aggregate_mc=14.0, aggregate_ash=2.5, aggregate_lhv_kcal=4100.0),
            LoadingRamp(ramp_code="RAMP-03", name="Ramp Biomassa 03 (Serbuk Kayu)", biomass_type="serbuk_sengon", max_capacity_kg=40000.0, current_stock_kg=5000.0, aggregate_mc=28.0, aggregate_ash=1.5, aggregate_lhv_kcal=3800.0),
            LoadingRamp(ramp_code="RAMP-04", name="Ramp Biomassa 04 (Cangkang/Tempurung)", biomass_type="tempurung_kelapa", max_capacity_kg=50000.0, current_stock_kg=12000.0, aggregate_mc=10.5, aggregate_ash=2.0, aggregate_lhv_kcal=4600.0),
        ]
        for r in defaults:
            db.add(r)
        await db.flush()
        ramps = defaults

    return [
        {
            "id": r.id,
            "ramp_code": r.ramp_code,
            "name": r.name,
            "biomass_type": r.biomass_type,
            "max_capacity_kg": r.max_capacity_kg,
            "current_stock_kg": r.current_stock_kg,
            "available_capacity_kg": max(0.0, r.max_capacity_kg - r.current_stock_kg),
            "utilization_pct": round((r.current_stock_kg / r.max_capacity_kg * 100), 1) if r.max_capacity_kg > 0 else 0,
            "aggregate_mc": r.aggregate_mc,
            "aggregate_ash": r.aggregate_ash,
            "aggregate_lhv_kcal": r.aggregate_lhv_kcal,
            "is_active": r.is_active,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in ramps
    ]


@router.post("/loading-ramps", status_code=201)
async def create_or_update_loading_ramp(
    req: LoadingRampCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Tambah atau perbarui konfigurasi Loading Ramp pabrik."""
    existing = (await db.execute(
        select(LoadingRamp).where(LoadingRamp.ramp_code == req.ramp_code.upper()).with_for_update()
    )).scalar_one_or_none()

    if existing:
        existing.name = req.name
        existing.biomass_type = req.biomass_type
        existing.max_capacity_kg = req.max_capacity_kg
        existing.current_stock_kg = req.current_stock_kg
        existing.aggregate_mc = req.aggregate_mc
        existing.aggregate_ash = req.aggregate_ash
        existing.aggregate_lhv_kcal = req.aggregate_lhv_kcal
        existing.updated_at = datetime.now(timezone.utc)
        ramp = existing
    else:
        ramp = LoadingRamp(
            ramp_code=req.ramp_code.upper(),
            name=req.name,
            mill_id=user.id,
            biomass_type=req.biomass_type,
            max_capacity_kg=req.max_capacity_kg,
            current_stock_kg=req.current_stock_kg,
            aggregate_mc=req.aggregate_mc,
            aggregate_ash=req.aggregate_ash,
            aggregate_lhv_kcal=req.aggregate_lhv_kcal,
            is_active=True,
        )
        db.add(ramp)

    await db.flush()
    return {
        "success": True,
        "id": ramp.id,
        "ramp_code": ramp.ramp_code,
        "name": ramp.name,
        "current_stock_kg": ramp.current_stock_kg,
        "message": f"Loading Ramp {ramp.ramp_code} berhasil disimpan."
    }


@router.post("/gate-receptions", status_code=201)
async def create_gate_reception(
    req: GateReceptionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Penerimaan muatan di Gerbang Pabrik & QC Timbangan Jembatan."""
    net_weight = req.gross_weight - req.tare_weight
    if net_weight <= 0:
        raise HTTPException(400, "Berat kotor (gross) harus lebih besar daripada berat tara!")

    if req.qc_decision == "ACCEPTED":
        accepted_qty = net_weight
        rejected_qty = 0.0
    elif req.qc_decision == "REJECTED":
        accepted_qty = 0.0
        rejected_qty = net_weight
        if not req.rejection_reason:
            raise HTTPException(422, "Penolakan total wajib mencantumkan alasan penolakan tertulis!")
    elif req.qc_decision == "PARTIALLY_ACCEPTED":
        accepted_qty = req.accepted_qty_kg if req.accepted_qty_kg is not None else 0.0
        rejected_qty = req.rejected_qty_kg if req.rejected_qty_kg is not None else (net_weight - accepted_qty)
        if accepted_qty + rejected_qty > net_weight + 0.1 or accepted_qty < 0 or rejected_qty < 0:
            raise HTTPException(400, f"Jumlah kuantitas diterima ({accepted_qty} kg) + ditolak ({rejected_qty} kg) tidak cocok dengan total netto timbangan ({net_weight} kg)!")
        if rejected_qty > 0 and not req.rejection_reason:
            raise HTTPException(422, "Penerimaan sebagian wajib mencantumkan alasan penolakan untuk porsi yang ditolak!")
    else:
        raise HTTPException(400, f"Keputusan QC tidak valid: {req.qc_decision}")

    # Cek tunggakan TOP yang overdue
    overdue_invoices = (await db.execute(
        select(FactoryInvoice)
        .where(FactoryInvoice.mill_id == user.id, FactoryInvoice.is_overdue.is_(True), FactoryInvoice.status != "PAID")
    )).scalars().all()
    if overdue_invoices and req.payment_scheme == "TOP":
        raise HTTPException(403, "Transaksi ditolak! Pabrik memiliki tagihan TOP yang telah jatuh tempo belum dilunasi. Wajib melunasi tagihan overdue sebelum membuka transaksi TOP baru.")

    # Alokasi Loading Ramp
    allocated_ramp = None
    if accepted_qty > 0 and req.allocated_ramp_id:
        ramp = (await db.execute(
            select(LoadingRamp).where(LoadingRamp.id == req.allocated_ramp_id).with_for_update()
        )).scalar_one_or_none()
        if not ramp:
            raise HTTPException(404, f"Loading Ramp ID {req.allocated_ramp_id} tidak ditemukan.")
        if (ramp.current_stock_kg + accepted_qty) > ramp.max_capacity_kg:
            raise HTTPException(409, f"Kapasitas fisik {ramp.ramp_code} terlampaui! Kapasitas maks: {ramp.max_capacity_kg} kg, Stok saat ini: {ramp.current_stock_kg} kg, Muatan masuk: {accepted_qty} kg.")

        old_stock = ramp.current_stock_kg
        new_total_stock = old_stock + accepted_qty
        if new_total_stock > 0:
            new_mc = ((old_stock * ramp.aggregate_mc) + (accepted_qty * req.tested_mc_pct)) / new_total_stock
            new_ash = ((old_stock * ramp.aggregate_ash) + (accepted_qty * req.tested_ash_pct)) / new_total_stock
            new_lhv = ((old_stock * ramp.aggregate_lhv_kcal) + (accepted_qty * req.tested_lhv_kcal)) / new_total_stock
            ramp.current_stock_kg = new_total_stock
            ramp.aggregate_mc = round(new_mc, 2)
            ramp.aggregate_ash = round(new_ash, 2)
            ramp.aggregate_lhv_kcal = round(new_lhv, 1)
            ramp.updated_at = datetime.now(timezone.utc)
            allocated_ramp = ramp

    ticket_num = f"GATE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    reception = GateReception(
        ticket_number=ticket_num,
        mill_id=user.id,
        collector_id=req.collector_id,
        delivery_request_id=req.delivery_request_id,
        vehicle_plate=req.vehicle_plate.upper(),
        driver_name=req.driver_name,
        logistics_carrier=req.logistics_carrier,
        biomass_type=req.biomass_type,
        gross_weight=req.gross_weight,
        tare_weight=req.tare_weight,
        net_weight=net_weight,
        tested_mc_pct=req.tested_mc_pct,
        tested_ash_pct=req.tested_ash_pct,
        tested_lhv_kcal=req.tested_lhv_kcal,
        contamination_pct=req.contamination_pct,
        qc_decision=req.qc_decision,
        accepted_qty_kg=accepted_qty,
        rejected_qty_kg=rejected_qty,
        rejection_reason=req.rejection_reason,
        qc_photo_url=req.qc_photo_url,
        allocated_ramp_id=allocated_ramp.id if allocated_ramp else None,
    )
    db.add(reception)
    await db.flush()

    dr_id = req.delivery_request_id
    if not dr_id:
        dr = DeliveryRequest(
            collector_id=req.collector_id,
            quantity_kg=net_weight,
            moisture_est=req.tested_mc_pct,
            ash_est=req.tested_ash_pct,
            proposed_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            proposed_price_per_kg=req.unit_price_rp,
            status=RequestStatus.REJECTED if accepted_qty == 0 else RequestStatus.ACCEPTED,
            logistics_carrier=req.logistics_carrier,
            note=f"Gate Reception {req.qc_decision}: {req.rejection_reason or ''}"
        )
        db.add(dr)
        await db.flush()
        dr_id = dr.id
    else:
        dr = await db.get(DeliveryRequest, dr_id)
        if dr and dr.quantity_kg > 0:
            sh_data = shrinkage_fields(dr.quantity_kg, net_weight)
            if sh_data.get("discrepancy_flag"):
                _audit.warning("Gate Reception %s susut melebihi batas toleransi: %s", reception.ticket_number, sh_data.get("discrepancy_note"))

    return_manifest = None
    reason_code = "lainnya"
    if rejected_qty > 0:
        if req.rejection_reason:
            r_lower = req.rejection_reason.lower()
            if "basah" in r_lower or req.tested_mc_pct > 25.0:
                reason_code = "basah"
            elif "jamur" in r_lower:
                reason_code = "berjamur"
            elif "kontaminan" in r_lower or req.contamination_pct > 5.0:
                reason_code = "kontaminan"
            elif "berat" in r_lower or "selisih" in r_lower:
                reason_code = "selisih_berat"

        rc = ReturnCase(
            request_id=dr_id,
            stage="gerbang_pabrik",
            reason_code=ReturnReason(reason_code),
            moisture=req.tested_mc_pct,
            quantity_kg=rejected_qty,
            location="pabrik",
            disposition=ReturnDisposition.RETURN_TO_SENDER,
            cost_bearer="pengepul",
            status="selesai",
            opened_by_id=user.id,
            resolved_by_id=user.id,
            note=req.rejection_reason,
            resolution_note=f"Surat Jalan Retur (Return Manifest) diterbitkan di gerbang pabrik untuk {rejected_qty} kg muatan ditolak.",
            resolved_at=datetime.now(timezone.utc),
        )
        db.add(rc)
        await db.flush()
        reception.return_case_id = rc.id
        return_manifest = {
            "return_case_id": rc.id,
            "stage": rc.stage,
            "disposition": rc.disposition.value if hasattr(rc.disposition, 'value') else str(rc.disposition),
            "cost_bearer": rc.cost_bearer,
            "quantity_kg": rc.quantity_kg,
            "reason_code": rc.reason_code.value if hasattr(rc.reason_code, 'value') else str(rc.reason_code),
            "note": rc.note,
        }

    # Teruskan timbangan & status ke harvest petani terlampir (propagasi custody sirkular)
    await factory_ops._receive_linked_harvests(
        db, user, dr_id, net_weight,
        rejected=(req.qc_decision == "REJECTED"),
        lot_code=reception.ticket_number,
        reject_category=reason_code if req.qc_decision == "REJECTED" else None,
        gross_kg=req.gross_weight,
        tare_kg=req.tare_weight,
        slip_url=req.qc_photo_url
    )

    # Release or fulfill stock locks for this collector & biomass
    from ..models.harvest import Harvest
    from ..models.trade import StockListing
    await db.execute(
        update(Harvest)
        .where(
            Harvest.collector_id == req.collector_id,
            Harvest.commodity == req.biomass_type,
            Harvest.is_locked.is_(True),
            Harvest.locked_by_mill_id == user.id
        )
        .values(is_locked=False, locked_by_mill_id=None, locked_at=None)
    )
    await db.execute(
        update(StockListing)
        .where(
            StockListing.commodity == req.biomass_type,
            StockListing.is_locked.is_(True),
            StockListing.locked_by_mill_id == user.id
        )
        .values(is_locked=False, locked_by_mill_id=None, locked_at=None)
    )

    eff_unit_price = req.unit_price_rp
    total_amount = round(accepted_qty * req.unit_price_rp)

    # Buat InboundQC lot record untuk bridging ke proses manufaktur batch
    qc_grade = "A" if req.tested_mc_pct <= 14.0 else ("B" if req.tested_mc_pct <= 18.0 else "C")
    qc_score = max(40.0, round(100.0 - req.tested_mc_pct - req.tested_ash_pct, 1))
    inb_decision = QCDecision.ACCEPT if req.qc_decision == "ACCEPTED" else (
        QCDecision.ACCEPT_PENALTY if req.qc_decision == "PARTIALLY_ACCEPTED" else QCDecision.REJECT
    )
    inbound_qc_obj = InboundQC(
        request_id=dr_id,
        gross_kg=req.gross_weight,
        tare_kg=req.tare_weight,
        net_kg=net_weight,
        payable_kg=accepted_qty,
        moisture=req.tested_mc_pct,
        ash=req.tested_ash_pct,
        volatile_matter=req.tested_lhv_kcal / 50.0 if req.tested_lhv_kcal else 70.0,
        fixed_carbon=15.0,
        contamination=req.contamination_pct,
        grade=qc_grade,
        score=qc_score,
        decision=inb_decision,
        final_price_per_kg=eff_unit_price,
        total_payment_rp=total_amount,
        remaining_kg=accepted_qty,
        verification_code=reception.ticket_number,
        evidence_photo_url=req.qc_photo_url,
        inspector_id=user.id,
        note=req.rejection_reason or f"Gate reception {reception.ticket_number}",
        rejected_kg=rejected_qty,
    )
    db.add(inbound_qc_obj)
    await db.flush()

    # Trigger settlement langsung ke dompet pengepul
    if accepted_qty > 0:
        await factory_ops.settle_qc(db, inbound_qc_obj, req.collector_id, user)

    invoice = None
    if accepted_qty > 0:
        inv_num = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=req.due_days)

        if req.payment_scheme == "CASH":
            dp_paid = float(total_amount)
            remaining = 0.0
            inv_status = "PAID"
            settled_at = now
        elif req.payment_scheme == "DP":
            dp_paid = min(float(req.dp_paid_amount), float(total_amount))
            remaining = float(total_amount) - dp_paid
            inv_status = "PARTIALLY_PAID" if dp_paid > 0 else "PENDING"
            settled_at = None
        else:
            dp_paid = 0.0
            remaining = float(total_amount)
            inv_status = "PENDING"
            settled_at = None

        invoice = FactoryInvoice(
            invoice_number=inv_num,
            mill_id=user.id,
            collector_id=req.collector_id,
            gate_reception_id=reception.id,
            biomass_type=req.biomass_type,
            billable_qty_kg=accepted_qty,
            unit_price_rp=eff_unit_price,
            total_amount_rp=float(total_amount),
            payment_scheme=req.payment_scheme,
            dp_paid_amount=dp_paid,
            remaining_amount=remaining,
            due_date=due_date,
            is_overdue=False,
            status=inv_status,
            settled_at=settled_at,
        )
        db.add(invoice)
        await db.flush()

    return {
        "success": True,
        "gate_ticket": {
            "id": reception.id,
            "ticket_number": reception.ticket_number,
            "vehicle_plate": reception.vehicle_plate,
            "driver_name": reception.driver_name,
            "carrier": reception.logistics_carrier,
            "biomass_type": reception.biomass_type,
            "gross_weight": reception.gross_weight,
            "tare_weight": reception.tare_weight,
            "net_weight": net_weight,
            "qc_decision": reception.qc_decision,
            "accepted_qty_kg": reception.accepted_qty_kg,
            "rejected_qty_kg": reception.rejected_qty_kg,
            "rejection_reason": reception.rejection_reason,
            "allocated_ramp": allocated_ramp.ramp_code if allocated_ramp else None,
            "return_case_id": reception.return_case_id,
        },
        "ramp_status": {
            "ramp_code": allocated_ramp.ramp_code,
            "new_stock_kg": allocated_ramp.current_stock_kg,
            "aggregate_mc": allocated_ramp.aggregate_mc,
            "aggregate_ash": allocated_ramp.aggregate_ash,
            "aggregate_lhv": allocated_ramp.aggregate_lhv_kcal,
        } if allocated_ramp else None,
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "total_amount_rp": invoice.total_amount_rp,
            "payment_scheme": invoice.payment_scheme,
            "dp_paid": invoice.dp_paid_amount,
            "remaining": invoice.remaining_amount,
            "status": invoice.status,
            "due_date": invoice.due_date.strftime("%Y-%m-%d"),
        } if invoice else None,
        "return_manifest": return_manifest,
        "message": f"✅ QC Selesai: {reception.qc_decision} ({accepted_qty} kg masuk ramp, {rejected_qty} kg ditolak).",
    }


@router.get("/gate-receptions")
async def list_gate_receptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    biomass_type: str | None = None,
):
    """Daftar riwayat penerimaan gerbang & hasil QC jembatan timbang."""
    query = select(GateReception).order_by(GateReception.id.desc())
    if biomass_type:
        query = query.where(GateReception.biomass_type == biomass_type)
    rows = (await db.execute(query.limit(100))).scalars().all()
    return [
        {
            "id": g.id,
            "ticket_number": g.ticket_number,
            "vehicle_plate": g.vehicle_plate,
            "driver_name": g.driver_name,
            "carrier": g.logistics_carrier,
            "biomass_type": g.biomass_type,
            "gross_weight": g.gross_weight,
            "tare_weight": g.tare_weight,
            "net_weight": g.net_weight,
            "qc_decision": g.qc_decision,
            "accepted_qty_kg": g.accepted_qty_kg,
            "rejected_qty_kg": g.rejected_qty_kg,
            "rejection_reason": g.rejection_reason,
            "qc_photo_url": g.qc_photo_url,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in rows
    ]


@router.get("/invoices")
async def list_factory_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
    biomass_type: str | None = None,
    status: str | None = None,
):
    """Daftar tagihan pabrik (Invoices) terkelompok berdasarkan biomassa & status jatuh tempo."""
    now = datetime.now(timezone.utc)
    
    query = (
        select(FactoryInvoice, User)
        .join(User, User.id == FactoryInvoice.collector_id)
        .order_by(FactoryInvoice.id.desc())
    )
    if biomass_type:
        query = query.where(FactoryInvoice.biomass_type == biomass_type)
    if status:
        query = query.where(FactoryInvoice.status == status)

    rows = (await db.execute(query.limit(100))).all()
    invoices_list = []
    for inv, col in rows:
        is_overdue = inv.status != "PAID" and inv.due_date < now
        if is_overdue and not inv.is_overdue:
            inv.is_overdue = True
            inv.status = "OVERDUE"
        
        invoices_list.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "collector_name": col.full_name,
            "biomass_type": inv.biomass_type,
            "billable_qty_kg": inv.billable_qty_kg,
            "unit_price_rp": inv.unit_price_rp,
            "total_amount_rp": inv.total_amount_rp,
            "payment_scheme": inv.payment_scheme,
            "dp_paid_amount": inv.dp_paid_amount,
            "remaining_amount": inv.remaining_amount,
            "due_date": inv.due_date.strftime("%Y-%m-%d"),
            "is_overdue": inv.is_overdue,
            "status": inv.status,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        })
    return invoices_list


@router.post("/invoices/{invoice_id}/pay")
async def pay_factory_invoice(
    invoice_id: int,
    req: InvoicePaymentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Pelunasan tagihan pabrik (Invoice TOP / DP) untuk membuka kembali pemblokiran order."""
    inv = (await db.execute(
        select(FactoryInvoice).where(FactoryInvoice.id == invoice_id).with_for_update()
    )).scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan.")

    inv.dp_paid_amount += req.amount_rp
    inv.remaining_amount = max(0.0, inv.total_amount_rp - inv.dp_paid_amount)
    if inv.remaining_amount <= 1e-6:
        inv.status = "PAID"
        inv.is_overdue = False
        inv.settled_at = datetime.now(timezone.utc)
    else:
        inv.status = "PARTIALLY_PAID"

    await db.flush()
    return {
        "success": True,
        "invoice_number": inv.invoice_number,
        "status": inv.status,
        "remaining_amount_rp": inv.remaining_amount,
        "is_overdue": inv.is_overdue,
        "message": f"Pembayaran Rp{req.amount_rp:g} berhasil dicatat. Sisa tagihan: Rp{inv.remaining_amount:g}."
    }
