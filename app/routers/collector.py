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
from ..models.harvest import Harvest, HarvestStatus, QualityGrade
from ..models.ledger import CustodyStage
from ..engines.quality import FeedstockSample, farmgate_price, score_sample
from ..models.trade import Bid, BidStatus, StockListing, CollectorPaymentReputation, ListingStatus
from ..models.circular import BiocharRequest
from ..models.factory_ops import DeliveryRequest
from ..models.route import Route, RouteStatus, RouteStop
from ..services import biomass as _biomass, factory_ops, trade
from ..services.qr_sign import new_qr_code
from ..services.custody import find_replay, load_harvest, pct_diff, transition
from ..engines.routing import plan_routes, road_km
from ..schemas.routing import RouteRequest

from ..security.url import EvidenceUrl
from ..services.privacy import PROXY_PHONE_PREFIX, has_real_phone, mask_phone

router = APIRouter()


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


# ---------------------------------------------------------------- Pasar B2B: lihat stok, menawar, penasihat harga
class BidCreate(BaseModel):
    listing_id: int = Field(..., gt=0)
    scheme: str = Field(..., pattern="^(jemput|antar)$")
    price_per_kg: float = Field(..., gt=0, le=10_000)
    quantity_kg: float = Field(..., gt=0, le=200_000, description="Boleh sebagian dari stok")
    pickup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    pickup_schedule_proposed: datetime | None = None
    logistics_mode: str = Field("PICKUP", pattern="^(PICKUP|DELIVER_SELF)$")
    payment_term: str = Field("COD", pattern="^(COD|DP|TEMPO_7D)$")
    note: str | None = Field(None, max_length=500)


class BidAdviceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: int = Field(..., gt=0)
    scheme: str = Field("jemput", pattern="^(jemput|antar)$")
    resale_price_per_kg: float | None = Field(None, gt=0, description="Harga jual ke pabrik (Rp/kg), opsional")
    resale_price: float | None = Field(None, gt=0, description="Alias harga jual ke pabrik")
    margin_per_kg: float = Field(default_factory=lambda: P("pasar.default_margin_per_kg"), ge=0)
    margin_pct: float | None = Field(None, ge=0, le=50,
                                     description="Margin dalam % harga jual; bila diisi menggantikan margin_per_kg")
    cost_per_km: float = Field(default_factory=lambda: P("logistik.cost_per_km"), ge=0)
    vehicle_m3: float = Field(default_factory=lambda: P("logistik.vehicle_m3"), gt=0)
    quantity_kg: float | None = Field(None, gt=0, le=200_000)

    @model_validator(mode="before")
    @classmethod
    def resolve_resale_price(cls, data: any):
        if isinstance(data, dict):
            rp = data.get("resale_price_per_kg") or data.get("resale_price")
            if rp is None:
                rp = float(P("pabrik.base_purchase_price_rp_kg", 650.0) or 650.0)
            data["resale_price_per_kg"] = float(rp)
        return data


@router.get("/market")
async def market(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Stok petani yang masih terbuka, terurut jarak dari gudang pengepul (terfilter spesialisasi)."""
    query = select(StockListing).where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
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
        query = query.where(StockListing.commodity == spec)

    rows = (await db.execute(query.order_by(StockListing.id.desc()).limit(200))).scalars().all()
    origin = (user.lat, user.lon) if user.lat is not None else None
    mine = {b.listing_id: b for b in (await db.execute(select(Bid).where(
        Bid.collector_id == user.id, Bid.status == BidStatus.ACTIVE))).scalars().all()}
    out = []
    for r in rows:
        d = trade.listing_dict(r, origin)
        d["my_active_bid"] = ({"bid_id": mine[r.id].id, "price_per_kg": mine[r.id].price_per_kg,
                               "quantity_kg": mine[r.id].quantity_kg} if r.id in mine else None)
        out.append(d)
    return sorted(out, key=lambda d: d.get("distance_km", 1e9))


@router.post("/bids", status_code=201)
async def create_bid(
    req: BidCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    try:
        bid = await trade.place_bid(db, user, req.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"bid_id": bid.id, "status": "active", "scheme": bid.scheme.value, "price_per_kg": bid.price_per_kg,
            "quantity_kg": bid.quantity_kg}


@router.get("/bids")
async def my_bids(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    rows = (await db.execute(select(Bid).where(Bid.collector_id == user.id).order_by(Bid.id.desc()).limit(100))).scalars().all()
    return [{"bid_id": b.id, "listing_id": b.listing_id, "scheme": b.scheme.value, "price_per_kg": b.price_per_kg,
             "quantity_kg": b.quantity_kg, "accepted_kg": b.accepted_kg, "status": b.status.value} for b in rows]


@router.post("/bids/{bid_id}/withdraw")
async def withdraw_bid(
    bid_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    res = await db.execute(update(Bid).where(Bid.id == bid_id, Bid.collector_id == user.id,
                                             Bid.status == BidStatus.ACTIVE)
                           .values(status=BidStatus.WITHDRAWN, decided_at=datetime.now(timezone.utc)))
    if res.rowcount != 1:
        raise HTTPException(409, "Tawaran tidak aktif atau bukan milik Anda.")
    return {"bid_id": bid_id, "status": "withdrawn"}


@router.post("/bid-advisor")
async def bid_advisor(
    req: BidAdviceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Tawaran maksimum yang masih untung (netback) dengan biaya logistik marginal dari solver rute."""
    margin = req.margin_per_kg if req.margin_pct is None else req.resale_price_per_kg * req.margin_pct / 100
    try:
        out = await trade.bid_advice(db, user, req.listing_id, req.scheme, req.resale_price_per_kg,
                                     margin, req.cost_per_km, req.vehicle_m3, req.quantity_kg)
        out["margin_per_kg"] = round(margin, 1)
        out["margin_pct"] = round(margin / req.resale_price_per_kg * 100, 2)
        return out
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


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


class PickupPlanRequest(BaseModel):
    bid_ids: list[int] | None = None
    vehicle_m3: float | None = Field(None, gt=0, le=1000)
    cost_per_km: float | None = Field(None, ge=0)
    time_budget_ms: int = Field(500, ge=10, le=2000)


@router.post("/pickup-plan")
async def pickup_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
    req: PickupPlanRequest | None = None,
):
    """Rencana rute penjemputan optimal untuk tawaran yang dimenangkan pengepul berskema jemput."""
    from ..models.trade import Bid, BidStatus, DeliveryScheme, StockListing
    from ..models.harvest import Harvest, HarvestStatus
    from ..engines.routing import plan_routes
    from ..schemas.routing import RouteRequest

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
    from ..models.circular import BiocharCircularRequest, BiocharRequest
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
    from ..concurrency import run_cpu
    res = await run_cpu(plan_routes, depot, mills, route_req)      # CPU-bound: jangan bekukan event loop
    total_ton = res["summary"]["total_ton"]
    total_cost = res["summary"]["total_cost"]
    res["summary"]["cost_per_kg"] = round(total_cost / (total_ton * 1000), 2) if total_ton > 0 else 0.0
    res["summary"]["total_biochar_backhaul_kg"] = total_biochar_backhaul_kg
    res["summary"]["biochar_backhaul_detected"] = total_biochar_backhaul_kg > 0
    return res



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


# ---------------------------------------------------------------- Omni 022: Market Grouped, Consolidated Routing & Receivables
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

class ConsolidatedPickupPlanRequest(BaseModel):
    harvest_ids: list[int] = Field(..., min_length=1)
    vehicle_plate: str | None = "AB 8421 CS"
    truck_max_kg: float = Field(5000.0, gt=0)
    truck_max_m3: float = Field(30.0, gt=0)
    biochar_backhaul_requests: list[int] | None = None
    vehicle_choice: str | None = None
    driver_choice: str | None = None
    schedule_day: str | None = None
    pickup_date: str | None = None
    fleet_mode: str | None = "single"


@router.get("/market-grouped")
async def market_grouped(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
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

    q = select(StockListing).where(StockListing.status.in_(trade.OPEN_STATES), StockListing.remaining_kg > 1e-6)
    if spec:
        q = q.where(StockListing.commodity == spec)

    rows = (await db.execute(q.order_by(StockListing.id.desc()).limit(300))).scalars().all()
    origin = (user.lat, user.lon) if user.lat is not None else None
    mine = {b.listing_id: b for b in (await db.execute(
        select(Bid).where(Bid.collector_id == user.id, Bid.status == BidStatus.ACTIVE)
    )).scalars().all()}

    grouped: dict[str, dict] = {}
    for r in rows:
        c_code = r.commodity or "sekam_padi"
        if c_code not in grouped:
            grouped[c_code] = {
                "commodity": c_code,
                "total_stock_kg": 0.0,
                "direct_count": 0,
                "bidding_count": 0,
                "direct_listings": [],
                "bidding_listings": [],
            }
        item = trade.listing_dict(r, origin)
        item["my_active_bid"] = ({"bid_id": mine[r.id].id, "price_per_kg": mine[r.id].price_per_kg,
                                  "quantity_kg": mine[r.id].quantity_kg} if r.id in mine else None)
        grouped[c_code]["total_stock_kg"] = round(grouped[c_code]["total_stock_kg"] + r.remaining_kg, 2)
        if getattr(r, "transaction_mode", "DIRECT") == "BIDDING":
            grouped[c_code]["bidding_count"] += 1
            grouped[c_code]["bidding_listings"].append(item)
        else:
            grouped[c_code]["direct_count"] += 1
            grouped[c_code]["direct_listings"].append(item)

    return list(grouped.values())


@router.get("/offers-dashboard")
async def get_offers_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Dashboard Status Penawaran Pengepul Spesialis (Grouped & Sorted per Biomassa).
    Terbagi menjadi 2 Tab: 'Langsung Diambil' dan 'Lelang'.
    Format Kolom:
    Nama Petani | Jenis Biomassa | Qty (kg) | Kualitas | Pilihan Kirim | Harga/kg | Keterangan | Aksi Finalisasi
    """
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

    from ..models.harvest import Mill
    from ..models.circular import BiocharCircularRequest

    listings_q = select(StockListing).where(
        StockListing.status.in_(trade.OPEN_STATES),
        StockListing.remaining_kg > 1e-6
    )
    # Bursa lelang terbuka untuk seluruh akun pengepul agar dapat ditawar
    listings = (await db.execute(listings_q.order_by(StockListing.id.desc()))).scalars().all()

    # Preload farmers
    f_ids = list({l.farmer_id for l in listings if l.farmer_id})
    farmers_map = {}
    if f_ids:
        f_res = await db.execute(select(User).where(User.id.in_(f_ids)))
        farmers_map = {u.id: u for u in f_res.scalars().all()}

    # Preload all mills
    mills_res = await db.execute(select(Mill))
    mills_map = {m.id: m for m in mills_res.scalars().all()}

    # My active bids
    mine = {b.listing_id: b for b in (await db.execute(
        select(Bid).where(Bid.collector_id == user.id, Bid.status == BidStatus.ACTIVE)
    )).scalars().all()}

    # Muat panen aktif (Harvest status REPORTED & VERIFIED) milik pengepul ini (hasil lelang yang sudah deal / lapor langsung)
    active_h_q = select(Harvest).where(
        Harvest.status.in_([HarvestStatus.REPORTED, HarvestStatus.VERIFIED]),
        (Harvest.collector_id == user.id) | (Harvest.collector_id.is_(None))
    )
    if spec:
        active_h_q = active_h_q.where((Harvest.collector_id == user.id) | (Harvest.commodity == spec))
    active_harvests = (await db.execute(active_h_q.order_by(Harvest.id.desc()))).scalars().all()

    # Preload additional farmers from active_harvests
    h_fids = list({h.farmer_id for h in active_harvests if h.farmer_id and h.farmer_id not in farmers_map})
    if h_fids:
        h_fres = await db.execute(select(User).where(User.id.in_(h_fids)))
        for u in h_fres.scalars().all():
            farmers_map[u.id] = u

    # Preload linked harvests for listings to obtain genuine QR / WR codes
    l_ids = [l.id for l in listings]
    linked_harvests_map = {}
    if l_ids:
        lh_res = await db.execute(select(Harvest).where(Harvest.listing_id.in_(l_ids)))
        for lh in lh_res.scalars().all():
            linked_harvests_map[lh.listing_id] = lh

    # Preload Biochar requests
    all_h_ids = list({h.id for h in active_harvests} | {lh.id for lh in linked_harvests_map.values()})
    bcr_by_harvest = {}
    bcr_by_listing = {}
    if all_h_ids or l_ids:
        bcr_q = select(BiocharCircularRequest).where(
            (BiocharCircularRequest.harvest_id.in_(all_h_ids)) |
            (BiocharCircularRequest.listing_id.in_(l_ids))
        )
        bcr_rows = (await db.execute(bcr_q)).scalars().all()
        for b in bcr_rows:
            if b.harvest_id:
                bcr_by_harvest[b.harvest_id] = b
            if b.listing_id:
                bcr_by_listing[b.listing_id] = b

    langsung_diambil = []
    lelang = []

    for l in listings:
        farmer = farmers_map.get(l.farmer_id)
        f_name = farmer.full_name if farmer else f"Petani #{l.farmer_id}"
        c_code = l.commodity or "sekam_padi"
        b_name = c_code.replace("_", " ").title()

        linked_h = linked_harvests_map.get(l.id)
        origin_code = getattr(l, "origin_qr_code", None) or (linked_h.origin_qr_code if linked_h else None) or (linked_h.qr_code if linked_h else None) or f"WR-LST-{l.id:04d}"
        wr_code = origin_code

        mc_val = l.moisture_pct if l.moisture_pct is not None else (linked_h.farmer_moisture_est if linked_h else None)
        gr_val = l.grade_estimate or (linked_h.farmer_grade_est if linked_h else None)
        qual_parts = []
        if mc_val is not None:
            qual_parts.append(f"Kadar Air {mc_val:.1f}%")
        if gr_val:
            qual_parts.append(f"Grade {gr_val}")
        kualitas = ", ".join(qual_parts) if qual_parts else "-"

        pilihan_kirim = "Dijemput Pengepul" if l.allow_jemput and not l.allow_antar else (
            "Antar Mandiri" if l.allow_antar and not l.allow_jemput else "Dijemput / Antar"
        )

        hrg = l.ask_price_jemput or l.ask_price_antar or l.floor_price or 450.0
        my_bid = mine.get(l.id)

        mill_obj = mills_map.get(l.mill_id or (linked_h.mill_id if linked_h else None))
        titik_pasok = f"{mill_obj.name} ({mill_obj.kecamatan})" if mill_obj else (
            f"Kec. {farmer.kecamatan}" if (farmer and farmer.kecamatan) else "Lahan Petani"
        )

        bcr = bcr_by_listing.get(l.id) or (bcr_by_harvest.get(linked_h.id) if linked_h else None)
        biochar_info = None
        if bcr:
            biochar_info = {
                "request_code": bcr.request_code,
                "requested_kg": bcr.requested_kg,
                "land_area_ha": bcr.land_area_ha,
                "delivery_point": bcr.delivery_point,
                "status": bcr.status,
            }
        elif linked_h and linked_h.biochar_backhaul_requested and linked_h.biochar_backhaul_kg:
            biochar_info = {
                "request_code": None,
                "requested_kg": linked_h.biochar_backhaul_kg,
                "land_area_ha": None,
                "delivery_point": "Lahan Petani",
                "status": "REQUESTED",
            }

        status_val = l.status.value if hasattr(l.status, "value") else str(l.status)
        is_act = (l.status in trade.OPEN_STATES and l.remaining_kg > 1e-6)
        is_verif = bool(linked_h and linked_h.status == HarvestStatus.VERIFIED)
        status_lbl = "🟢 Aktif (Siap Ditawar)" if l.status == ListingStatus.OPEN else (
            f"🟡 Sebagian Deal ({l.remaining_kg:.0f} kg sisa)" if l.status == ListingStatus.PARTIAL else (
                "🔵 Deal Terverifikasi" if is_verif else (
                    "⚪ Selesai (Lelang Ditutup)" if l.status == ListingStatus.CLOSED else "🔴 Dibatalkan"
                )
            )
        )

        # Preload custody TRX code if linked harvest exists
        linked_trx = None
        if linked_h:
            cev_row = (await db.execute(select(CustodyEvent.verification_code).where(
                CustodyEvent.harvest_id == linked_h.id, CustodyEvent.verification_code.is_not(None)
            ).limit(1))).scalar_one_or_none()
            linked_trx = cev_row

        item = {
            "listing_id": l.id,
            "harvest_id": linked_h.id if linked_h else None,
            "wr_code": wr_code,
            "origin_qr_code": origin_code,
            "trx_code": linked_trx,
            "batch_ref": f"WR-LST-{l.id:04d}",
            "status": status_val,
            "is_active": is_act,
            "status_label": status_lbl,
            "is_verified_initial": is_verif,
            "verification_stage": "verified" if is_verif else "unverified",
            "verification_label": "🔵 Sudah Terverifikasi (Deal)" if is_verif else "🟡 Belum Verifikasi (Lelang Berjalan)",
            "nama_petani": f_name,
            "farmer_phone": farmer.phone if farmer else None,
            "kecamatan": farmer.kecamatan if farmer else None,
            "jenis_biomassa": b_name,
            "commodity_code": c_code,
            "qty_kg": l.remaining_kg,
            "farmer_claimed_qty": getattr(l, "farmer_claimed_qty", l.quantity_kg),
            "kualitas": kualitas,
            "moisture_est": mc_val,
            "grade_est": gr_val,
            "pilihan_kirim": pilihan_kirim,
            "logistics_mode": getattr(l, "logistics_mode", "PICKUP"),
            "delivery_scheme": "antar" if l.allow_antar and not l.allow_jemput else "jemput",
            "harga_per_kg": hrg,
            "floor_price": hrg,
            "titik_pasok": titik_pasok,
            "mill_id": l.mill_id or (linked_h.mill_id if linked_h else None),
            "photo_url": l.evidence_photo_url or (linked_h.photo_url if linked_h else None),
            "biochar_request": biochar_info,
            "reported_at": l.created_at.isoformat() if l.created_at else None,
            "transaction_mode": "BIDDING",
            "keterangan": f"Bursa lelang aktif (Batas min: Rp{hrg:g}/kg)",
            "aksi_finalisasi": "Beri Penawaran",
            "my_active_bid": {"bid_id": my_bid.id, "price": my_bid.price_per_kg, "qty": my_bid.quantity_kg} if my_bid else None,
            "is_locked": getattr(l, "is_locked", False),
        }

        # Seluruh listing pasar bursa lelang masuk ke tab lelang untuk proses tawar-menawar harga
        lelang.append(item)

    existing_h_ids = {item.get("harvest_id") for item in langsung_diambil if item.get("harvest_id")}
    diantar_petani = []

    for h in active_harvests:
        if h.id in existing_h_ids:
            continue
        farmer = farmers_map.get(h.farmer_id)
        f_name = farmer.full_name if farmer else f"Petani #{h.farmer_id}"
        c_code = h.commodity or "sekam_padi"
        b_name = c_code.replace("_", " ").title()

        wr_code = h.origin_qr_code or h.qr_code or f"WR-HV-{h.id:04d}"

        mc_val = h.farmer_moisture_est
        gr_val = h.farmer_grade_est
        qual_parts = []
        if mc_val is not None:
            qual_parts.append(f"Kadar Air {mc_val:.1f}%")
        if gr_val:
            qual_parts.append(f"Grade {gr_val}")
        kualitas = ", ".join(qual_parts) if qual_parts else "-"

        is_antar = (h.delivery_scheme == "antar") or (getattr(h, "logistics_mode", "") == "DELIVER_SELF")
        pilihan_kirim = "Antar Mandiri" if is_antar else "Dijemput Pengepul"
        hrg = h.agreed_price_per_kg or 450.0

        mill_obj = mills_map.get(h.mill_id)
        titik_pasok = f"{mill_obj.name} ({mill_obj.kecamatan})" if mill_obj else (
            f"Kec. {farmer.kecamatan}" if (farmer and farmer.kecamatan) else "Lahan Petani"
        )

        bcr = bcr_by_harvest.get(h.id) or (bcr_by_listing.get(h.listing_id) if h.listing_id else None)
        biochar_info = None
        if bcr:
            biochar_info = {
                "request_code": bcr.request_code,
                "requested_kg": bcr.requested_kg,
                "land_area_ha": bcr.land_area_ha,
                "delivery_point": bcr.delivery_point,
                "status": bcr.status,
            }
        elif h.biochar_backhaul_requested and h.biochar_backhaul_kg:
            biochar_info = {
                "request_code": None,
                "requested_kg": h.biochar_backhaul_kg,
                "land_area_ha": None,
                "delivery_point": "Lahan Petani",
                "status": "REQUESTED",
            }

        status_val = h.status.value if hasattr(h.status, "value") else str(h.status)
        is_verif = (h.status == HarvestStatus.VERIFIED)
        is_act = (h.status in (HarvestStatus.REPORTED, HarvestStatus.VERIFIED))
        status_lbl = "🟡 Menunggu Verifikasi Qty & Harga" if h.status == HarvestStatus.REPORTED else (
            "🔵 Terverifikasi Pengepul (Siap Jemput)" if h.status == HarvestStatus.VERIFIED else (
                "🚚 Diangkut Pengepul" if h.status == HarvestStatus.COLLECTED else (
                    "🏭 Diterima Gudang/Pabrik" if h.status in (HarvestStatus.DELIVERED, HarvestStatus.CONVERTED) else "❌ Ditolak QC"
                )
            )
        )

        cev_row = (await db.execute(select(CustodyEvent.verification_code).where(
            CustodyEvent.harvest_id == h.id, CustodyEvent.verification_code.is_not(None)
        ).limit(1))).scalar_one_or_none()

        item = {
            "harvest_id": h.id,
            "listing_id": h.listing_id,
            "wr_code": wr_code,
            "origin_qr_code": h.origin_qr_code or h.qr_code or f"WR-HV-{h.id:04d}",
            "trx_code": cev_row,
            "batch_ref": f"WR-LST-{h.listing_id:04d}" if h.listing_id else f"WR-HV-{h.id:04d}",
            "status": status_val,
            "is_active": is_act,
            "status_label": status_lbl,
            "is_verified_initial": is_verif,
            "verification_stage": "verified" if is_verif else "unverified",
            "verification_label": "🔵 Sudah Terverifikasi (Qty & Harga)" if is_verif else "🟡 Belum Verifikasi Qty & Harga",
            "nama_petani": f_name,
            "farmer_phone": farmer.phone if farmer else None,
            "kecamatan": farmer.kecamatan if farmer else None,
            "jenis_biomassa": b_name,
            "commodity_code": c_code,
            "qty_kg": h.quantity_kg,
            "farmer_claimed_qty": h.farmer_claimed_qty or h.quantity_kg,
            "kualitas": kualitas,
            "moisture_est": mc_val,
            "grade_est": gr_val,
            "pilihan_kirim": pilihan_kirim,
            "logistics_mode": h.logistics_mode or ("DELIVER_SELF" if is_antar else "PICKUP"),
            "delivery_scheme": "antar" if is_antar else "jemput",
            "harga_per_kg": hrg,
            "titik_pasok": titik_pasok,
            "mill_id": h.mill_id,
            "photo_url": h.photo_url,
            "biochar_request": biochar_info,
            "reported_at": h.reported_at.isoformat() if h.reported_at else None,
            "transaction_mode": h.transaction_mode or "DIRECT",
            "keterangan": "Terverifikasi pengepul, siap rute jemput / timbang" if is_verif else ("Diantar petani ke gudang" if is_antar else "Laporan petani siap verifikasi Qty & Harga"),
            "aksi_finalisasi": "⚖️ Uji Mutu & Timbang" if is_verif else "✓ Setujui Qty & Harga",
            "my_active_bid": None,
            "is_locked": getattr(h, "is_locked", False),
        }
        if is_antar:
            diantar_petani.append(item)
        else:
            langsung_diambil.append(item)

    langsung_diambil.sort(key=lambda x: (x["commodity_code"], -x.get("harvest_id", x["listing_id"] or 0)))
    diantar_petani.sort(key=lambda x: (x["commodity_code"], -x.get("harvest_id", x["listing_id"] or 0)))
    lelang.sort(key=lambda x: (x["commodity_code"], -x["listing_id"]))

    all_items = langsung_diambil + lelang + diantar_petani
    total_unverified = sum(1 for it in all_items if not it.get("is_verified_initial"))
    total_verified = sum(1 for it in all_items if it.get("is_verified_initial"))

    return {
        "collector_id": user.id,
        "specialization_commodity": spec,
        "specialization_name": spec.replace("_", " ").title() if spec else "Semua Komoditas",
        "total_direct": len(langsung_diambil),
        "total_auction": len(lelang),
        "total_diantar": len(diantar_petani),
        "total_unverified": total_unverified,
        "total_verified": total_verified,
        "langsung_diambil": langsung_diambil,
        "lelang": lelang,
        "diantar_petani": diantar_petani,
        "tabs": {
            "langsung_diambil": langsung_diambil,
            "lelang": lelang,
            "diantar_petani": diantar_petani,
        }
    }


@router.post("/consolidated-pickup-plan")
async def consolidated_pickup_plan(
    req: ConsolidatedPickupPlanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PENGEPUL))],
):
    """Penyusunan rute multi-stop penjemputan biomassa petani terintegrasi muatan balik (backhaul) biochar.

    Memverifikasi constraint kapasitas ganda armada (Massa ≤ 5.000 kg dan Volume ≤ 30 m³).
    Simulasi dinamis: muatan balik biochar diturunkan di petani sementara biomassa dimuat.
    """
    harvests = (await db.execute(
        select(Harvest).where(Harvest.id.in_(req.harvest_ids))
    )).scalars().all()
    if not harvests:
        raise HTTPException(404, "Tidak ada harvest yang valid ditemukan")

    farmer_ids = [h.farmer_id for h in harvests if h.farmer_id]
    farmers = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(farmer_ids)))).scalars().all()}

    # Biochar requests
    biochar_reqs = []
    if req.biochar_backhaul_requests:
        biochar_reqs = (await db.execute(
            select(BiocharRequest).where(BiocharRequest.id.in_(req.biochar_backhaul_requests))
        )).scalars().all()

    total_biochar_kg = sum(b.requested_kg for b in biochar_reqs)
    # Biochar density ~300 kg/m3
    biochar_volume_m3 = round(total_biochar_kg / 300.0, 2)

    depot = {"lat": user.lat or -6.9175, "lon": user.lon or 107.6191, "name": user.full_name or "Gudang Pengepul"}
    points = []
    total_biomass_kg = 0.0
    total_biomass_m3 = 0.0

    stops_detail = []
    for h in harvests:
        f = farmers.get(h.farmer_id)
        f_lat = f.lat if f and f.lat is not None else depot["lat"] + 0.01
        f_lon = f.lon if f and f.lon is not None else depot["lon"] + 0.01
        qty_kg = h.quantity_kg
        total_biomass_kg += qty_kg
        # Husk density ~120 kg/m3
        vol_m3 = round(qty_kg / 120.0, 2)
        total_biomass_m3 += vol_m3
        
        # Check if farmer receives biochar
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

    # Solve route with routing engine
    r_req = RouteRequest(vehicle_m3=req.truck_max_m3, cost_per_km=P("logistik.cost_per_km"), mode="auto", time_budget_ms=200)
    route_sol = plan_routes(depot, points, r_req)

    # Map points by mill id (e.g. H12 -> pt)
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
            "description": f"Armada {plate_used} ({driver_used}) berangkat membawa muatan balik biochar",
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

    # Calculate overall combined feasibility
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
