"""Prototipe 3 (fase 4): SEC/IKE ternormalisasi, batas bergerak ±2σ/±3σ, CUSUM, indikator pengering & hammer mill."""
import random

from app.engines.sec_monitor import OpsAnalysisRequest, OpsLog, _water_t, analyse
from tests.test_field_ops import env  # noqa: F401  (fixture)


def scenario(vary_baseline=True, spike_at=27, seed=1):
    random.seed(seed)
    logs = []
    for i in range(30):
        H, cap, util, mc = 8, 2.0, 0.9, 14
        if vary_baseline and i % 4 == 0 and i < 14:
            util = 0.6
        if i == 20:
            util = 0.4                                 # beban parsial, efisiensi normal
        if i == 24:
            mc = 24                                    # bahan basah
        T = cap * H * util
        E = 400 * H + 250 * T + 3000 * _water_t(T, mc, 10)
        hm = 18 * T
        if i == spike_at:
            E *= 1.35                                  # injeksi konsumsi daya tinggi
        if i >= 28:
            hm = 30 * T                                # hammer aus
        E *= 1 + random.gauss(0, 0.02)
        logs.append(OpsLog(label=f"D{i:02d}", kwh_total=E / 3.6, kwh_hammer_mill=hm, operating_hours=H,
                           product_ton=T, feed_moisture_pct=mc, rated_capacity_t_h=cap))
    return logs


def by_label(a):
    return {r["label"]: r for r in a["rows"]}


def test_partial_load_raises_raw_sec_but_no_false_alarm():
    a = analyse(OpsAnalysisRequest(logs=scenario()))
    d20, d19 = by_label(a)["D20"], by_label(a)["D19"]
    assert d20["sec_mj_per_t"] > 1.3 * d19["sec_mj_per_t"]                  # SEC mentah melonjak saat beban 40 %
    assert d20["alert"] is None and abs(d20["enpi"] - 1) < 0.08                 # ternormalisasi: normal
    assert a["baseline"]["fixed_load_basis"].startswith("regresi")


def test_injected_high_consumption_triggers_action_alarm():
    a = analyse(OpsAnalysisRequest(logs=scenario()))
    d27 = by_label(a)["D27"]
    assert d27["alert"] == "aksi" and d27["residual_pct"] > d27["band_action_pct"]
    assert any(c["code"] == "konsumsi_di_atas_baseline" for c in d27["causes"])
    assert sum(1 for r in a["rows"] if r["alert"]) <= 2                        # tidak banjir alarm


def test_wet_feed_and_hammer_mill_indicators_with_iso50001_cards():
    a = analyse(OpsAnalysisRequest(logs=scenario()))
    rows = by_label(a)
    assert any(c["code"] == "pengering_bahan_basah" for c in rows["D24"]["causes"]) and rows["D24"]["alert"] is None
    assert any(c["code"] == "hammer_mill_gesekan" for c in rows["D29"]["causes"])
    titles = [r["title"] for r in a["recommendations"]]
    assert titles[0] == "Tekan kadar air bahan masuk" and "Perawatan hammer mill" in titles
    assert all("iso50001" in r for r in a["recommendations"])


def test_constant_baseline_utilization_warns_or_uses_idle_kw():
    flat = analyse(OpsAnalysisRequest(logs=scenario(vary_baseline=False)))
    assert flat["baseline"]["fixed_load_basis"] == "tidak teridentifikasi" and flat["baseline"]["notes"]
    measured = analyse(OpsAnalysisRequest(logs=scenario(vary_baseline=False), idle_kw=400 / 3.6))
    d20 = by_label(measured)["D20"]
    assert measured["baseline"]["fixed_load_basis"] == "daya idle terukur" and d20["alert"] is None


def test_gradual_drift_detected_by_cusum():
    random.seed(3)
    logs = []
    for i in range(40):
        T = 14.4
        E = (400 * 8 + 250 * T) * (1 + (0.012 * (i - 20) if i > 20 else 0)) * (1 + random.gauss(0, 0.01))
        logs.append(OpsLog(label=f"D{i:02d}", kwh_total=E / 3.6, operating_hours=8, product_ton=T, rated_capacity_t_h=2))
    a = analyse(OpsAnalysisRequest(logs=logs, baseline_n=20, idle_kw=400 / 3.6))
    assert any(x["code"] == "cusum_drift" for x in a["alerts"])
    assert "Degradasi efisiensi persisten" in [r["title"] for r in a["recommendations"]]


def test_ingest_and_analysis_endpoints(env):
    logs = scenario()
    body = {"facility": "Pabrik Pelet Sleman", "logs": [
        {"log_date": f"2026-09-{i + 1:02d}", "kwh_total": l.kwh_total, "kwh_hammer_mill": l.kwh_hammer_mill,
         "operating_hours": l.operating_hours, "product_ton": l.product_ton, "feed_moisture_pct": l.feed_moisture_pct,
         "rated_capacity_t_h": l.rated_capacity_t_h, "client_event_id": f"e2e-{i}"} for i, l in enumerate(logs)]}
    assert env.call("pengepul", "POST", "/factory/energy/ops-logs", body).status_code == 403
    r = env.ok("pabrik", "POST", "/factory/energy/ops-logs", body, status=201)
    assert r["created"] == 30 and r["skipped"] == []
    again = env.ok("pabrik", "POST", "/factory/energy/ops-logs", body, status=201)       # antrean offline dikirim ulang
    assert again["created"] == 0 and len(again["skipped"]) == 30
    a = env.ok("auditor", "GET", "/factory/energy/ops-analysis?facility=Pabrik%20Pelet%20Sleman&feed_code=sekam_padi")
    assert a["baseline"]["feed_moisture_ref_pct"] == 12
    assert any(row["alert"] == "aksi" for row in a["rows"])
    assert env.ok("pabrik", "GET", "/factory/energy/ops-facilities")[0]["logs"] == 30
    few = env.call("pabrik", "GET", "/factory/energy/ops-analysis?facility=Kosong")
    assert few.status_code == 422
