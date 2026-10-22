"""Prototipe 2 (fase 3): energi riil basis as-received, listrik η 22/28/36 %, CO₂ dihindari & pohon keputusan."""
from app.biomass_seed import BIOMASS_SEED
from app.engines.conversion_energy import ConversionInput, analyse, lhv_ar
from tests.test_field_ops import env  # noqa: F401  (fixture)

S = {r["code"]: r for r in BIOMASS_SEED}


def run(code, t, mc=None, km=None, **kw):
    r = S[code]
    return analyse(ConversionInput(
        code=code, name=r["name"], ton_per_month=t, moisture_pct=mc if mc is not None else r["moisture_typ_pct"],
        ash_pct_db=r["ash_pct_db"], lhv_db_mj_kg=r["lhv_db_mj_kg"], hhv_db_mj_kg=r["hhv_db_mj_kg"],
        volatile_pct_db=r["volatile_pct_db"], fixed_carbon_pct_db=r["fixed_carbon_pct_db"],
        chlorine_pct_db=r["chlorine_pct_db"], sio2_pct_ash=r["sio2_pct_ash"], k2o_pct_ash=r["k2o_pct_ash"],
        na2o_pct_ash=r["na2o_pct_ash"], distance_to_pltu_km=km, **kw))


def test_protocol_formulas():
    a = run("sekam_padi", 100, mc=12)
    lhv = 14.3 * 0.88 - 2.443 * 0.12
    assert abs(a["energy"]["lhv_ar_mj_kg"] - lhv) < 1e-3
    assert abs(a["energy"]["thermal_gj_per_month"] - 100_000 * lhv / 1000) < 0.1
    el = a["energy"]["electricity_mwh_per_month"]
    assert abs(el["turbin_uap_kecil"] - 100_000 * lhv * 0.22 / 3600) < 0.01        # E_el = m·LHV·η/3600
    assert abs(el["terintegrasi"] - 100_000 * lhv * 0.28 / 3600) < 0.01
    assert abs(a["energy"]["co2_avoided_t_per_month"]["turbin_uap_kecil"] - el["turbin_uap_kecil"] * 0.87) < 0.01


def test_wet_biomass_energy_collapses_and_drying_is_charged():
    dry, wet = run("ampas_tebu", 1000, mc=15), run("ampas_tebu", 1000, mc=50)
    assert wet["energy"]["lhv_ar_mj_kg"] < dry["energy"]["lhv_ar_mj_kg"] / 1.8
    assert lhv_ar(17.5, 95) < 0
    comb = next(r for r in wet["routes"] if r["route"] == "gasifikasi")
    assert comb["drying_gj_per_month"] > 0
    assert any("pengeringan" in w for w in wet["warnings"])


def test_decision_tree_routes_match_field_practice():
    assert run("sekam_padi", 1000)["decision"]["route"] == "pirolisis"                       # biochar + bio-silika
    assert run("tempurung_kelapa", 100, mc=10)["routes"][0]["product"] == "arang / karbon aktif"
    sawdust = run("serbuk_sengon", 1500, mc=20, km=40)
    assert sawdust["decision"]["route"] == "cofiring"
    assert run("serbuk_sengon", 1500, mc=20, km=400)["decision"]["route"] != "cofiring"     # terlalu jauh dari PLTU
    assert run("serbuk_sengon", 1500, mc=45, km=40)["decision"]["route"] != "cofiring"      # basah: gagal spek TM ≤ 25 %
    assert run("ampas_tebu", 3000)["decision"]["route"] == "pembakaran"                     # boiler pabrik gula
    corn = run("tongkol_jagung", 300)                                                        # AI 0,40 > 0,34
    assert corn["decision"]["route"] not in ("gasifikasi", "pembakaran", "cofiring")
    assert any("alkali" in w for w in corn["warnings"])
    coir = run("sabut_kelapa", 1500)                                                         # Cl 0,8 %: korosi
    assert coir["decision"]["route"] == "pembakaran_kecil" and any("Klorin" in w for w in coir["warnings"])
    assert run("serbuk_karet", 200, mc=15)["decision"]["route"] == "gasifikasi"            # kering, abu & alkali rendah
    path = sawdust["decision"]["path"]
    assert path[0]["answer"] == "tidak" and path[-1]["route"] == "cofiring"


def test_endpoint_uses_master_and_roles(env):
    r = env.ok("pabrik", "POST", "/factory/conversion/analyse", {"code": "sekam_padi", "ton_per_month": 500})
    assert r["decision"]["route"] == "pirolisis" and r["energy"]["grid_ef_t_per_mwh"] == 0.87
    assert env.call("auditor", "POST", "/factory/conversion/analyse", {"code": "sekam_padi", "ton_per_month": 5}).status_code == 200
    assert env.call("petani", "POST", "/factory/conversion/analyse", {"code": "sekam_padi", "ton_per_month": 5}).status_code == 403
    assert env.call("pabrik", "POST", "/factory/conversion/analyse", {"code": "x", "ton_per_month": 5}).status_code == 422


def test_drying_not_double_counted():
    """Audit: energi bersih rute = E_th(ar) + 2,443·air diuapkan − energi pengering (panas laten tidak dihitung dua kali)."""
    a = run("ampas_tebu", 1000, mc=50)
    gas = next(r for r in a["routes"] if r["route"] == "gasifikasi")
    water = 1000 * 0.5 - 500 * 15 / 85
    net = a["energy"]["thermal_gj_per_month"] + 2.443 * water - water * 3.0
    assert abs(gas["electricity_mwh_per_month"] - net * 0.28 / 3.6) < 0.5
