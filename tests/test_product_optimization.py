"""Unit test untuk Engine ⑫ — Optimasi Multi-Biomassa ke Produk Akhir (Biopellet, Briket, Biochar, Biosilika)."""

import pytest
from app.biomass_seed import BIOMASS_SEED
from app.engines.product_optimization import (
    FeedstockItem,
    PRODUCTS,
    evaluate_biopellet_pathway,
    evaluate_briket_pathway,
    evaluate_biochar_pathway,
    evaluate_biosilika_pathway,
    evaluate_feedstock,
    optimize_allocation,
    AllocationRequest,
    AllocationCapacity,
)
from tests.test_field_ops import env  # noqa: F401

S = {r["code"]: r for r in BIOMASS_SEED}


def _make_item(code: str, tonnage: float = 100.0, mc: float | None = None) -> FeedstockItem:
    r = S[code]
    return FeedstockItem(
        code=code,
        name=r["name"],
        tonnage=tonnage,
        moisture_pct=mc if mc is not None else r["moisture_typ_pct"],
        ash_pct_db=r["ash_pct_db"],
        volatile_pct_db=r.get("volatile_pct_db"),
        fixed_carbon_pct_db=r.get("fixed_carbon_pct_db"),
        hhv_db_mj_kg=r.get("hhv_db_mj_kg"),
        lhv_db_mj_kg=r.get("lhv_db_mj_kg"),
        sio2_pct_ash=r.get("sio2_pct_ash"),
        k2o_pct_ash=r.get("k2o_pct_ash"),
        na2o_pct_ash=r.get("na2o_pct_ash"),
        chlorine_pct_db=r.get("chlorine_pct_db"),
        sulfur_pct_db=r.get("sulfur_pct_db"),
        base_price_per_kg=600.0,
    )


def test_eval_all_products_mass_balance_closure():
    """Memastikan setiap jalur produk menutup neraca massa (Σ output + Σ loss = input)."""
    for code in ("sekam_padi", "tempurung_kelapa", "serbuk_sengon", "tongkol_jagung"):
        item = _make_item(code)
        p = evaluate_biopellet_pathway(item)
        assert abs(p["mass_balance_closure"] - 1.0) < 1e-4

        b = evaluate_briket_pathway(item)
        assert abs(b["mass_balance_closure"] - 1.0) < 1e-4

        c = evaluate_biochar_pathway(item)
        assert abs(c["mass_balance_closure"] - 1.0) < 1e-4

        s = evaluate_biosilika_pathway(item)
        assert abs(s["mass_balance_closure"] - 1.0) < 1e-4


def test_rice_husk_yields_high_silica_and_low_pellet_suitability():
    """Sekam padi harus menghasilkan yield silika tertinggi, tetapi skor pelet rendah karena abu tinggi."""
    husk = _make_item("sekam_padi")
    res = evaluate_feedstock(husk)

    silica = res["products"]["bio_silika"]
    pellet = res["products"]["bio_pellet"]
    char = res["products"]["biochar"]

    # Silika rendemen > 100 kg/ton
    assert silica["yield_kg_per_ton"] > 100.0
    assert silica["suitability"]["score"] >= 90.0
    assert silica["suitability"]["status"] == "sangat_direkomendasikan"

    # Pelet abu tinggi -> skor kesesuaian rendah
    assert pellet["product_quality"]["ash_pct"] > 10.0
    assert pellet["suitability"]["score"] < 60.0

    # Biochar layak
    assert char["suitability"]["score"] >= 80.0


def test_coconut_shell_yields_premium_briquette_and_negligible_silica():
    """Tempurung kelapa harus juara briket arang, tetapi biosilika tidak layak karena abu rendah."""
    shell = _make_item("tempurung_kelapa")
    res = evaluate_feedstock(shell)

    briket = res["products"]["briket"]
    silica = res["products"]["bio_silika"]

    assert briket["suitability"]["score"] >= 90.0
    assert briket["suitability"]["status"] == "sangat_direkomendasikan"
    assert briket["product_quality"]["ash_pct"] < 5.0

    # Silika sangat tidak layak (< 5 kg/ton)
    assert silica["yield_kg_per_ton"] < 5.0
    assert silica["suitability"]["status"] == "tidak_layak"


def test_wood_sawdust_yields_excellent_pellet():
    """Serbuk gergaji sengon harus unggul untuk biopellet (abu rendah, ISO compliant)."""
    wood = _make_item("serbuk_sengon")
    res = evaluate_feedstock(wood)

    pellet = res["products"]["bio_pellet"]
    assert pellet["suitability"]["score"] >= 80.0
    assert pellet["product_quality"]["ash_pct"] < 2.0


def test_allocation_optimizer_max_profit():
    """Solver LP harus mengalokasikan stok multi-biomassa ke produk paling menguntungkan."""
    feeds = [
        _make_item("sekam_padi", tonnage=50.0),
        _make_item("tempurung_kelapa", tonnage=30.0),
        _make_item("serbuk_sengon", tonnage=40.0),
    ]

    req = AllocationRequest(
        feedstocks=feeds,
        capacities=AllocationCapacity(
            max_pellet_ton=100.0,
            max_briket_ton=12.0,
            max_biochar_ton=100.0,
            max_silica_kg=10_000.0,
        ),
        objective="max_profit",
    )

    out = optimize_allocation(req)
    assert out["status"] == "success"
    assert out["total_feedstock_input_ton"] == pytest.approx(120.0, abs=0.1)

    # Pastikan sekam masuk ke silika/biochar, tempurung masuk ke briket, serbuk masuk ke pelet
    allocs = out["allocations"]
    husk_alloc = [a for a in allocs if a["feedstock_code"] == "sekam_padi"]
    shell_alloc = [a for a in allocs if a["feedstock_code"] == "tempurung_kelapa"]
    wood_alloc = [a for a in allocs if a["feedstock_code"] == "serbuk_sengon"]

    assert any(a["product"] == "bio_silika" for a in husk_alloc)
    assert any(a["product"] == "briket" for a in shell_alloc)
    assert any(a["product"] == "bio_pellet" for a in wood_alloc)

    # Keuangan positif
    assert out["financial_summary"]["total_gross_profit_rp"] > 0
    assert out["financial_summary"]["overall_gross_margin_pct"] > 0


def test_allocation_capacity_constraint_enforced():
    """Kendala kapasitas pabrik harus dihormati oleh solver."""
    feeds = [_make_item("sekam_padi", tonnage=100.0)]
    max_silica = 2000.0  # Hanya bisa menampung 2000 kg silika

    req = AllocationRequest(
        feedstocks=feeds,
        capacities=AllocationCapacity(max_silica_kg=max_silica),
        objective="max_profit",
    )

    out = optimize_allocation(req)
    # Output silika tidak boleh melebihi max_silica
    assert out["product_outputs"]["bio_silika_kg"] <= max_silica + 1e-2


def test_allocation_max_energy():
    """Objektif max_energy harus memprioritaskan bahan berkalori tinggi ke pelet/briket."""
    feeds = [_make_item("serbuk_sengon", tonnage=50.0)]
    req = AllocationRequest(feedstocks=feeds, objective="max_energy")
    out = optimize_allocation(req)
    assert out["status"] == "success"
    # Serbuk sengon menghasilkan energi netto tertinggi bila dijadikan bio_pellet
    assert out["allocations"][0]["product"] == "bio_pellet"
    assert out["energy_summary"]["total_product_energy_gj"] > 0


def test_allocation_max_carbon():
    """Objektif max_carbon harus memprioritaskan sekuestrasi biochar dan offset batubara."""
    feeds = [_make_item("tempurung_kelapa", tonnage=50.0)]
    req = AllocationRequest(feedstocks=feeds, objective="max_carbon")
    out = optimize_allocation(req)
    assert out["status"] == "success"
    assert out["climate_summary"]["total_co2e_benefit_ton"] > 0


def test_custom_price_overrides():
    """Pabrik dapat menimpa harga jual per produk dalam kalkulator/solver."""
    husk = _make_item("sekam_padi")
    res_base = evaluate_feedstock(husk)
    res_override = evaluate_feedstock(husk, price_overrides={"bio_silika": 45000.0})

    p_base = res_base["products"]["bio_silika"]["economics"]["revenue_per_ton_feed"]
    p_over = res_override["products"]["bio_silika"]["economics"]["revenue_per_ton_feed"]
    assert p_over > p_base


def test_corn_cob_and_bagasse_evaluations():
    """Tongkol jagung & ampas tebu dievaluasi dengan benar."""
    corn = _make_item("tongkol_jagung")
    res_corn = evaluate_feedstock(corn)
    assert res_corn["products"]["briket"]["suitability"]["score"] >= 70.0

    bagasse = _make_item("ampas_tebu")
    res_bag = evaluate_feedstock(bagasse)
    # Ampas tebu basah (50% MC) memiliki beban pengeringan tinggi
    assert res_bag["products"]["bio_pellet"]["energy_metrics"]["thermal_drying_mj_per_ton_feed"] > 1000.0


def test_optimization_endpoints(env):
    """Pengujian integrasi endpoint API optimasi multi-biomassa."""
    # 1. Config endpoint
    cfg = env.ok("pabrik", "GET", "/factory/optimization/config")
    assert "products" in cfg and "bio_silika" in cfg["products"]
    assert "biomasses" in cfg and len(cfg["biomasses"]) >= 1

    # 2. Evaluate endpoint
    ev = env.ok("pabrik", "POST", "/factory/optimization/evaluate", {
        "code": "sekam_padi",
        "tonnage": 200.0,
    })
    assert ev["feedstock"]["code"] == "sekam_padi"
    assert "products" in ev
    assert ev["products"]["bio_silika"]["yield_kg_per_ton"] > 100.0

    # 3. Allocate endpoint
    al = env.ok("pabrik", "POST", "/factory/optimization/allocate", {
        "feedstocks": [
            {"code": "sekam_padi", "tonnage": 50.0},
            {"code": "tempurung_kelapa", "tonnage": 30.0},
        ],
        "max_briket_ton": 15.0,
        "objective": "max_profit",
    })
    assert al["status"] == "success"
    assert al["total_feedstock_input_ton"] == 80.0
    assert len(al["allocations"]) >= 1

    # 4. RBAC: Petani role tidak diizinkan mengakses optimasi alokasi pabrik (403)
    res_farmer = env.call("petani", "POST", "/factory/optimization/allocate", {
        "feedstocks": [{"code": "sekam_padi", "tonnage": 10.0}],
    })
    assert res_farmer.status_code == 403


