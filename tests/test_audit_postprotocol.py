"""Regresi hasil audit pasca-protokol multi-biomassa (3 auditor: backend, engine, race/XSS)."""
import random

from app.engines.fuel_blend import BlendOptimizeRequest, BlendSpec, evaluate, optimize
from app.engines.sec_monitor import OpsAnalysisRequest, OpsLog, analyse
from tests.test_field_ops import PROX, env  # noqa: F401  (fixture)
from tests.test_fuel_blend import feed
from tests.test_phase5_integrated import _parallel, _price


def _auction_lot(env, kg=500, code="sekam_padi", price=400, mc_ad=None):
    body = {"quantity_kg": kg, "commodity": code, "allow_jemput": True, "ask_price_jemput": price}
    if mc_ad is not None:
        body["moisture_pct"] = mc_ad
    lst = env.ok("petani", "POST", "/farmer/listings", body, status=201)
    bid = env.ok("pengepul", "POST", "/collector/bids", {"listing_id": lst["id"], "scheme": "jemput", "price_per_kg": price,
                                                          "quantity_kg": kg}, status=201)
    return env.ok("petani", "POST", f"/farmer/listings/{lst['id']}/accept", {"bid_id": bid["bid_id"], "quantity_kg": kg})["harvest_id"]


# ---------------------------------------------------------------- backend (auditor A)
def test_auction_wet_commodity_uses_commodity_reference_moisture(env):
    hid = _auction_lot(env, kg=1000, code="ampas_tebu", price=300)
    v = env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": hid, "weighed_kg": 1000, "moisture": 50,
                                                          "contamination": 0})
    assert abs(v["total_price"] - 300_000) < 1                      # MC 50 % = acuan bagasse → tidak dipotong ±43 %


def test_preview_matches_verify_with_contaminant_tolerance(env):
    _price(env, "tongkol_jagung", 650)
    prev = env.ok("pengepul", "POST", "/collector/refraction-preview",
                  {"commodity": "tongkol_jagung", "kg": 1000, "moisture_pct": 15, "contaminant_pct": 2})
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 1000, "commodity": "tongkol_jagung"}, status=201)
    v = env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 1000, "moisture": 15,
                                                          "contamination": 2})
    assert prev["value_rp"] == round(v["total_price"]) == 650_000


def test_harvest_booked_into_warehouse_once_and_within_weight(env):
    _price(env, "tongkol_jagung", 650)
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 100, "commodity": "tongkol_jagung"}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 100, "moisture": 15, "contamination": 0})
    w = env.ok("pengepul", "POST", "/collector/warehouses", {"name": "G Audit"}, status=201)
    url = f"/collector/warehouses/{w['id']}/movements"
    assert env.call("pengepul", "POST", url, {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 5000,
                                              "harvest_id": h["id"]}).status_code == 422
    ok = {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 100, "moisture_pct": 15, "harvest_id": h["id"]}
    env.ok("pengepul", "POST", url, ok, status=201)
    assert env.call("pengepul", "POST", url, ok).status_code == 409
    raw = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 50, "commodity": "tongkol_jagung"}, status=201)
    raw_body = {**ok, "kg": 50, "harvest_id": raw["id"]}
    assert env.call("pengepul", "POST", url, raw_body).status_code in (404, 409)      # bukan lot saya / belum ditimbang


def test_replay_keys_of_other_users_do_not_leak(env):
    w1 = env.ok("pengepul", "POST", "/collector/warehouses", {"name": "G1"}, status=201)
    w2 = env.ok("pengepul2", "POST", "/collector/warehouses", {"name": "G2"}, status=201)
    body = {"commodity": "sekam_padi", "movement": "masuk", "kg": 10, "moisture_pct": 12, "note": "rahasia A",
            "client_event_id": "kunci-A"}
    env.ok("pengepul", "POST", f"/collector/warehouses/{w1['id']}/movements", body, status=201)
    r = env.call("pengepul2", "POST", f"/collector/warehouses/{w2['id']}/movements", body)
    assert r.status_code == 409 and "rahasia" not in r.text
    pf = env.ok("pengepul2", "POST", "/collector/proxy-farmers", {"full_name": "Mbah Uji", "consent_given": True}, status=201)
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 10, "client_event_id": "kunci-P"}, status=201)
    leak = env.call("pengepul2", "POST", "/collector/proxy-harvest",
                    {"farmer_id": pf.get("id") or pf.get("farmer_id"), "quantity_kg": 10, "client_event_id": "kunci-P"})
    assert leak.status_code == 409 and h["qr_code"] not in leak.text


def test_inactive_commodity_does_not_strand_stock_or_lots(env):
    _price(env, "tongkol_jagung", 650)
    w = env.ok("pengepul", "POST", "/collector/warehouses", {"name": "G Nonaktif"}, status=201)
    url = f"/collector/warehouses/{w['id']}/movements"
    env.ok("pengepul", "POST", url, {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 300, "moisture_pct": 15}, status=201)
    lot = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 200, "commodity": "tongkol_jagung"}, status=201)
    env.ok("pabrik", "PUT", "/biomass/tongkol_jagung", {"changes": {"is_active": False}, "source": "musim habis"})
    env.ok("pengepul", "POST", url, {"commodity": "tongkol_jagung", "movement": "keluar", "kg": 300}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": lot["id"], "weighed_kg": 200, "moisture": 15, "contamination": 0})
    assert env.call("pengepul", "POST", url, {"commodity": "tongkol_jagung", "movement": "masuk", "kg": 10}).status_code == 422
    assert env.call("petani", "POST", "/farmer/harvest", {"quantity_kg": 5, "commodity": "tongkol_jagung"}).status_code == 422


def test_verify_accepts_fresh_wet_sawdust_for_drying(env):
    _price(env, "serbuk_sengon", 500)
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 800, "commodity": "serbuk_sengon"}, status=201)
    r = env.call("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 800, "moisture": 65,
                                                            "contamination": 0, "beli_untuk_dikeringkan": True})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------- engine (auditor B)
def _flat_logs(n=20):
    return [OpsLog(label=f"D{i}", kwh_total=2000 * (1 + 0.01 * (i % 3)), operating_hours=8, product_ton=10,
                   feed_moisture_pct=45 if i % 4 else None, rated_capacity_t_h=2) for i in range(n)]


def test_sec_monitor_unlogged_dryer_energy_no_nan_and_api_ok(env):
    a = analyse(OpsAnalysisRequest(logs=_flat_logs()))
    assert a["baseline"]["beta_mj_per_t_water"] == 0 and any("pengering" in n for n in a["baseline"]["notes"])
    assert all(r["enpi"] is not None for r in a["rows"])
    logs = [{"log_date": f"2026-07-{i + 1:02d}", "kwh_total": l.kwh_total, "operating_hours": 8, "product_ton": 10,
             "feed_moisture_pct": l.feed_moisture_pct} for i, l in enumerate(_flat_logs())]
    env.ok("pabrik", "POST", "/factory/energy/ops-logs", {"facility": "NaN Test", "logs": logs}, status=201)
    assert env.call("pabrik", "GET", "/factory/energy/ops-analysis?facility=NaN%20Test").status_code == 200
    assert env.call("pabrik", "GET", "/factory/energy/ops-analysis?facility=NaN%20Test&idle_kw=0").status_code in (200, 422)


def test_sec_monitor_missing_moisture_is_imputed_not_zero():
    rnd = random.Random(2)
    logs = []
    for i in range(30):
        t, mc = 14.4, 18
        e = 400 * 8 + 250 * t + 3000 * (t * 0.9 * (mc / 82 - 10 / 90))
        if i == 25:
            e *= 1.25
        e *= 1 + rnd.gauss(0, 0.01)
        logs.append(OpsLog(label=f"D{i}", kwh_total=e / 3.6, operating_hours=8, product_ton=t,
                           feed_moisture_pct=None if i % 3 == 0 else mc, rated_capacity_t_h=2))
    a = analyse(OpsAnalysisRequest(logs=logs, idle_kw=400 / 3.6))
    assert a["rows"][25]["alert"] == "aksi" and a["baseline"]["residual_sd_pct"] < 3
    assert a["rows"][3]["feed_moisture_imputed"] is True


def test_unknown_alkali_fails_closed_and_card_uses_configured_limit():
    corn_unknown = feed("tongkol_jagung").model_copy(update={"k2o_pct_ash": None, "na2o_pct_ash": None})
    p = evaluate([corn_unknown], [1000], 10)
    assert p["indices"]["alkali_index"] is None and p["slagging_verdict"] == "WASPADA"
    spec = BlendSpec(target_kg=1000, product_moisture_pct=10, ai_max=0.34, drying_cost_rp_per_kg_water=0)
    assert optimize(BlendOptimizeRequest(feeds=[corn_unknown], spec=spec))["feasible"] is False
    loose = optimize(BlendOptimizeRequest(feeds=[feed("tongkol_jagung")], spec=spec.model_copy(update={"ai_max": 0.5})))
    assert loose["feasible"] and loose["feasibility_card"]["verdict"] == "LAYAK"     # kartu = batas optimizer


def test_duplicate_feed_codes_return_422(env):
    _price(env, "sekam_padi", 450)
    feeds = [{"code": "sekam_padi", "available_kg": 100}, {"code": "sekam_padi", "available_kg": 100}]
    assert env.call("pabrik", "POST", "/factory/fuel-blend/optimize", {"target_kg": 50, "feeds": feeds}).status_code == 422
    assert env.call("pabrik", "POST", "/factory/fuel-blend/evaluate",
                    {"feeds": feeds, "shares_pct": {"sekam_padi": 100}}).status_code == 422


# ---------------------------------------------------------------- race (auditor C)
def test_dp_and_final_payment_race_never_overpays(env):
    for _ in range(4):
        hid = _auction_lot(env)
        env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": hid, "weighed_kg": 500, **PROX})
        res = _parallel(env, [("pengepul", "POST", f"/collector/harvests/{hid}/pay-dp", {"amount_rp": 20_000, "method": "tunai"}),
                              ("pengepul", "POST", f"/collector/harvests/{hid}/pay-farmer", {"method": "tunai"})])
        dp, pay = res
        if dp.status_code == 201 and pay.status_code == 201:
            assert pay.json()["dp_rp"] == 20_000                                    # DP dipotong, bukan dibayar ganda


def test_concurrent_redemptions_cannot_overdraw_wallet(env):
    async def credit(s):
        from app.models.ledger import BiocharLedgerEntry
        s.add(BiocharLedgerEntry(farmer_id=env.uid["petani"], entry_type="adjustment", amount_kg=100, note="uji",
                                 created_by_id=env.uid["pabrik"]))
        await s.commit()
    env.q(credit)
    res = _parallel(env, [("petani", "POST", "/farmer/biochar/redeem", {"kg": 80}) for _ in range(3)])
    assert sorted(r.status_code for r in res).count(201) == 1


def test_concurrent_finished_goods_sales_never_negative(env):
    env.ok("pabrik", "POST", "/factory/inventory/movements", {"product": "biochar", "movement": "penyesuaian",
                                                               "quantity_kg": 1000, "note": "stok awal uji"}, status=201)
    res = _parallel(env, [("pabrik", "POST", "/factory/inventory/movements",
                           {"product": "biochar", "movement": "penjualan", "quantity_kg": 700, "unit_price_rp": 3000})
                          for _ in range(3)])
    assert sum(1 for r in res if r.status_code == 201) == 1
    assert env.ok("pabrik", "GET", "/factory/inventory")["balance_kg"]["biochar"] >= 0
