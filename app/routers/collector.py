"""Router: Pengepul (📦) — Endpoints khusus pengepul/collector."""

import uuid
from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..params import P
from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyStage
from ..engines.quality import FeedstockSample, farmgate_price, score_sample
from ..models.trade import Bid, BidStatus, StockListing, ListingStatus
from ..models.circular import BiocharRequest
from ..models.factory_ops import DeliveryRequest
from ..models.route import Route, RouteStatus, RouteStop
from ..services import biomass as _biomass, factory_ops, trade
from ..services.qr_sign import new_qr_code
from ..services.custody import find_replay, load_harvest, pct_diff, transition
from ..engines.routing import plan_routes
from ..schemas.routing import RouteRequest

from ..security.url import EvidenceUrl
from ..services.privacy import PROXY_PHONE_PREFIX, has_real_phone, mask_phone
from .collector_bidding import router as bidding_router
from .collector_logistics import router as logistics_router

router = APIRouter()
router.include_router(bidding_router)
router.include_router(logistics_router)


class VerifyHarvestRequest(BaseModel):
    harvest_id: int
    weighed_kg: float = Field(..., gt=0, le=50000, description="Hasil timbangan pengepul (dasar harga)")
    actual_weighed_qty: float | None = Field(None, gt=0, le=50000, description="Hasil timbangan lapangan sebenarnya")
    moisture: float = Field(..., ge=0, le=95)     # bagasse/serbuk segar 50–70 %: tetap bisa "beli untuk dikeringkan"
    # F9: hanya kadar air (moisture meter) wajib di lapangan; abu/VM/FC diisi bila ada uji lab/NIR
    ash: float | None = Field(None, ge=0, le=40)
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    contamination: float = Field(0, ge=0, le=50)
    pyrolysis_temp_c: float = Field(500, ge=300, le=700)
    client_event_id: str | None = Field(None, max_length=64, description="Kunci idempotensi antrean offline")
    client_recorded_at: datetime | None = None
    evidence_photo_url: EvidenceUrl | None = Field(None, max_length=1000, description="Bukti foto serah-terima (opsional)")
    beli_untuk_dikeringkan: bool = Field(
        False, description="Mutu di bawah batas tolak tetap dibeli (harga basis kering) karena pengepul akan "
                           "mengeringkan/menyortir sendiri; risiko jamur ditanggung pengepul dan tercatat.")


class CancelPurchaseRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class PriceQuoteRequest(BaseModel):
    weighed_kg: float = Field(..., gt=0, le=50000)
    moisture: float = Field(..., ge=0, le=60)
    contamination: float = Field(0, ge=0, le=50)
    ash: float | None = Field(None, ge=0, le=40, description="Opsional - bila tidak diukur dipakai acuan menu Parameter")
    volatile_matter: float | None = Field(None, ge=0, le=100)
    fixed_carbon: float | None = Field(None, ge=0, le=100)
    harvest_id: int | None = Field(None, description="Isi untuk panen hasil lelang (harga kontrak)")


class RejectHarvestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    harvest_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    category: str = Field("lainnya", pattern="^(basah|berjamur|kontaminan|selisih_berat|stok_tidak_ada|lainnya)$",
                          description="Penyebab terstruktur → defect rate di laporan bulanan petani")
    client_event_id: str | None = Field(None, max_length=64)
    client_recorded_at: datetime | None = None


class ApproveInitialOfferRequest(BaseModel):
    agreed_price_per_kg: float | None = Field(None, gt=0, le=100_000)
    agreed_qty_kg: float | None = Field(None, gt=0, le=500_000)
    pickup_date: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=500)



@router.get("/available-harvests")
async def list_available_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    kecamatan: str | None = None,
    status: str | None = None,
    limit: int = 500,
):
    """Lihat laporan biomassa dari petani yang siap diverifikasi/diambil."""
    query = select(Harvest)
    if status == "verified":
        query = query.where(Harvest.status == HarvestStatus.VERIFIED)
    elif status == "reported":
        query = query.where(Harvest.status == HarvestStatus.REPORTED)
    else:
        query = query.where(Harvest.status.in_([HarvestStatus.REPORTED, HarvestStatus.VERIFIED]))

    query = query.where((Harvest.collector_id.is_(None)) | (Harvest.collector_id == user.id))
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
        # Pengepul tetap melihat lot yang khusus dialokasikan kepadanya meskipun di luar spesialisasi default
        query = query.where((Harvest.collector_id == user.id) | (Harvest.commodity == spec))

    if kecamatan:
        query = query.join(User, Harvest.farmer_id == User.id).where(
            User.kecamatan == kecamatan
        )
    query = query.order_by(Harvest.reported_at.desc()).limit(min(max(limit, 1), 1000))

    result = await db.execute(query)
    harvests = result.scalars().all()

    from ..models.biomass import BiomassParameter
    bp_rows = (await db.execute(select(BiomassParameter.code, BiomassParameter.name))).all()
    com_names = {r[0]: r[1] for r in bp_rows}

    # H1 fix: Batch-load all farmers in a single query instead of N+1
    farmer_ids = list({h.farmer_id for h in harvests if h.farmer_id})
    farmers_map = {}
    if farmer_ids:
        farmers_result = await db.execute(
            select(User).where(User.id.in_(farmer_ids))
        )
        farmers_map = {u.id: u for u in farmers_result.scalars().all()}

    # Lot hasil lelang milik saya + status DP → tombol DP langsung di antrean (mengikat kesepakatan)
    from ..models.compliance import FarmerDownPayment
    own_ids = [h.id for h in harvests if h.collector_id == user.id]
    dp_map = {d.harvest_id: d for d in (await db.execute(
        select(FarmerDownPayment).where(FarmerDownPayment.harvest_id.in_(own_ids)))).scalars()} if own_ids else {}
    results_list = []
    for h in harvests:
        farmer = farmers_map.get(h.farmer_id)
        dp = dp_map.get(h.id)
        c_code = h.commodity or "sekam_padi"
        c_name = com_names.get(c_code, c_code.replace("_", " ").title())
        results_list.append({
            "id": h.id,
            "quantity_kg": h.quantity_kg,
            "commodity": c_code,
            "commodity_name": c_name,
            "farmer_id": h.farmer_id,
            "farmer_name": farmer.full_name if farmer else f"Petani #{h.farmer_id}",
            # F12 minimisasi: nomor disamarkan di daftar lintas-pengguna; nomor lengkap via /harvests/{id}/contact
            "farmer_phone": mask_phone(farmer.phone) if farmer else None,
            "farmer_without_phone": bool(farmer and not has_real_phone(farmer.phone)),
            "kecamatan": farmer.kecamatan if farmer else None,
            "qr_code": h.qr_code,
            "origin_qr_code": h.origin_qr_code or h.qr_code,
            "wr_code": h.origin_qr_code or h.qr_code or f"WR-HV-{h.id:04d}",
            "listing_id": h.listing_id,
            "batch_ref": f"WR-LST-{h.listing_id:04d}" if h.listing_id else f"WR-HV-{h.id:04d}",
            "status": h.status.value if hasattr(h.status, "value") else str(h.status),
            "is_active": h.status == HarvestStatus.REPORTED,
            "photo_url": h.photo_url,
            "delivery_scheme": h.delivery_scheme or "jemput",
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
            "farmer_moisture_est": h.farmer_moisture_est, "farmer_grade_est": h.farmer_grade_est,
            "is_auction": h.listing_id is not None and h.collector_id == user.id,
            "agreed_price_per_kg": h.agreed_price_per_kg if h.collector_id == user.id else None,
            "dp": {"amount_rp": int(dp.amount_rp), "status": dp.status, "receipt_code": dp.receipt_code} if dp else None,
        })
    return results_list


def _biomass_grade(bio, moisture: float, contamination: float) -> dict:
    """Grade komoditas non-sekam dari acuan master: A ≤ MC acuan & kontaminan ≤ toleransi; TOLAK > MC tolak/kontaminan
    > 20 %. Harga tetap basis kering kontinu (tanpa tebing di batas grade) — grade hanya informasi mutu."""
    mid = (bio.moisture_ref_pct + bio.moisture_reject_pct) / 2
    if moisture > bio.moisture_reject_pct or contamination > 20:
        grade = "TOLAK"
    elif moisture <= bio.moisture_ref_pct and contamination <= bio.contaminant_tol_pct:
        grade = "A"
    elif moisture <= mid and contamination <= bio.contaminant_tol_pct + 3:
        grade = "B"
    else:
        grade = "C"
    score = max(0.0, round(100 - max(0.0, moisture - bio.moisture_ref_pct) * 3 - max(0.0, contamination - bio.contaminant_tol_pct) * 4, 1))
    return {"grade": grade, "score": score, "price_multiplier": 1.0, "commodity": bio.code,
            "basis": f"acuan {bio.name}: MC {bio.moisture_ref_pct:g}% (tolak > {bio.moisture_reject_pct:g}%), "
                     f"kontaminan ≤ {bio.contaminant_tol_pct:g}%"}


@router.post("/verify")
async def verify_harvest(
    req: VerifyHarvestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Timbang + uji mutu biomassa (Engine ②). Harga ke petani dihitung dari timbangan pengepul,
    bukan estimasi petani. Idempoten terhadap client_event_id (aman diulang dari antrean offline)."""
    replay = await find_replay(db, req.client_event_id)
    harvest = await load_harvest(db, req.harvest_id)
    if replay is None and harvest.status != HarvestStatus.REPORTED:
        raise HTTPException(409, f"Harvest sudah berstatus '{harvest.status.value}' — sudah diverifikasi atau diproses.")
    if harvest.collector_id is not None and harvest.collector_id != user.id:
        raise HTTPException(403, "Harvest ini hasil lelang pengepul lain.")

    # Isolasi spesialisasi bisnis pengepul
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

    if spec and harvest.commodity and harvest.commodity != spec:
        raise HTTPException(
            403,
            f"Isolasi spesialisasi: Pengepul ({user.full_name or user.username}) hanya diizinkan memverifikasi komoditas spesialisasinya ({spec}), bukan {harvest.commodity}."
        )

    bio = await _biomass.get_biomass(db, harvest.commodity, allow_inactive=True)   # lot lama tetap bisa diproses
    if bio.code == "sekam_padi":
        quality = score_sample(FeedstockSample(
            moisture=req.moisture, ash=req.ash, volatile_matter=req.volatile_matter, fixed_carbon=req.fixed_carbon,
            contamination=req.contamination, pyrolysis_temp_c=req.pyrolysis_temp_c,
        ))
    else:   # 018: komoditas lain dinilai dari acuan master (kadar air & kontaminan), bukan kurva mutu sekam
        quality = _biomass_grade(bio, req.moisture, req.contamination)
    estimate_gap = pct_diff(harvest.quantity_kg, req.weighed_kg)
    note = None
    if abs(estimate_gap) > P("sirkular.estimate_tolerance_pct"):
        note = (f"Estimasi petani {harvest.quantity_kg:g} kg vs timbangan {req.weighed_kg:g} kg "
                f"(selisih {estimate_gap:+.1f}%)")
    off_spec = quality["grade"] == "TOLAK"
    if off_spec and replay is None and not req.beli_untuk_dikeringkan:
        raise HTTPException(422, f"Mutu TOLAK (kadar air {req.moisture:g}% / kontaminan {req.contamination:g}%): "
                                 "Tolak agar biomassa tetap di petani untuk dikeringkan/disortir, atau centang "
                                 "'beli untuk dikeringkan' (harga basis kering, risiko ditanggung pengepul).")
    price_grade = "C" if off_spec else quality["grade"]     # dibeli di bawah spek: harga basis kering, bukan 0
    if harvest.agreed_price_per_kg:
        # Hasil lelang: harga kontrak; hanya dipotong bila lebih basah dari kadar air yang diiklankan petani
        listing = await db.get(StockListing, harvest.listing_id) if harvest.listing_id else None
        base_price = harvest.agreed_price_per_kg
        pricing = farmgate_price(base_price, req.weighed_kg, req.moisture, req.contamination, price_grade, 1.0,
                                 # tanpa MC di iklan: acuan komoditas (bukan acuan sekam 12 % — memotong bagasse ±43 %)
                                 reference_moisture=(listing.moisture_pct if listing and listing.moisture_pct is not None
                                                     else bio.moisture_ref_pct),
                                 wetter_only=True, method="basis_kering" if off_spec else None)
    elif bio.code == "sekam_padi":
        base_price = _biomass.base_price_for(bio)
        pricing = farmgate_price(base_price, req.weighed_kg, req.moisture, req.contamination, price_grade,
                                 quality["price_multiplier"], method="basis_kering" if off_spec else None)
    else:
        base_price = _biomass.base_price_for(bio)
        if base_price is None:
            raise HTTPException(422, f"Harga dasar {bio.name} belum diisi pabrik (menu Multi-biomassa → harga dasar).")
        # kotoran ≤ toleransi komoditas tidak dipotong — sama dengan pratinjau refraksi yang ditunjukkan ke petani
        pricing = farmgate_price(base_price, req.weighed_kg, req.moisture,
                                 max(0.0, req.contamination - bio.contaminant_tol_pct), price_grade, 1.0,
                                 reference_moisture=bio.moisture_ref_pct, wetter_only=True, method="basis_kering")
    if off_spec:
        note = "; ".join(x for x in (note, "Dibeli di bawah spek untuk dikeringkan/disortir pengepul") if x)
    total_price = pricing["total_price"]
    multiplier = round(pricing["price_per_kg"] / base_price, 4) if base_price else 0.0

    actual_qty = req.actual_weighed_qty or req.weighed_kg
    claimed_qty = harvest.quantity_kg or actual_qty
    dev_kg = round(actual_qty - claimed_qty, 2)
    dev_pct = round((dev_kg / claimed_qty) * 100, 2) if claimed_qty > 0 else 0.0
    qc_stat = "PASS" if (not off_spec or req.beli_untuk_dikeringkan) else "REJECT"
    qr_token = harvest.qr_verification_token or str(uuid.uuid4()).replace("-", "")

    event = await transition(
        db, req.harvest_id, harvest.status, HarvestStatus.VERIFIED, user, CustodyStage.COLLECTOR_WEIGH,
        weight_kg=actual_qty, client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at,
        note=note, evidence_photo_url=req.evidence_photo_url, collector_id=user.id, verified_kg=actual_qty, moisture=req.moisture, ash=req.ash,
        volatile_matter=req.volatile_matter, fixed_carbon=req.fixed_carbon, contamination=req.contamination,
        grade=quality["grade"], quality_score=quality["score"], verified_at=datetime.now(timezone.utc),
        base_price_per_kg=base_price, incentive_multiplier=multiplier, total_price=total_price,
        actual_weighed_qty=actual_qty,
        farmer_claimed_qty=claimed_qty,
        deviation_kg=dev_kg,
        deviation_pct=dev_pct,
        qc_status=qc_stat,
        qr_verification_token=qr_token,
    )
    harvest = await load_harvest(db, req.harvest_id)
    return {
        "harvest_id": harvest.id,
        "status": harvest.status.value,
        "grade": quality["grade"],
        "score": quality["score"],
        "weighed_kg": harvest.verified_kg,
        "verified_kg": harvest.verified_kg,
        "actual_weighed_qty": actual_qty,
        "farmer_estimate_kg": harvest.quantity_kg,
        "farmer_claimed_qty": claimed_qty,
        "deviation_kg": dev_kg,
        "deviation_pct": dev_pct,
        "estimate_gap_pct": round(estimate_gap, 2),
        "total_price": harvest.total_price,
        "qc_status": qc_stat,
        "qr_verification_token": qr_token,
        "quality_detail": quality,
        "replayed": replay is not None,
        "custody_event_id": event.id,
        "verification_code": event.verification_code,
        "qr_code": harvest.qr_code,
        "origin_qr_code": harvest.origin_qr_code or harvest.qr_code,
        "listing_id": harvest.listing_id,
        "batch_ref": f"WR-LST-{harvest.listing_id:04d}" if harvest.listing_id else f"WR-HV-{harvest.id:04d}",
        "price_basis": "harga lelang" if harvest.agreed_price_per_kg else (
            "basis kering" if pricing["method"] == "basis_kering" else "harga dasar × pengali mutu"),
        "pricing": pricing,
        "commodity": bio.code,
        "message": f"{bio.name} {harvest.verified_kg:g} kg dinilai Grade {quality['grade']} (skor {quality['score']})",
    }


@router.post("/reject")
async def reject_harvest(
    req: RejectHarvestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tolak laporan biomassa sebelum diangkut (mis. basah / terkontaminasi)."""
    harvest = await load_harvest(db, req.harvest_id)
    if harvest.collector_id is not None and harvest.collector_id != user.id:
        raise HTTPException(403, "Harvest ini hasil lelang pengepul lain.")
    event = await transition(
        db, req.harvest_id, HarvestStatus.REPORTED, HarvestStatus.REJECTED, user, CustodyStage.COLLECTOR_REJECT,
        client_event_id=req.client_event_id, client_recorded_at=req.client_recorded_at, note=req.reason,
        collector_id=user.id, rejected_reason=req.reason, rejected_at=datetime.now(timezone.utc),
        reject_category=req.category,
        qc_status="REJECT",
        qc_rejection_reason=req.reason,
    )
    return {"harvest_id": req.harvest_id, "status": "rejected", "custody_event_id": event.id, "qc_status": "REJECT"}


@router.post("/harvests/{harvest_id}/cancel-purchase")
async def cancel_purchase(
    harvest_id: int,
    body: CancelPurchaseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Batalkan pembelian: lelang yang belum ditimbang (stok petani dikembalikan) atau jemputan truk pabrik
    yang belum dimuat (ongkos jarak kosong dibebankan bila truk sudah berangkat)."""
    from ..services.logistics import cancel_purchase as _cancel
    return await _cancel(db, user, harvest_id, body.reason)


@router.post("/harvests/{harvest_id}/approve-initial")
async def approve_initial_offer(
    harvest_id: int,
    req: ApproveInitialOfferRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Pengepul menyetujui Qty & Harga awal dari penawaran biomassa petani.
    Status berubah menjadi 'Terverifikasi Pengepul' dan siap dijadwalkan / dioptimasi rute jemput."""
    harvest = await load_harvest(db, harvest_id)
    if harvest.status != HarvestStatus.REPORTED:
        raise HTTPException(409, f"Harvest #{harvest_id} sudah berstatus '{harvest.status.value}'.")

    # Isolasi spesialisasi bisnis pengepul
    spec = getattr(user, "specialization_commodity", None)
    if not spec:
        u_low = f"{(user.username or '')} {(user.full_name or '')}".lower()
        if "sekam" in u_low: spec = "sekam_padi"
        elif "jagung" in u_low: spec = "tongkol_jagung"
        elif "tebu" in u_low: spec = "ampas_tebu"
        elif "kayu" in u_low or "serat" in u_low or "sengon" in u_low: spec = "serbuk_sengon"

    if spec and harvest.commodity and harvest.commodity != spec:
        raise HTTPException(
            403,
            f"Isolasi spesialisasi: Pengepul ({user.full_name or user.username}) hanya diizinkan memproses {spec}, bukan {harvest.commodity}."
        )

    bio = await _biomass.get_biomass(db, harvest.commodity, allow_inactive=True)
    base_price = _biomass.base_price_for(bio) or 450.0
    agreed_price = req.agreed_price_per_kg or harvest.agreed_price_per_kg or base_price
    agreed_qty = req.agreed_qty_kg or harvest.quantity_kg
    total_val = round(agreed_qty * agreed_price, 2)

    note_text = req.note or f"Verifikasi awal Qty ({agreed_qty:g} kg) & Harga (Rp{agreed_price:g}/kg) disetujui pengepul."
    if req.pickup_date:
        note_text += f" Target penjemputan: {req.pickup_date}"

    qr_token = harvest.qr_verification_token or str(uuid.uuid4()).replace("-", "")

    event = await transition(
        db, harvest_id, HarvestStatus.REPORTED, HarvestStatus.VERIFIED, user, CustodyStage.COLLECTOR_WEIGH,
        weight_kg=agreed_qty,
        collector_id=user.id,
        verified_kg=agreed_qty,
        base_price_per_kg=agreed_price,
        total_price=total_val,
        actual_weighed_qty=agreed_qty,
        farmer_claimed_qty=harvest.quantity_kg,
        deviation_kg=0.0,
        deviation_pct=0.0,
        qc_status="PENDING",
        qr_verification_token=qr_token,
        note=note_text,
    )

    harvest.agreed_price_per_kg = agreed_price
    harvest.collector_id = user.id
    harvest.verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(harvest)

    return {
        "success": True,
        "message": f"Penawaran #{harvest.id} berhasil diverifikasi! Qty: {agreed_qty:g} kg, Harga: Rp{agreed_price:g}/kg disetujui.",
        "harvest_id": harvest.id,
        "status": harvest.status.value,
        "agreed_price_per_kg": agreed_price,
        "verified_kg": agreed_qty,
        "verification_code": event.verification_code,
        "custody_event_id": event.id,
    }



@router.post("/price-quote")
async def price_quote(
    body: PriceQuoteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Simulasi harga di depan petani SEBELUM timbang resmi: cukup berat + kadar air (+ kontaminan).
    Abu/VM/FC opsional - di lapangan biasanya hanya moisture meter yang tersedia."""
    ash = body.ash if body.ash is not None else P("rendemen.ref_ash")
    fc = body.fixed_carbon if body.fixed_carbon is not None else P("harga_mutu.fc_best")
    vm = body.volatile_matter if body.volatile_matter is not None else max(0.0, 100 - ash - fc)
    quality = score_sample(FeedstockSample(moisture=body.moisture, ash=ash, volatile_matter=vm, fixed_carbon=fc,
                                           contamination=body.contamination))
    base, ref, wetter_only, mult = P("harga_mutu.base_price_per_kg"), None, False, quality["price_multiplier"]
    if body.harvest_id:
        h = await load_harvest(db, body.harvest_id)
        if h.collector_id not in (None, user.id):
            raise HTTPException(404, "Harvest tidak ditemukan")
        if h.agreed_price_per_kg:
            listing = await db.get(StockListing, h.listing_id) if h.listing_id else None
            base, wetter_only, mult = h.agreed_price_per_kg, True, 1.0
            ref = listing.moisture_pct if listing and listing.moisture_pct else None
    pricing = farmgate_price(base, body.weighed_kg, body.moisture, body.contamination, quality["grade"], mult,
                             reference_moisture=ref, wetter_only=wetter_only)
    measured = [k for k in ("ash", "volatile_matter", "fixed_carbon") if getattr(body, k) is not None]
    return {"grade": quality["grade"], "score": quality["score"], "pricing": pricing,
            "measured_fields": ["moisture", "contamination", *measured],
            "estimated_fields": [k for k in ("ash", "volatile_matter", "fixed_carbon") if k not in measured],
            "warnings": quality["warnings"]}


@router.get("/returns")
async def my_returns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Kasus retur atas biomassa yang saya jual ke pabrik (lot QC / muatan rute yang ditolak atau disortir)."""
    from ..models.factory_ops import ReturnCase
    from ..services.logistics import return_dict
    from ..services.logistics import act_as_system
    await act_as_system(db)      # filter kepemilikan dilakukan di query di bawah
    q = (select(ReturnCase)
         .outerjoin(Harvest, Harvest.id == ReturnCase.harvest_id)
         .outerjoin(DeliveryRequest, DeliveryRequest.id == ReturnCase.request_id)
         .where((Harvest.collector_id == user.id) | (DeliveryRequest.collector_id == user.id))
         .order_by(ReturnCase.id.desc()).limit(200))
    return [return_dict(r) for r in (await db.execute(q)).scalars().all()]


@router.get("/daily-summary")
async def daily_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Ringkasan koleksi hari ini."""
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    next_day = start_of_day + timedelta(days=1)
    result = await db.execute(
        select(
            func.count(Harvest.id),
            func.sum(func.coalesce(Harvest.verified_kg, Harvest.quantity_kg)),
            func.avg(Harvest.quality_score),
            func.sum(Harvest.total_price),
        )
        .where(Harvest.collector_id == user.id)
        .where(Harvest.verified_at >= start_of_day)
        .where(Harvest.verified_at < next_day)
    )
    row = result.one()
    return {
        "date": start_of_day.date().isoformat(),
        "total_pickups": row[0] or 0,
        "total_kg": round(row[1] or 0, 1),
        "avg_quality_score": round(row[2] or 0, 1),
        "total_cost": round(row[3] or 0),
    }


# ---------------------------------------------------------------- B2B Procurement: Delivery Request ke pabrik

class DeliveryRequestCreate(BaseModel):
    quantity_kg: float = Field(..., gt=0, le=1_000_000)
    moisture_est: float = Field(..., ge=0, le=60)
    ash_est: float | None = Field(None, ge=0, le=60)
    grade_est: str | None = Field(None, pattern="^(A|B|C)$")
    proposed_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    proposed_price_per_kg: float = Field(..., gt=0, le=20_000)
    harvest_ids: list[int] = Field(default_factory=list, max_length=500,
                                   description="Harvest petani (sudah Anda timbang) yang ikut dikirim → dompet biochar")
    mill_id: int | None = Field(None, description="Pilihan pabrik tujuan")
    biomass_type: str = Field("sekam_padi", max_length=50, description="Jenis biomassa")
    logistics_carrier: str = Field("FACTORY_FLEET", pattern="^(FACTORY_FLEET|COLLECTOR_SELF)$",
                                   description="'FACTORY_FLEET' (Dijemput Armada Pabrik) | 'COLLECTOR_SELF' (Antar Mandiri Pengepul)")
    pricing_mode: str = Field("AUCTION", pattern="^(AUCTION|FACTORY_PRICE)$",
                              description="'AUCTION' (Tawar Bebas) | 'FACTORY_PRICE' (Ikut Acuan Pabrik)")
    note: str | None = Field(None, max_length=500)


class NegotiationAction(BaseModel):
    action: str = Field(..., pattern="^(accept|counter|reject|cancel)$")
    price_per_kg: float | None = Field(None, gt=0, le=20_000)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(None, max_length=500)


@router.get("/factory-price")
async def factory_price(
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    moisture: float = 11.0,
    ash: float | None = None,
):
    """Harga rekomendasi pabrik (target) untuk kadar air tertentu — dasar ajuan yang transparan."""
    if not 0 <= moisture <= 60:
        raise HTTPException(422, "Kadar air 0–60%")
    return factory_ops.factory_price_preview(moisture, ash)


@router.post("/delivery-requests", status_code=201)
async def create_delivery_request(
    req: DeliveryRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    r = await factory_ops.submit_request(db, user, req.model_dump())
    return factory_ops.request_dict(r)


@router.get("/delivery-requests")
async def my_delivery_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    rows = (await db.execute(select(DeliveryRequest).where(DeliveryRequest.collector_id == user.id)
                             .order_by(DeliveryRequest.id.desc()).limit(100))).scalars().all()
    return [factory_ops.request_dict(r) for r in rows]


@router.post("/delivery-requests/{request_id}/respond")
async def respond_delivery_request(
    request_id: int,
    body: NegotiationAction,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Jawab tawaran balik pabrik: accept | counter | reject, atau cancel ajuan."""
    try:
        r = await factory_ops.respond(db, user, request_id, body.action, body.price_per_kg, body.date, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return factory_ops.request_dict(r)


@router.get("/attachable-harvests")
async def attachable_harvests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Harvest petani yang sudah Anda timbang & belum terlampir di ajuan — bisa dikirim ke pabrik (→ dompet)."""
    active_routes = (
        select(RouteStop.harvest_id)
        .join(Route, RouteStop.route_id == Route.id)
        .where(
            RouteStop.harvest_id.is_not(None),
            Route.status.in_([RouteStatus.PLANNED, RouteStatus.IN_PROGRESS]),
        )
    )
    rows = (await db.execute(select(Harvest, User.full_name).join(User, User.id == Harvest.farmer_id)
                             .where(Harvest.collector_id == user.id, Harvest.status == HarvestStatus.VERIFIED,
                                    Harvest.delivery_request_id.is_(None),
                                    ~Harvest.id.in_(active_routes))
                             .order_by(Harvest.id.desc()).limit(200))).all()
    return [{"id": h.id, "farmer": name, "verified_kg": h.verified_kg, "moisture": h.moisture, "grade":
             h.grade.value if hasattr(h.grade, "value") else h.grade} for h, name in rows]



@router.get("/settlements")
async def my_settlements(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tagihan saya ke pabrik (jalur QC & jalur rute): menunggu harga / terutang / dibayar."""
    from sqlalchemy.orm import aliased
    from ..models.factory_ops import CollectorSettlement
    FarmerUser = aliased(User, name="farmer_user")
    q = (select(CollectorSettlement, FarmerUser.full_name.label("farmer_name"))
         .outerjoin(Harvest, Harvest.id == CollectorSettlement.harvest_id)
         .outerjoin(FarmerUser, FarmerUser.id == Harvest.farmer_id)
         .where(CollectorSettlement.collector_id == user.id)
         .order_by(CollectorSettlement.id.desc()).limit(300))
    rows = (await db.execute(q)).all()
    return [{**factory_ops.settlement_dict(s), "farmer_name": fname} for s, fname in rows]


@router.get("/settlements/{settlement_id}/history")
async def my_settlement_history(
    settlement_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Jejak audit tagihan milik pengepul yang sedang login."""
    from ..models.factory_ops import CollectorSettlement
    s = await db.get(CollectorSettlement, settlement_id)
    if s is None or s.collector_id != user.id:
        raise HTTPException(404, "Tagihan tidak ditemukan.")
    return await factory_ops.settlement_history(db, settlement_id)


# ======================================================================================================
# F7 — Petani tanpa HP: pengepul mendaftarkan & melaporkan atas nama petani (persetujuan lisan dicatat)

# ======================================================================================================
import logging as _logging
import secrets as _secrets
import uuid as _uuid

from sqlalchemy.exc import IntegrityError as _IntegrityError

from ..models.compliance import FarmerPayment
from ..models.harvest import Mill
from ..models.ledger import CustodyEvent
from ..services import payments as _payments
from ..services.custody import trusted_device_time
from ..services.phone import normalize_phone
from ..services.privacy import record_consents

_audit = _logging.getLogger("biochain.audit")


class ProxyFarmerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    # Disetarakan dengan pendaftaran petani mandiri (auth.RegisterRequest): nama, HP, kecamatan, kabupaten, lokasi
    full_name: str = Field(..., min_length=2, max_length=100)
    kecamatan: str | None = Field(None, max_length=100)
    kabupaten: str | None = Field(None, max_length=100)
    lat: float | None = Field(None, ge=-11, le=6, description="Lokasi sawah/gudang petani (GPS HP pengepul)")
    lon: float | None = Field(None, ge=95, le=141)
    desa: str | None = Field(None, max_length=100, description="Desa/dusun untuk membedakan nama yang sama")
    phone: str | None = Field(None, max_length=30, description="Opsional — HP keluarga/ketua kelompok tani")
    consent_given: bool = Field(..., description="Petani menyetujui (lisan) data dicatat oleh pengepul")


class ProxyHarvestRequest(BaseModel):
    # Field sama dengan laporan petani mandiri (farmer.HarvestReportRequest)
    farmer_id: int
    quantity_kg: float = Field(..., gt=0, le=50000)
    commodity: str = Field("sekam_padi", max_length=24, description="Kode komoditas (GET /api/v1/biomass)")
    mill_id: int | None = None
    moisture_est: float | None = Field(None, ge=0, le=60)
    grade_est: str | None = Field(None, pattern="^[ABCD]$")
    photo_url: EvidenceUrl | None = None
    client_event_id: str | None = Field(None, max_length=64)
    client_recorded_at: datetime | None = None


class PayFarmerRequest(BaseModel):
    method: str = Field(..., description="tunai | transfer | qris | ewallet")
    reference: str | None = Field(None, max_length=80)
    evidence_photo_url: EvidenceUrl | None = None
    client_event_id: str | None = Field(None, max_length=64)


def _proxy_dict(u: User) -> dict:
    return {"id": u.id, "full_name": u.full_name, "kecamatan": u.kecamatan,
            "phone": u.phone if has_real_phone(u.phone) else None, "username": u.username}


@router.post("/proxy-farmers", status_code=201)
async def create_proxy_farmer(req: ProxyFarmerRequest, db: Annotated[AsyncSession, Depends(get_db)],
                              user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Daftarkan petani yang tidak punya HP. Akun tidak bisa dipakai login sampai nomor HP & password diatur admin."""
    if not req.consent_given:
        raise HTTPException(422, "Tanyakan dulu persetujuan petani bahwa datanya dicatat (UU PDP).")
    phone = None
    if req.phone:
        phone = normalize_phone(req.phone)
        if phone is None:
            raise HTTPException(422, "Nomor HP tidak valid (boleh dikosongkan).")
        if (await db.execute(select(User.id).where(User.phone == phone))).first():
            raise HTTPException(409, "Nomor HP sudah terdaftar — gunakan akun petani tersebut.")
    from .auth import hash_password
    from ..concurrency import run_cpu
    name = req.full_name.strip() + (f" ({req.desa.strip()})" if req.desa else "")
    farmer = User(full_name=name[:100], role=UserRole.PETANI, is_active=True, kecamatan=req.kecamatan or user.kecamatan,
                  kabupaten=req.kabupaten or user.kabupaten, lat=req.lat, lon=req.lon, managed_by_id=user.id,
                  phone=phone or f"{PROXY_PHONE_PREFIX}{_uuid.uuid4().hex[:12].upper()}",
                  password_hash=await run_cpu(hash_password, _secrets.token_urlsafe(24)))
    db.add(farmer)
    await db.flush()
    await record_consents(db, farmer.id, {"layanan_inti": True}, method="lisan_via_pengepul", recorded_by_id=user.id)
    await db.commit()
    _audit.info("proxy_farmer_created", extra={"collector_id": user.id, "farmer_id": farmer.id})
    return _proxy_dict(farmer)


@router.get("/proxy-farmers")
async def list_proxy_farmers(db: Annotated[AsyncSession, Depends(get_db)],
                             user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    rows = (await db.execute(select(User).where(User.managed_by_id == user.id, User.anonymized_at.is_(None))
                             .order_by(User.full_name))).scalars().all()
    return [_proxy_dict(u) for u in rows]


@router.post("/proxy-harvest", status_code=201)
async def proxy_harvest(req: ProxyHarvestRequest, db: Annotated[AsyncSession, Depends(get_db)],
                        user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Lapor stok atas nama petani binaan (tanpa HP). Idempoten (client_event_id); nota QR dicetak untuk petani."""
    uid = user.id
    replay = await find_replay(db, req.client_event_id)
    if replay is not None:
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.collector_id != uid:                       # kunci idempotensi milik orang lain → jangan bocorkan lotnya
            raise HTTPException(409, "client_event_id sudah dipakai.")
        return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": h.farmer_id,
                "replayed": True, "message": "ℹ️ Laporan ini sudah tercatat sebelumnya."}
    farmer = await db.get(User, req.farmer_id)
    if farmer is None or farmer.managed_by_id != uid:
        raise HTTPException(403, "Hanya untuk petani binaan Anda (didaftarkan lewat 'Petani tanpa HP').")
    if req.mill_id is not None and not (await db.execute(select(Mill.id).where(Mill.id == req.mill_id))).first():
        raise HTTPException(422, "mill_id tidak dikenal")
    h_uuid = str(_uuid.uuid4())
    # collector_id = pelapor: lot binaan langsung ditangani pengepul ini (juga syarat RLS harvests di PostgreSQL)
    h = Harvest(uuid=h_uuid, farmer_id=farmer.id, mill_id=req.mill_id, quantity_kg=req.quantity_kg, collector_id=uid,
                commodity=(await _biomass.get_biomass(db, req.commodity)).code,
                status=HarvestStatus.REPORTED, qr_code=new_qr_code(h_uuid), photo_url=req.photo_url,
                farmer_moisture_est=req.moisture_est, farmer_grade_est=req.grade_est,
                reported_at=trusted_device_time(req.client_recorded_at)[0])
    db.add(h)
    await db.flush()
    db.add(CustodyEvent(harvest_id=h.id, stage=CustodyStage.FARMER_REPORT.value, from_status=None,
                        to_status=HarvestStatus.REPORTED.value, weight_kg=req.quantity_kg, actor_id=uid,
                        actor_role=UserRole.PENGEPUL.value, client_event_id=req.client_event_id,
                        client_recorded_at=req.client_recorded_at,
                        note=f"Dilaporkan pengepul atas nama petani tanpa HP (#{farmer.id})"))
    try:
        await db.commit()
    except _IntegrityError:
        await db.rollback()
        replay = await find_replay(db, req.client_event_id)
        if replay is None:
            raise
        h = (await db.execute(select(Harvest).where(Harvest.id == replay.harvest_id))).scalar_one()
        if h.collector_id != uid:
            raise HTTPException(409, "client_event_id sudah dipakai.")
        return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": h.farmer_id,
                "replayed": True, "message": "ℹ️ Laporan ini sudah tercatat sebelumnya."}
    return {"id": h.id, "qr_code": h.qr_code, "quantity_kg": h.quantity_kg, "farmer_id": farmer.id,
            "farmer_name": farmer.full_name, "replayed": False,
            "message": f"✅ {req.quantity_kg:g} kg dilaporkan atas nama {farmer.full_name}. Cetak/foto nota QR untuk petani."}


@router.get("/harvests/{harvest_id}/contact")
async def farmer_contact(harvest_id: int, db: Annotated[AsyncSession, Depends(get_db)],
                         user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Nomor HP lengkap petani untuk mengatur penjemputan — akses dicatat (akuntabilitas PDP)."""
    h = (await db.execute(select(Harvest).where(Harvest.id == harvest_id))).scalar_one_or_none()
    if h is None:
        raise HTTPException(404, "Harvest tidak ditemukan")
    if h.collector_id not in (None, user.id):
        raise HTTPException(403, "Lot ini sudah ditangani pengepul lain.")
    farmer = await db.get(User, h.farmer_id)
    _audit.info("farmer_contact_viewed", extra={"collector_id": user.id, "harvest_id": h.id, "farmer_id": h.farmer_id})
    no_phone = not has_real_phone(farmer.phone)
    return {"harvest_id": h.id, "farmer_name": farmer.full_name, "phone": None if no_phone else farmer.phone,
            "without_phone": no_phone, "managed_by_me": farmer.managed_by_id == user.id,
            "kecamatan": farmer.kecamatan}


@router.get("/unpaid-harvests")
async def unpaid_harvests(db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Lot yang sudah saya timbang tetapi belum tercatat dibayar ke petani (F8)."""
    return await _payments.unpaid_for_collector(db, user)


@router.post("/harvests/{harvest_id}/pay-farmer", status_code=201)
async def pay_farmer(harvest_id: int, req: PayFarmerRequest, db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Catat pembayaran ke petani + terbitkan kuitansi BYR (Rupiah bulat, NUMERIC). Idempoten (client_event_id)."""
    return await _payments.pay_farmer(db, user, harvest_id, req.method, req.reference, req.evidence_photo_url,
                                      req.client_event_id)


class DownPaymentRequest(BaseModel):
    amount_rp: float = Field(..., gt=0, le=1_000_000_000)
    method: str = Field(..., pattern="^(tunai|transfer|qris|ewallet)$")
    reference: str | None = Field(None, max_length=80)
    client_event_id: str | None = Field(None, max_length=64)


@router.post("/harvests/{harvest_id}/pay-dp", status_code=201)
async def pay_dp(harvest_id: int, req: DownPaymentRequest, db: Annotated[AsyncSession, Depends(get_db)],
                 user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Uang muka ke petani (kuitansi DP-…); dipotong otomatis saat pelunasan BYR."""
    return await _payments.pay_down_payment(db, user, harvest_id, req.amount_rp, req.method, req.reference,
                                            req.client_event_id)


@router.get("/charges")
async def my_charges(db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    """Potongan logistik atas nama saya (ongkos jarak kosong batal/stok tidak ada)."""
    from ..models.factory_ops import LogisticsCharge
    from ..services.logistics import charge_dict
    rows = (await db.execute(select(LogisticsCharge).where(LogisticsCharge.collector_id == user.id)
                             .order_by(LogisticsCharge.id.desc()).limit(100))).scalars().all()
    return [charge_dict(c) for c in rows]


@router.get("/farmer-payments")
async def my_farmer_payments(db: Annotated[AsyncSession, Depends(get_db)],
                             user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))]):
    rows = (await db.execute(select(FarmerPayment).where(FarmerPayment.collector_id == user.id)
                             .order_by(FarmerPayment.id.desc()).limit(200))).scalars().all()
    return [_payments.payment_dict(p) for p in rows]


@router.get("/factory-receivables")

async def factory_receivables(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Daftar piutang dan status penerimaan Delivery Request dari pabrik-pabrik pembeli."""
    drs = (await db.execute(
        select(DeliveryRequest)
        .where(DeliveryRequest.collector_id == user.id)
        .order_by(DeliveryRequest.id.desc())
        .limit(100)
    )).scalars().all()

    now_utc = datetime.now(timezone.utc)
    total_unpaid_rp = 0.0
    items = []
    for dr in drs:
        price_per_kg = dr.agreed_price_per_kg or dr.proposed_price_per_kg or 450.0
        kg = dr.quantity_kg or 0.0
        amount = round(kg * price_per_kg)
        
        status_str = dr.status.value if hasattr(dr.status, "value") else str(dr.status)
        is_settled = status_str in ("settled", "paid", "delivered")
        if not is_settled:
            total_unpaid_rp += amount
            
        c_at = dr.created_at
        days_outstanding = (now_utc - (c_at.replace(tzinfo=timezone.utc) if c_at.tzinfo is None else c_at)).days if c_at else 0

        items.append({
            "delivery_request_id": dr.id,
            "request_code": f"DR-{dr.id:04d}",
            "factory_name": "Pabrik Biochar Sleman",
            "quantity_kg": kg,
            "price_per_kg": price_per_kg,
            "amount_rp": amount,
            "status": status_str,
            "is_settled": is_settled,
            "days_outstanding": days_outstanding,
            "created_at": c_at.isoformat() if c_at else None,
        })

    return {
        "collector_id": user.id,
        "total_unpaid_rp": total_unpaid_rp,
        "pending_invoices_count": len([i for i in items if not i["is_settled"]]),
        "items": items,
    }


# -----------------------------------------------------------------------------
# FASE 4: Collector Gate Feedback & Quality Rejection Logs
# -----------------------------------------------------------------------------
@router.get("/gate-feedback")
async def get_collector_gate_feedback(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Riwayat transparansi penerimaan gerbang pabrik, hasil timbangan, penolakan QC, dan saran peningkatan mutu."""
    from ..models.industrial import GateReception

    rows = (await db.execute(
        select(GateReception)
        .where(GateReception.collector_id == user.id)
        .order_by(GateReception.id.desc())
        .limit(100)
    )).scalars().all()

    feedback_list = []
    for g in rows:
        recs = []
        if g.tested_mc_pct > 20.0:
            recs.append(f"Kadar air {g.tested_mc_pct}% terlalu lembab. Lakukan penjemuran terpal.")
        if g.tested_ash_pct > 15.0 and "sekam" in g.biomass_type:
            recs.append(f"Kandungan pasir/tanah menyebabkan abu {g.tested_ash_pct}%.")
        if g.contamination_pct > 5.0:
            recs.append(f"Kontaminasi {g.contamination_pct}% terdeteksi.")
        if not recs and g.qc_decision == "ACCEPTED":
            recs.append("Kualitas prima memenuhi standar pabrik.")

        feedback_list.append({
            "ticket_number": g.ticket_number,
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

    return {
        "collector_id": user.id,
        "total_deliveries": len(rows),
        "total_accepted_kg": sum(g.accepted_qty_kg for g in rows),
        "total_rejected_kg": sum(g.rejected_qty_kg for g in rows),
        "items": feedback_list,
    }
