"""Router: Factory Production & Blending Operations — Multi-Ramp Blending Optimizer, Execution Commit, & Safety Testing."""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.industrial import LoadingRamp, ProductionBlend, ByProductLedger

_pabrik_only = require_role([UserRole.PABRIK, UserRole.ADMIN])
_audit_read = require_role([UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR])

router = APIRouter()


class BlendOptimizeRequest(BaseModel):
    batch_size_kg: float = Field(10000.0, gt=0, le=500000.0)
    target_selling_prices: dict[str, float] | None = None


class BlendCommitRequest(BaseModel):
    target_product: str = Field(..., pattern="^(BIOPELLET|BIOCHAR|BIO_SILICA|BRIQUETTE)$")
    total_input_kg: float = Field(..., gt=0)
    ramp_allocations: list[dict] = Field(..., min_length=1)
    cost_per_kg: float = Field(..., ge=0)
    target_selling_price_per_kg: float = Field(..., gt=0)
    estimated_margin_rp: float
    net_tco2e: float
    final_mc_pct: float
    final_ash_pct: float
    final_lhv_kcal: float


class SafetyTestRequest(BaseModel):
    pb_ppm: float = Field(..., ge=0, description="Kandungan Timbal / Pb (PPM)")
    cd_ppm: float = Field(..., ge=0, description="Kandungan Kadmium / Cd (PPM)")
    as_ppm: float = Field(..., ge=0, description="Kandungan Arsenik / As (PPM)")
    lab_cert_no: str = Field(..., min_length=3, max_length=80, description="Nomor Sertifikat Uji Lab KAN/ISO 17025")


@router.post("/blends/optimize")
async def optimize_multi_ramp_blend(
    req: BlendOptimizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Mesin Rekomendasi Blending Multi-Ramp untuk 4 Produk Akhir."""
    ramps = (await db.execute(
        select(LoadingRamp).where(LoadingRamp.is_active.is_(True), LoadingRamp.current_stock_kg > 0)
    )).scalars().all()

    if not ramps:
        # Jika belum ada stok, buat sampel simulasi ramp agar kalkulator selalu interaktif
        defaults = [
            LoadingRamp(ramp_code="RAMP-01", name="Ramp Biomassa 01 (Granular/Sekam)", biomass_type="sekam_padi", max_capacity_kg=60000.0, current_stock_kg=18000.0, aggregate_mc=13.5, aggregate_ash=17.0, aggregate_lhv_kcal=3450.0),
            LoadingRamp(ramp_code="RAMP-02", name="Ramp Biomassa 02 (Cacah/Tongkol)", biomass_type="tongkol_jagung", max_capacity_kg=45000.0, current_stock_kg=12000.0, aggregate_mc=14.0, aggregate_ash=2.5, aggregate_lhv_kcal=4100.0),
            LoadingRamp(ramp_code="RAMP-03", name="Ramp Biomassa 03 (Serbuk Kayu)", biomass_type="serbuk_sengon", max_capacity_kg=40000.0, current_stock_kg=9000.0, aggregate_mc=28.0, aggregate_ash=1.5, aggregate_lhv_kcal=3800.0),
            LoadingRamp(ramp_code="RAMP-04", name="Ramp Biomassa 04 (Cangkang/Tempurung)", biomass_type="tempurung_kelapa", max_capacity_kg=50000.0, current_stock_kg=15000.0, aggregate_mc=10.5, aggregate_ash=2.0, aggregate_lhv_kcal=4600.0),
        ]
        for r in defaults:
            db.add(r)
        await db.flush()
        ramps = defaults

    total_avail = sum(r.current_stock_kg for r in ramps)
    target_kg = min(req.batch_size_kg, total_avail)

    prices = {
        "BIOPELLET": 1600.0,
        "BIOCHAR": 5500.0,
        "BIO_SILICA": 22000.0,
        "BRIQUETTE": 3200.0,
    }
    if req.target_selling_prices:
        prices.update(req.target_selling_prices)

    opex_per_kg = {
        "BIOPELLET": 450.0,
        "BIOCHAR": 1200.0,
        "BIO_SILICA": 5500.0,
        "BRIQUETTE": 700.0,
    }

    yield_factors = {
        "BIOPELLET": 0.92,
        "BIOCHAR": 0.28,
        "BIO_SILICA": 0.12,
        "BRIQUETTE": 0.85,
    }

    carbon_factors = {
        "BIOPELLET": 1.45,
        "BIOCHAR": 2.85,
        "BIO_SILICA": 1.10,
        "BRIQUETTE": 1.25,
    }

    # 1. BIOPELLET (Abu rendah, lignin/kalori tinggi: serbuk kayu, ampas tebu, tongkol)
    alloc_pellet = []
    accum = 0.0
    sorted_for_pellet = sorted(
        ramps,
        key=lambda r: (
            0 if any(k in r.biomass_type for k in ("sengon", "kayu", "tebu", "jagung")) else 1,
            r.aggregate_ash,
            -r.aggregate_lhv_kcal
        )
    )
    for r in sorted_for_pellet:
        needed = target_kg - accum
        take = min(r.current_stock_kg * 0.7, needed)
        if take > 0:
            alloc_pellet.append({"ramp_id": r.id, "ramp_code": r.ramp_code, "name": r.name, "biomass": r.biomass_type, "qty_kg": round(take, 1)})
            accum += take
        if accum >= target_kg:
            break

    # 2. BIOCHAR (Karbonisasi luas: Sekam / Tempurung / Serbuk / Tebu)
    alloc_biochar = []
    accum = 0.0
    sorted_for_char = sorted(ramps, key=lambda r: 0 if r.biomass_type in ("sekam_padi", "tempurung_kelapa", "ampas_tebu") else 1)
    for r in sorted_for_char:
        needed = target_kg - accum
        take = min(r.current_stock_kg * 0.7, needed)
        if take > 0:
            alloc_biochar.append({"ramp_id": r.id, "ramp_code": r.ramp_code, "name": r.name, "biomass": r.biomass_type, "qty_kg": round(take, 1)})
            accum += take
        if accum >= target_kg:
            break

    # 3. BIO-SILIKA (Matriks Khusus: Wajib biomassa kaya silika / sekam padi)
    alloc_silica = []
    sekam_ramps = [r for r in ramps if "sekam" in r.biomass_type]
    if sekam_ramps:
        sr = sekam_ramps[0]
        take = min(sr.current_stock_kg * 0.8, target_kg)
        alloc_silica.append({"ramp_id": sr.id, "ramp_code": sr.ramp_code, "name": sr.name, "biomass": sr.biomass_type, "qty_kg": round(take, 1)})
    else:
        alloc_silica = []

    # 4. BRIKET (Campuran arang kalori tinggi & densitas padat)
    alloc_briquette = []
    accum = 0.0
    sorted_for_briq = sorted(ramps, key=lambda r: -r.aggregate_lhv_kcal)
    for r in sorted_for_briq:
        needed = target_kg - accum
        take = min(r.current_stock_kg * 0.7, needed)
        if take > 0:
            alloc_briquette.append({"ramp_id": r.id, "ramp_code": r.ramp_code, "name": r.name, "biomass": r.biomass_type, "qty_kg": round(take, 1)})
            accum += take
        if accum >= target_kg:
            break

    compatibility_rules = {
        "BIOPELLET": {
            "preferred": ["serbuk_sengon", "ampas_tebu", "tongkol_jagung"],
            "restricted": ["sekam_padi"],
            "rationale": "Membutuhkan lignin tinggi sebagai binder alami dan kadar abu rendah (<3%) untuk mencegah slagging pada boiler.",
        },
        "BIOCHAR": {
            "preferred": ["sekam_padi", "tempurung_kelapa", "ampas_tebu", "serbuk_sengon"],
            "restricted": [],
            "rationale": "Cocok untuk hampir semua biomassa berselulosa/lignin; menghasilkan karbon aktif pembenah tanah & carbon sink.",
        },
        "BIO_SILICA": {
            "preferred": ["sekam_padi"],
            "restricted": ["serbuk_sengon", "tongkol_jagung", "ampas_tebu", "tempurung_kelapa"],
            "rationale": "Secara kimiawi wajib abu biomassa bersilika amorf tinggi (~20% SiO2 pada sekam padi). Kayu/tongkol tidak menghasilkan silika presipitasi murni.",
        },
        "BRIQUETTE": {
            "preferred": ["tempurung_kelapa", "tongkol_jagung", "serbuk_sengon"],
            "restricted": [],
            "rationale": "Membutuhkan nilai kalor tinggi (>4000 kcal/kg) dan daya rekat arang yang kokoh.",
        },
    }

    product_configs = [
        ("BIOPELLET", "Biopellet Industri & Ekspor", alloc_pellet),
        ("BIOCHAR", "Biochar Pembenah Tanah & C-Sink", alloc_biochar),
        ("BIO_SILICA", "Bio-Silika Presipitasi Kemurnian Tinggi", alloc_silica),
        ("BRIQUETTE", "Briket Arang Kalori Tinggi", alloc_briquette),
    ]

    recommendations = []
    for p_key, p_name, alloc in product_configs:
        tot_input = sum(a["qty_kg"] for a in alloc)
        if tot_input <= 0:
            continue
        ramp_map = {r.id: r for r in ramps}
        calc_mc = sum(a["qty_kg"] * ramp_map[a["ramp_id"]].aggregate_mc for a in alloc if a["ramp_id"] in ramp_map) / tot_input
        calc_ash = sum(a["qty_kg"] * ramp_map[a["ramp_id"]].aggregate_ash for a in alloc if a["ramp_id"] in ramp_map) / tot_input
        calc_lhv = sum(a["qty_kg"] * ramp_map[a["ramp_id"]].aggregate_lhv_kcal for a in alloc if a["ramp_id"] in ramp_map) / tot_input

        output_qty = tot_input * yield_factors[p_key]
        raw_feedstock_cost_per_kg = 450.0
        hpp_per_kg = (raw_feedstock_cost_per_kg / yield_factors[p_key]) + opex_per_kg[p_key]
        sell_price = prices[p_key]
        margin_per_kg = sell_price - hpp_per_kg
        total_profit_rp = margin_per_kg * output_qty

        process_emission_factor = 0.08
        net_tco2e = ((output_qty / 1000.0) * carbon_factors[p_key]) - ((tot_input / 1000.0) * process_emission_factor)

        compat = compatibility_rules.get(p_key, {})
        used_biomass = [a["biomass"] for a in alloc]
        is_fully_compatible = all(any(pref in b for pref in compat.get("preferred", [])) for b in used_biomass)
        compat_score = 1.0 if is_fully_compatible else 0.70

        from ..biomass_seed import BIOMASS_SEED
        from ..engines.energy import calculate_wte_drying_penalty
        seed_dict = {s["code"]: s for s in BIOMASS_SEED}

        tot_alk_kg = 0.0
        tot_hhv_wt = 0.0
        for a in alloc:
            b_code = a["biomass"]
            s_match = seed_dict.get(b_code)
            if not s_match:
                for k, v in seed_dict.items():
                    if k in b_code or b_code in k:
                        s_match = v
                        break
            if not s_match:
                s_match = seed_dict.get("sekam_padi", {})
            ash_val = s_match.get("ash_pct_db", 2.0)
            k2o_val = s_match.get("k2o_pct_ash", 10.0) or 0.0
            na2o_val = s_match.get("na2o_pct_ash", 1.0) or 0.0
            hhv_val = s_match.get("hhv_db_mj_kg", 18.0) or 18.0

            w_fraction = a["qty_kg"] / tot_input
            tot_alk_kg += w_fraction * (ash_val * (k2o_val + na2o_val) / 10000.0)
            tot_hhv_wt += w_fraction * hhv_val

        alkali_idx = (tot_alk_kg / (tot_hhv_wt / 1000.0)) if tot_hhv_wt > 0 else 0.0
        if alkali_idx < 0.17:
            slagging_verdict = "AMAN"
        elif alkali_idx <= 0.34:
            slagging_verdict = "WASPADA"
        else:
            slagging_verdict = "BAHAYA"

        drying_penalty = calculate_wte_drying_penalty(
            feedstock_kg=tot_input,
            moisture_pct=calc_mc,
            target_moisture_pct=14.0,
            lhv_dry_kcal=calc_lhv,
        )

        recommendations.append({
            "target_product": p_key,
            "product_name": p_name,
            "total_input_kg": tot_input,
            "estimated_output_kg": round(output_qty, 1),
            "yield_pct": round(yield_factors[p_key] * 100, 1),
            "ramp_allocations": alloc,
            "final_mc_pct": round(calc_mc, 1),
            "final_ash_pct": round(calc_ash, 1),
            "final_lhv_kcal": round(calc_lhv, 0),
            "alkali_index": round(alkali_idx, 3),
            "slagging_verdict": slagging_verdict,
            "drying_penalty": drying_penalty,
            "hpp_per_kg": round(hpp_per_kg, 0),
            "target_selling_price_per_kg": sell_price,
            "margin_per_kg": round(margin_per_kg, 0),
            "total_profit_rp": round(total_profit_rp, 0),
            "net_tco2e": round(net_tco2e, 2),
            "feedstock_compatibility": {
                "is_compatible": is_fully_compatible,
                "compatibility_score": compat_score,
                "technical_basis": compat.get("rationale"),
                "preferred_feedstocks": compat.get("preferred", []),
            },
            "is_most_profitable": False,
            "is_lowest_carbon": False,
        })

    if recommendations:
        best_profit = max(recommendations, key=lambda x: x["total_profit_rp"])
        best_profit["is_most_profitable"] = True
        best_carbon = max(recommendations, key=lambda x: x["net_tco2e"])
        best_carbon["is_lowest_carbon"] = True

    return {
        "batch_size_kg": target_kg,
        "total_stock_available_kg": total_avail,
        "recommendations": recommendations,
    }


@router.post("/blends/commit", status_code=201)
async def commit_production_blend(
    req: BlendCommitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Eksekusi dan Kunci Batch Produksi Blending Multi-Ramp."""
    for alloc in req.ramp_allocations:
        r_id = alloc["ramp_id"]
        qty = alloc["qty_kg"]
        ramp = (await db.execute(
            select(LoadingRamp).where(LoadingRamp.id == r_id).with_for_update()
        )).scalar_one_or_none()
        if not ramp:
            raise HTTPException(404, f"Ramp ID {r_id} tidak ditemukan.")
        if ramp.current_stock_kg < qty:
            raise HTTPException(409, f"Stok pada {ramp.ramp_code} tidak mencukupi! Tersedia: {ramp.current_stock_kg} kg, Diminta: {qty} kg.")
        ramp.current_stock_kg -= qty
        ramp.updated_at = datetime.now(timezone.utc)

    blend_code = f"BLD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    blend = ProductionBlend(
        blend_code=blend_code,
        mill_id=user.id,
        target_product=req.target_product,
        ramp_allocations=req.ramp_allocations,
        total_input_kg=req.total_input_kg,
        final_mc_pct=req.final_mc_pct,
        final_ash_pct=req.final_ash_pct,
        final_lhv_kcal=req.final_lhv_kcal,
        cost_per_kg=req.cost_per_kg,
        target_selling_price_per_kg=req.target_selling_price_per_kg,
        estimated_margin_rp=req.estimated_margin_rp,
        net_tco2e=req.net_tco2e,
    )
    db.add(blend)
    await db.flush()

    by_products = []
    if req.target_product == "BIOPELLET":
        fa_kg = round(req.total_input_kg * 0.05, 1)
        bp = ByProductLedger(
            blend_id=blend.id,
            mill_id=user.id,
            by_product_type="FLY_ASH",
            quantity_kg=fa_kg,
            circular_status="STORED",
            notes=f"Fly ash sisa pembakaran boiler pellet batch {blend_code}",
        )
        db.add(bp)
        by_products.append({"type": "FLY_ASH", "qty_kg": fa_kg})
    elif req.target_product == "BIOCHAR":
        wv_kg = round(req.total_input_kg * 0.15, 1)
        bp1 = ByProductLedger(
            blend_id=blend.id,
            mill_id=user.id,
            by_product_type="WOOD_VINEGAR",
            quantity_kg=wv_kg,
            circular_status="STORED",
            notes=f"Asap cair pirolisis (wood vinegar) & syngas dari batch {blend_code}",
        )
        db.add(bp1)
        by_products.append({"type": "WOOD_VINEGAR", "qty_kg": wv_kg})
    elif req.target_product == "BIO_SILICA":
        ba_kg = round(req.total_input_kg * 0.40, 1)
        bp = ByProductLedger(
            blend_id=blend.id,
            mill_id=user.id,
            by_product_type="BOTTOM_ASH",
            quantity_kg=ba_kg,
            circular_status="STORED",
            notes=f"Residu abu bawah ekstraksi silika batch {blend_code}",
        )
        db.add(bp)
        by_products.append({"type": "BOTTOM_ASH", "qty_kg": ba_kg})
    elif req.target_product == "BRIQUETTE":
        bo_kg = round(req.total_input_kg * 0.08, 1)
        bp = ByProductLedger(
            blend_id=blend.id,
            mill_id=user.id,
            by_product_type="BIO_OIL",
            quantity_kg=bo_kg,
            circular_status="STORED",
            notes=f"Tar bio-oil sampingan pirolisis briket {blend_code}",
        )
        db.add(bp)
        by_products.append({"type": "BIO_OIL", "qty_kg": bo_kg})

    await db.flush()

    return {
        "success": True,
        "blend_code": blend.blend_code,
        "target_product": blend.target_product,
        "total_input_kg": blend.total_input_kg,
        "estimated_margin_rp": blend.estimated_margin_rp,
        "net_tco2e": blend.net_tco2e,
        "by_products_recorded": by_products,
        "message": f"🎉 Batch {blend.blend_code} ({blend.target_product}) berhasil dikunci dan stok ramp telah dipotong.",
    }


@router.get("/blends")
async def list_production_blends(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Daftar riwayat batch blending produksi yang telah dieksekusi."""
    rows = (await db.execute(
        select(ProductionBlend).order_by(ProductionBlend.id.desc()).limit(50)
    )).scalars().all()
    return [
        {
            "id": b.id,
            "blend_code": b.blend_code,
            "target_product": b.target_product,
            "ramp_allocations": b.ramp_allocations,
            "total_input_kg": b.total_input_kg,
            "final_mc_pct": b.final_mc_pct,
            "final_ash_pct": b.final_ash_pct,
            "final_lhv_kcal": b.final_lhv_kcal,
            "estimated_margin_rp": b.estimated_margin_rp,
            "net_tco2e": b.net_tco2e,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in rows
    ]


@router.get("/by-products")
async def list_by_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Daftar hasil samping (by-products) dan inventaris sirkular."""
    rows = (await db.execute(
        select(ByProductLedger).order_by(ByProductLedger.id.desc()).limit(50)
    )).scalars().all()
    return [
        {
            "id": bp.id,
            "by_product_type": bp.by_product_type,
            "quantity_kg": bp.quantity_kg,
            "circular_status": bp.circular_status,
            "pb_ppm": bp.pb_ppm,
            "cd_ppm": bp.cd_ppm,
            "as_ppm": bp.as_ppm,
            "is_safety_passed": bp.is_safety_passed,
            "lab_cert_no": bp.lab_cert_no,
            "notes": bp.notes,
            "created_at": bp.created_at.isoformat() if bp.created_at else None,
        }
        for bp in rows
    ]


@router.post("/by-products/{byproduct_id}/safety-test")
async def test_byproduct_heavy_metals(
    byproduct_id: int,
    req: SafetyTestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_only)],
):
    """Gatekeeper Keamanan Kimia: Validasi batas logam berat (Pb <50 ppm, Cd <2 ppm, As <10 ppm) sebelum biochar/abu diizinkan ke tanah pertanian."""
    bp = (await db.execute(
        select(ByProductLedger).where(ByProductLedger.id == byproduct_id).with_for_update()
    )).scalar_one_or_none()
    if not bp:
        raise HTTPException(404, "Data by-product tidak ditemukan.")

    passed = (req.pb_ppm < 50.0) and (req.cd_ppm < 2.0) and (req.as_ppm < 10.0)
    bp.pb_ppm = req.pb_ppm
    bp.cd_ppm = req.cd_ppm
    bp.as_ppm = req.as_ppm
    bp.is_safety_passed = passed
    bp.lab_cert_no = req.lab_cert_no

    if passed:
        bp.circular_status = "APPROVED_FOR_SOIL"
        msg = f"✅ Uji Logam Berat LOLOS (Pb: {req.pb_ppm:g}, Cd: {req.cd_ppm:g}, As: {req.as_ppm:g} ppm). Biochar disetujui untuk pembenah tanah sawah!"
    else:
        bp.circular_status = "REJECTED_HAZARDOUS"
        msg = f"⛔ PERINGATAN: Melebihi ambang batas aman logam berat! (Batas: Pb<50, Cd<2, As<10 ppm). Status dikarantina B3, dilarang disalurkan ke petani."

    await db.flush()
    return {
        "success": True,
        "byproduct_id": bp.id,
        "is_safety_passed": passed,
        "circular_status": bp.circular_status,
        "lab_cert_no": bp.lab_cert_no,
        "message": msg
    }
