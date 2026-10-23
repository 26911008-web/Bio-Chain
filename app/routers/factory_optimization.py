"""Sub-router pabrik: Optimasi produk multi-output (HiGHS) dari stok multi-biomassa.

Dipisah dari app/routers/factory.py (audit 23 Okt 2026, CLAUDE.md §3.1) dan di-mount olehnya.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..concurrency import run_cpu

router = APIRouter()

_pabrik_dep = require_role(UserRole.PABRIK, UserRole.ADMIN)
# Aksi yang mengubah timbangan / stok hanya oleh operator pabrik (admin tidak, demi pemisahan tugas).
_pabrik_only = require_role(UserRole.PABRIK)
_audit_read = require_role(UserRole.PABRIK, UserRole.ADMIN, UserRole.AUDITOR)



router = APIRouter()


# ---------------------------------------------------------------- Optimasi Multi-Biomassa ke Produk Akhir (Engine ⑫)
class OptimizeEvaluateRequest(BaseModel):
    code: str | None = Field(None, max_length=24, description="Kode komoditas master")
    commodity_code: str | None = Field(None, max_length=24, description="Alias untuk code dari frontend")
    name: str | None = Field(None, max_length=80)
    tonnage: float | None = Field(None, gt=0, le=100_000_000)
    quantity_kg: float | None = Field(None, gt=0, le=100_000_000_000)
    moisture_pct: float | None = Field(None, ge=0, lt=95)
    ash_pct_db: float | None = Field(None, ge=0, lt=60)
    volatile_pct_db: float | None = Field(None, ge=0, le=100)
    fixed_carbon_pct_db: float | None = Field(None, ge=0, le=100)
    hhv_db_mj_kg: float | None = Field(None, gt=5, lt=35)
    lhv_db_mj_kg: float | None = Field(None, gt=5, lt=35)
    sio2_pct_ash: float | None = Field(None, ge=0, le=100)
    base_price_per_kg: float | None = Field(None, ge=0, le=100_000)
    purchase_price_per_kg: float | None = Field(None, ge=0, le=100_000)
    price_overrides: dict[str, float] | None = None


class FeedstockAllocationInput(BaseModel):
    code: str = Field(..., min_length=2, max_length=24)
    name: str | None = None
    tonnage: float | None = Field(None, gt=0, le=100_000_000)
    stock_kg: float | None = Field(None, gt=0)
    moisture_pct: float | None = Field(None, ge=0, lt=95)
    ash_pct_db: float | None = Field(None, ge=0, lt=60)
    base_price_per_kg: float | None = Field(None, ge=0, le=100_000)
    purchase_price_per_kg: float | None = Field(None, ge=0, le=100_000)


class OptimizeAllocateRequest(BaseModel):
    feedstocks: list[FeedstockAllocationInput] | None = None
    stocks: list[FeedstockAllocationInput] | None = None
    max_pellet_ton: float | None = Field(None, ge=0)
    max_briket_ton: float | None = Field(None, ge=0)
    max_biochar_ton: float | None = Field(None, ge=0)
    max_silica_kg: float | None = Field(None, ge=0)
    capacities: dict[str, float] | None = None
    objective: str = Field("max_profit", pattern="^(max_profit|max_energy|max_carbon|balanced)$")
    price_overrides: dict[str, float] | None = None


@router.get("/optimization/config")
async def optimization_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Konfigurasi produk, komoditas aktif, harga default, dan kapasitas lini pabrik."""
    from ..services.biomass import list_biomass
    from ..engines.product_optimization import PRODUCT_META, PRODUCTS
    biomasses = await list_biomass(db, active_only=True)
    return {
        "products": PRODUCT_META,
        "product_list": PRODUCTS,
        "product_meta": PRODUCT_META,
        "biomasses": biomasses,
        "capacities": {
            "bio_pellet": 250000.0,
            "briket": 150000.0,
            "biochar": 100000.0,
            "bio_silika": 15000.0,
        },
        "default_capacities": {
            "max_pellet_ton": 250.0,
            "max_briket_ton": 150.0,
            "max_biochar_ton": 100.0,
            "max_silica_kg": 15000.0,
        },
    }


@router.post("/optimization/evaluate")
async def optimization_evaluate(
    req: OptimizeEvaluateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_audit_read)],
):
    """Evaluasi multi-kriteria 1 jenis biomassa ke 4 produk akhir (biopellet, briket, biochar, biosilika)."""
    from ..services.biomass import get_biomass
    from ..engines.product_optimization import FeedstockItem, evaluate_feedstock, PRODUCT_META

    code = req.commodity_code or req.code or "sekam_padi"
    bm = await get_biomass(db, code, allow_inactive=True)

    tonnage = req.tonnage
    if tonnage is None:
        if req.quantity_kg is not None:
            tonnage = req.quantity_kg / 1000.0
        else:
            tonnage = 100.0

    price = req.purchase_price_per_kg if req.purchase_price_per_kg is not None else req.base_price_per_kg

    item = FeedstockItem(
        code=bm.code,
        name=req.name or bm.name,
        tonnage=tonnage,
        moisture_pct=req.moisture_pct if req.moisture_pct is not None else bm.moisture_typ_pct,
        ash_pct_db=req.ash_pct_db if req.ash_pct_db is not None else bm.ash_pct_db,
        volatile_pct_db=req.volatile_pct_db if req.volatile_pct_db is not None else bm.volatile_pct_db,
        fixed_carbon_pct_db=req.fixed_carbon_pct_db if req.fixed_carbon_pct_db is not None else bm.fixed_carbon_pct_db,
        hhv_db_mj_kg=req.hhv_db_mj_kg if req.hhv_db_mj_kg is not None else bm.hhv_db_mj_kg,
        lhv_db_mj_kg=req.lhv_db_mj_kg if req.lhv_db_mj_kg is not None else bm.lhv_db_mj_kg,
        sio2_pct_ash=req.sio2_pct_ash if req.sio2_pct_ash is not None else bm.sio2_pct_ash,
        k2o_pct_ash=bm.k2o_pct_ash,
        na2o_pct_ash=bm.na2o_pct_ash,
        chlorine_pct_db=bm.chlorine_pct_db,
        sulfur_pct_db=bm.sulfur_pct_db,
        base_price_per_kg=price if price is not None else (bm.base_price_per_kg or 0.0),
    )

    ev = await run_cpu(evaluate_feedstock, item, req.price_overrides)

    # Format and enrich response for frontend compatibility
    grade_map = lambda sc: "S" if sc >= 85 else "A" if sc >= 70 else "B" if sc >= 55 else "C" if sc >= 40 else "D"
    products_enriched = {}
    for k, p in ev.get("products", {}).items():
        meta = PRODUCT_META.get(k, {})
        sc = p["suitability"]["score"]
        grade = grade_map(sc)
        p_enrich = dict(p)
        p_enrich["name"] = meta.get("name", p.get("label", k))
        p_enrich["standard"] = meta.get("standard", p["product_quality"].get("standard_compliance", "-"))
        p_enrich["yield"] = {
            "product_output_kg": round(p["yield_kg_per_ton"] * item.tonnage, 1),
            "yield_pct": p.get("yield_pct", 0),
        }
        econ = p.get("economics", {})
        p_enrich["economics"] = {
            **econ,
            "gross_margin_rp": round(econ.get("gross_profit_per_ton_feed", 0) * item.tonnage, 0),
            "selling_price_rp_per_kg": econ.get("product_price_per_kg", 0),
            "margin_per_ton_feed_rp": econ.get("gross_profit_per_ton_feed", 0),
        }
        en_m = p.get("energy_metrics", {})
        p_enrich["energy"] = {
            "electricity_sec_kwh_per_ton": en_m.get("sec_kwh_per_ton_product", 0),
            "product_lhv_ar_mj_kg": p["product_quality"].get("product_lhv_ar_mj_kg") or en_m.get("net_energy_output_gj", 0),
            "total_energy_gj": round(en_m.get("net_energy_output_gj", 0) * item.tonnage, 2),
        }
        cl_m = p.get("climate_metrics", {})
        p_enrich["carbon"] = {
            "net_carbon_balance_tco2e": round(cl_m.get("net_climate_benefit_tco2e_per_ton", 0) * item.tonnage, 3),
        }
        suit = p.get("suitability", {})
        p_enrich["suitability"] = {
            **suit,
            "grade": grade,
            "verdict": suit.get("status_label", ""),
            "warnings": suit.get("disadvantages", []),
            "compliance": [
                {"standard": p["product_quality"].get("standard_compliance", "Standar Mutu"), "ok": sc >= 60}
            ],
        }
        products_enriched[k] = p_enrich

    rankings = ev.get("rankings", {})
    ev["products"] = products_enriched
    ev["recommendation"] = {
        "synthesis_rationale": ev.get("summary_recommendation", ""),
        "best_economic_product": rankings.get("best_by_profit", {}).get("label", "-"),
        "best_energy_product": rankings.get("best_by_energy", {}).get("label", "-"),
        "best_carbon_product": rankings.get("best_by_carbon", {}).get("label", "-"),
        "overall_recommended_product": rankings.get("best_by_suitability", {}).get("label", "-"),
    }
    ev["feedstock"]["quantity_kg"] = round(item.tonnage * 1000.0, 1)
    return ev


@router.post("/optimization/allocate")
async def optimization_allocate(
    req: OptimizeAllocateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_pabrik_dep)],
):
    """Optimasi alokasi pasokan multi-biomassa ke portofolio produk menggunakan solver Linear Programming (HiGHS)."""
    from ..services.biomass import get_biomass
    from ..engines.product_optimization import AllocationCapacity, AllocationRequest, FeedstockItem, optimize_allocation, PRODUCT_META

    feedstock_inputs = req.feedstocks or req.stocks or []
    if not feedstock_inputs:
        raise HTTPException(422, "Minimal 1 stok biomassa harus disertakan.")

    items = []
    for f in feedstock_inputs:
        bm = await get_biomass(db, f.code, allow_inactive=True)
        t = f.tonnage
        if t is None:
            t = (f.stock_kg / 1000.0) if f.stock_kg is not None else 10.0
        price = f.purchase_price_per_kg if f.purchase_price_per_kg is not None else f.base_price_per_kg

        items.append(FeedstockItem(
            code=bm.code,
            name=f.name or bm.name,
            tonnage=t,
            moisture_pct=f.moisture_pct if f.moisture_pct is not None else bm.moisture_typ_pct,
            ash_pct_db=f.ash_pct_db if f.ash_pct_db is not None else bm.ash_pct_db,
            volatile_pct_db=bm.volatile_pct_db,
            fixed_carbon_pct_db=bm.fixed_carbon_pct_db,
            hhv_db_mj_kg=bm.hhv_db_mj_kg,
            lhv_db_mj_kg=bm.lhv_db_mj_kg,
            sio2_pct_ash=bm.sio2_pct_ash,
            k2o_pct_ash=bm.k2o_pct_ash,
            na2o_pct_ash=bm.na2o_pct_ash,
            chlorine_pct_db=bm.chlorine_pct_db,
            sulfur_pct_db=bm.sulfur_pct_db,
            base_price_per_kg=price if price is not None else (bm.base_price_per_kg or 0.0),
        ))

    caps = req.capacities or {}
    max_pellet = req.max_pellet_ton
    if max_pellet is None and "bio_pellet" in caps:
        max_pellet = caps["bio_pellet"] / 1000.0
    max_briket = req.max_briket_ton
    if max_briket is None and "briket" in caps:
        max_briket = caps["briket"] / 1000.0
    max_char = req.max_biochar_ton
    if max_char is None and "biochar" in caps:
        max_char = caps["biochar"] / 1000.0
    max_silica = req.max_silica_kg
    if max_silica is None and "bio_silika" in caps:
        max_silica = caps["bio_silika"]

    alloc_req = AllocationRequest(
        feedstocks=items,
        capacities=AllocationCapacity(
            max_pellet_ton=max_pellet,
            max_briket_ton=max_briket,
            max_biochar_ton=max_char,
            max_silica_kg=max_silica,
        ),
        objective=req.objective,
        price_overrides=req.price_overrides,
    )

    try:
        raw_res = await run_cpu(optimize_allocation, alloc_req)
    except ValueError as e:
        raise HTTPException(422, str(e))

    res = dict(raw_res)

    # Enrich summary for frontend
    fin = res.get("financial_summary", {})
    clim = res.get("climate_summary", {})
    nrg = res.get("energy_summary", {})
    tot_feed_kg = round(res.get("total_feedstock_input_ton", 0) * 1000.0, 0)

    tot_prod_kg = 0.0
    for a in res.get("allocations", []):
        p_kg = a.get("produced_qty", 0) * (1000.0 if a.get("produced_unit") == "ton" else 1.0)
        tot_prod_kg += p_kg

    res["summary"] = {
        "total_feedstock_used_kg": tot_feed_kg,
        "total_product_output_kg": round(tot_prod_kg, 1),
        "total_gross_margin_rp": fin.get("total_gross_profit_rp", 0),
        "total_revenue_rp": fin.get("total_revenue_rp", 0),
        "total_energy_output_gj": nrg.get("total_product_energy_gj", 0),
        "total_net_carbon_balance_tco2e": clim.get("total_co2e_benefit_ton", 0),
    }

    # Enrich allocations
    enriched_allocs = []
    for a in res.get("allocations", []):
        a_copy = dict(a)
        a_copy["product_key"] = a.get("product")
        a_copy["product_name"] = a.get("product_label") or PRODUCT_META.get(a.get("product"), {}).get("name", a.get("product"))
        a_copy["allocated_kg"] = round(a.get("allocated_feedstock_ton", 0) * 1000.0, 0)
        p_qty = a.get("produced_qty", 0)
        a_copy["product_output_kg"] = round(p_qty * (1000.0 if a.get("produced_unit") == "ton" else 1.0), 1)
        a_copy["gross_margin_rp"] = a.get("gross_profit_rp", 0)
        a_copy["energy_gj"] = a.get("net_energy_gj", 0)
        a_copy["net_carbon_tco2e"] = a.get("co2e_benefit_t", 0)
        sc = a.get("suitability_score", 0)
        a_copy["suitability_verdict"] = "Sangat Layak" if sc >= 80 else "Layak" if sc >= 60 else "Cukup"
        enriched_allocs.append(a_copy)
    res["allocations"] = enriched_allocs

    # Capacity utilization in kg
    cap_util_enriched = {}
    for p, cu in res.get("capacity_utilization", {}).items():
        is_kg = (p == "bio_silika")
        cap_util_enriched[p] = {
            "capacity_kg": cu.get("capacity", 0) if is_kg else cu.get("capacity", 0) * 1000.0,
            "allocated_product_kg": cu.get("produced", 0) if is_kg else cu.get("produced", 0) * 1000.0,
            "utilization_pct": cu.get("utilization_pct", 0),
        }
    res["capacity_utilization"] = cap_util_enriched
    res["managerial_insights"] = res.get("insights", [])

    return res
