"""Prototipe 1 (fase 2): least-cost blending multi-biomassa + indeks alkali/slagging."""
from app.biomass_seed import BIOMASS_SEED
from app.engines.fuel_blend import KCAL_PER_MJ, BlendFeed, BlendOptimizeRequest, BlendSpec, evaluate, lhv_ar, optimize
from tests.test_field_ops import env  # noqa: F401  (fixture)

SEED = {r["code"]: r for r in BIOMASS_SEED}
PRICE = {"sekam_padi": 450, "tongkol_jagung": 650, "serbuk_sengon": 500, "tempurung_kelapa": 2000,
         "ampas_tebu": 250, "sabut_kelapa": 300}


def feed(code, kg=50_000, mc=None, **kw):
    r = SEED[code]
    return BlendFeed(code=code, name=r["name"], available_kg=kg, price_per_kg=PRICE[code],
                     moisture_pct=mc if mc is not None else r["moisture_typ_pct"], ash_pct_db=r["ash_pct_db"],
                     lhv_db_mj_kg=r["lhv_db_mj_kg"], hhv_db_mj_kg=r["hhv_db_mj_kg"], chlorine_pct_db=r["chlorine_pct_db"],
                     sulfur_pct_db=r["sulfur_pct_db"], **{f"{o}_pct_ash": r[f"{o}_pct_ash"] for o in
                                                          ("sio2", "k2o", "na2o", "cao", "mgo", "fe2o3", "al2o3", "p2o5")}, **kw)


def test_lhv_as_received_iso18125():
    assert abs(lhv_ar(17.5, 50) - 7.5285) < 1e-3                         # bagasse basah (docs/15 §3)
    assert abs(lhv_ar(14.3, 10) - (14.3 * 0.9 - 0.2443)) < 1e-9


def test_pure_corn_cob_flagged_high_slagging_risk():
    p = evaluate([feed("tongkol_jagung")], [1000], 10)
    assert p["indices"]["alkali_index"] > 0.34 and p["slagging_verdict"] == "BAHAYA"
    assert "Risiko Tinggi Terak/Slagging pada Boiler Industri" in p["warnings"][0]
    wood = evaluate([feed("serbuk_sengon")], [1000], 10)
    assert wood["indices"]["alkali_index"] < 0.17 and wood["slagging_verdict"] == "AMAN"
    husk = evaluate([feed("sekam_padi")], [1000], 10)
    assert husk["indices"]["base_acid"] < 0.206                          # B/A rendah walau AI formal tinggi (docs/15 §2)
    assert any("kristobalit" in w for w in husk["warnings"])


def test_alkali_constraint_forces_dilution_with_low_alkali_wood():
    # 4.000 kcal/kg GCV ar (praktik pasar pelet RI); NCV ar 4.000 tidak tercapai tanpa tempurung (docs/16)
    spec = BlendSpec(target_kg=10_000, product_moisture_pct=10, lhv_ar_min_mj=4000 / KCAL_PER_MJ, calorific_basis="gcv_ar",
                     ash_max_pct=10, ai_max=0.34, drying_cost_rp_per_kg_water=0)
    only_corn = optimize(BlendOptimizeRequest(feeds=[feed("tongkol_jagung")], spec=spec))
    assert not only_corn["feasible"]
    r = optimize(BlendOptimizeRequest(feeds=[feed("tongkol_jagung"), feed("serbuk_sengon")], spec=spec))
    assert r["feasible"]
    assert r["properties"]["indices"]["alkali_index"] <= 0.34 + 1e-6
    assert r["properties"]["gcv_ar_kcal_kg"] >= 3999
    assert r["feasibility_card"]["verdict"] == "LAYAK"
    shares = {c["code"]: c["share_dry_pct"] for c in r["composition"]}
    assert shares.get("serbuk_sengon", 0) > 0                             # kayu wajib masuk untuk menekan alkali


def test_least_cost_picks_cheapest_feasible_and_drying_cost_matters():
    base = dict(target_kg=10_000, product_moisture_pct=10, lhv_ar_min_mj=14.5, ash_max_pct=10, ai_max=0.34)
    feeds = [feed("ampas_tebu"), feed("serbuk_sengon", mc=15), feed("tempurung_kelapa")]   # serbuk sudah kering
    free_dry = optimize(BlendOptimizeRequest(feeds=feeds, spec=BlendSpec(**base, drying_cost_rp_per_kg_water=0)))
    costly_dry = optimize(BlendOptimizeRequest(feeds=feeds, spec=BlendSpec(**base, drying_cost_rp_per_kg_water=400)))
    share = lambda r, c: next((x["share_dry_pct"] for x in r["composition"] if x["code"] == c), 0)  # noqa: E731
    assert share(free_dry, "ampas_tebu") > share(costly_dry, "ampas_tebu")  # bagasse 50 % MC mahal dikeringkan
    assert costly_dry["cost"]["drying_rp"] >= 0 and "tempurung_kelapa" not in {c["code"] for c in free_dry["composition"]}


def test_pellet_iso_b_rejects_pure_rice_husk_ash(env):
    env.ok("pabrik", "PUT", "/biomass/sekam_padi", {"changes": {"base_price_per_kg": 450}, "source": "harga uji"})
    r = env.ok("pabrik", "POST", "/factory/fuel-blend/optimize",
               {"preset": "pelet_iso17225_6_b", "target_kg": 5000, "feeds": [{"code": "sekam_padi", "available_kg": 50000}]})
    assert r["feasible"] is False                       # abu 17,5 % & NCV terlalu rendah sekaligus (docs/15 §9b)
    assert any("Biaya pengeringan" in n for n in r["notes"])
    env.ok("pabrik", "PUT", "/biomass/serbuk_sengon", {"changes": {"base_price_per_kg": 500}, "source": "harga uji"})
    ok = env.ok("pabrik", "POST", "/factory/fuel-blend/optimize",
                {"preset": "pelet_iso17225_6_b", "target_kg": 5000,
                 "feeds": [{"code": "sekam_padi", "available_kg": 50000}, {"code": "serbuk_sengon", "available_kg": 50000}]})
    assert ok["feasible"] and ok["properties"]["ash_pct_db"] <= 10 + 1e-6
    assert env.call("pengepul", "POST", "/factory/fuel-blend/optimize",
                    {"target_kg": 1, "feeds": [{"code": "sekam_padi", "available_kg": 1}]}).status_code == 403
    missing = env.call("pabrik", "POST", "/factory/fuel-blend/optimize",
                       {"target_kg": 100, "feeds": [{"code": "sabut_kelapa", "available_kg": 1000}]})
    assert missing.status_code == 422 and "Harga" in missing.json()["detail"]


def test_slider_evaluate_endpoint(env):
    env.ok("pabrik", "PUT", "/biomass/tongkol_jagung", {"changes": {"base_price_per_kg": 650}, "source": "harga uji"})
    env.ok("pabrik", "PUT", "/biomass/serbuk_sengon", {"changes": {"base_price_per_kg": 500}, "source": "harga uji"})
    feeds = [{"code": "tongkol_jagung", "available_kg": 1000}, {"code": "serbuk_sengon", "available_kg": 1000}]
    hot = env.ok("pabrik", "POST", "/factory/fuel-blend/evaluate", {"feeds": feeds, "shares_pct": {"tongkol_jagung": 100}})
    mix = env.ok("pabrik", "POST", "/factory/fuel-blend/evaluate",
                 {"feeds": feeds, "shares_pct": {"tongkol_jagung": 40, "serbuk_sengon": 60}})
    assert hot["slagging_verdict"] == "BAHAYA" and mix["indices"]["alkali_index"] < hot["indices"]["alkali_index"]
    pres = env.ok("pabrik", "GET", "/factory/fuel-blend/presets")
    assert "pelet_4000_kcal" in pres["presets"] and pres["drying_cost_rp_per_kg_water"] is None
