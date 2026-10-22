"""Engine ⑧ Feedstock, ⑨ Waste-to-Energy, ⑩ Analitik Energi (IKE/SEC/anomali) + API & RBAC."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engines.biomass_data import (REF_HUSK_FC, REF_HUSK_VM, biochar_yield_estimate, hhv_parikh,
                                      lhv_as_received, presets)
from app.engines.energy import EnergyAnalysisRequest, analyze, classify_ike
from app.engines.feedstock import FeedstockCompareRequest, compare_feedstocks, topsis
from app.engines.quality import REF_ASH, biochar_yield_db
from app.engines.waste_energy import WasteStream, advise
from app.main import app
from app.seed import demo_energy_history
from tests.conftest import demo_headers


# ---------------------------------------------------------------- korelasi bahan bakar
def test_parikh_hhv_matches_published_coefficients():
    assert hhv_parikh(15, 64, 18) == pytest.approx(0.3536 * 15 + 0.1559 * 64 - 0.0078 * 18)
    assert 14 < hhv_parikh(18, 64, 18) < 17          # sekam padi tipikal 14–17 MJ/kg


def test_lhv_decreases_with_moisture_and_is_below_hhv():
    hhv = 18.0
    vals = [lhv_as_received(hhv, m) for m in (0, 15, 30, 60)]
    assert vals[0] < hhv and all(a > b for a, b in zip(vals, vals[1:]))


@pytest.mark.parametrize("temp", [350, 500, 650])
def test_yield_model_reproduces_husk_calibration(temp):
    assert biochar_yield_estimate(REF_HUSK_FC, REF_HUSK_VM, REF_ASH, temp) == pytest.approx(biochar_yield_db(temp, REF_ASH))


# ---------------------------------------------------------------- ⑧ perbandingan feedstock
def _fs(**kw):
    return {"cost_per_ton": 500_000, "stock_ton": 50, **kw}


def test_topsis_dominant_alternative_ranks_first():
    rows = [{"a": 10, "b": 1}, {"a": 5, "b": 5}, {"a": 1, "b": 9}]
    s = topsis(rows, [("a", 0.5, +1), ("b", 0.5, -1)])
    assert s[0] == pytest.approx(1.0) and s[2] == pytest.approx(0.0)


def test_high_ash_feedstock_ranks_last_for_pellet():
    out = compare_feedstocks(FeedstockCompareRequest(purpose="pellet", feedstocks=[
        _fs(id="sekam", preset="sekam_padi", cost_per_ton=400_000),
        _fs(id="serbuk", preset="serbuk_gergaji"), _fs(id="tongkol", preset="tongkol_jagung")]))
    assert out["ranking"][-1]["id"] == "sekam"
    assert "kadar abu" in out["ranking"][-1]["weaknesses"]


def test_compare_runs_lp_blend_when_spec_given():
    out = compare_feedstocks(FeedstockCompareRequest(
        feedstocks=[_fs(id="sekam", preset="sekam_padi", stock_ton=120), _fs(id="serbuk", preset="serbuk_gergaji", stock_ton=60)],
        spec={"ash_max": 10}, target_ton=50))
    assert out["blend"]["feasible"] and out["blend"]["blend_properties"]["ash"] <= 10 + 1e-6
    assert out["computation_details"]["formulas"]["TOPSIS"]


def test_inconsistent_proximate_is_rejected():
    with pytest.raises(ValidationError):
        FeedstockCompareRequest(feedstocks=[_fs(id="x", moisture=10, ash=10, volatile_matter=10, fixed_carbon=10),
                                            _fs(id="y", preset="sekam_padi")])


# ---------------------------------------------------------------- ⑨ waste-to-energy
@pytest.mark.parametrize("preset,expected_top", [
    ("sekam_padi", "Pirolisis lambat (biochar)"),
    ("kotoran_sapi", "Digestasi anaerob (biogas)"),
    ("sisa_makanan", "Digestasi anaerob (biogas)"),
])
def test_technology_recommendation_follows_moisture_logic(preset, expected_top):
    out = advise(WasteStream(preset=preset, ton_per_day=10))
    assert out["technologies"][0]["technology"] == expected_top


def test_energy_outputs_never_exceed_primary_energy():
    out = advise(WasteStream(preset="tempurung_kelapa", ton_per_day=10))
    primary_mwh = out["energy_potential"]["setara_listrik_mwh_teoritis"]
    for t in out["technologies"]:
        assert t["outputs"].get("listrik_mwh_per_tahun", 0) <= primary_mwh


def test_off_range_cn_is_flagged_for_codigestion():
    out = advise(WasteStream(preset="tkks", ton_per_day=50))
    ad = next(t for t in out["technologies"] if "anaerob" in t["technology"])
    assert any("co-digestion" in n for n in ad["notes"])


def test_volume_scales_energy_linearly():
    a = advise(WasteStream(preset="sekam_padi", ton_per_day=10))["energy_potential"]["energi_primer_gj_per_tahun"]
    b = advise(WasteStream(preset="sekam_padi", ton_per_day=20))["energy_potential"]["energi_primer_gj_per_tahun"]
    assert b == pytest.approx(2 * a, rel=1e-3)


# ---------------------------------------------------------------- ⑩ analitik energi
def _req(rows, **kw):
    keys = ("period", "kwh", "building_kwh", "production_ton", "peak_kw", "operating_hours", "cost_rp")
    return EnergyAnalysisRequest(facility="uji", floor_area_m2=300,
                                 readings=[{k: r.get(k) for k in keys if r.get(k) is not None} for r in rows], **kw)


def test_injected_waste_months_are_detected_exactly():
    rows = demo_energy_history()
    out = analyze(_req(rows))
    injected = {r["period"] for r in rows if r["note"]}
    assert {a["period"] for a in out["anomalies"]} == injected
    # Nilai sebenarnya 95 kWh/t; noise ±3% pada 12 bulan acuan → galat baku kemiringan ≈ ±10 kWh/t.
    assert out["baseline"]["kwh_per_ton"] == pytest.approx(95, abs=12)
    assert out["baseline"]["base_load_kwh_per_month"] == pytest.approx(18_000, rel=0.25)
    assert out["baseline"]["r2"] > 0.9
    assert out["summary"]["waste_rp"] > 0 and out["recommendations"][0]["title"] == "Telusuri bulan pemborosan"


def test_cusum_ends_near_total_excess():
    out = analyze(_req(demo_energy_history()))
    assert out["series"][-1]["cusum_kwh"] == pytest.approx(sum(p["residual_kwh"] for p in out["series"]), abs=24)


@pytest.mark.parametrize("ike,btype,label", [
    (8.0, "ac", "Sangat efisien"), (12, "ac", "Efisien"), (16, "ac", "Cukup efisien"), (20, "ac", "Boros"),
    (3.0, "non_ac", "Sangat efisien"), (8.0, "non_ac", "Boros"),
])
def test_ike_classification_follows_permen_esdm(ike, btype, label):
    assert classify_ike(ike, btype) == label


def test_ike_without_building_meter_is_only_indicative():
    rows = [dict(r, building_kwh=None) for r in demo_energy_history()]
    assert analyze(_req(rows))["summary"]["ike_category"].startswith("Indikatif")


def test_flat_production_falls_back_to_mean_baseline():
    rows = [{"period": f"2025-{m:02d}", "kwh": 10_000 + m, "production_ton": 0} for m in range(1, 9)]
    out = analyze(_req(rows))
    assert out["baseline"]["model"].startswith("rata-rata") and out["summary"]["sec_kwh_per_ton_avg"] is None


def test_duplicate_periods_rejected():
    rows = [{"period": "2025-01", "kwh": 1, "production_ton": 1}] * 6
    with pytest.raises(ValueError):
        analyze(_req(rows))


# ---------------------------------------------------------------- API (histori dari database) & RBAC
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_energy_analysis_reads_history_from_database(client):
    r = client.get("/api/v1/factory/energy/analysis", headers=demo_headers(client, "pabrik"))
    assert r.status_code == 200
    body = r.json()
    assert body["data_source"]["table"] == "energy_readings" and body["data_source"]["rows"] >= 6
    assert body["summary"]["ike_category"] and body["anomalies"]


@pytest.fixture
def cleanup_test_facility():
    yield
    import asyncio
    from sqlalchemy import delete
    import app.database as dbm
    from app.models.energy import EnergyMeterReading

    async def purge():
        async with dbm.async_session() as s:
            await s.execute(delete(EnergyMeterReading).where(EnergyMeterReading.facility == "Gudang Uji"))
            await s.commit()
    asyncio.run(purge())


def test_pabrik_can_record_reading_and_it_is_used(client, cleanup_test_facility):
    h = demo_headers(client, "pabrik")
    body = {"facility": "Gudang Uji", "kwh": 5000, "building_kwh": 900, "production_ton": 40, "floor_area_m2": 100}
    for m in range(1, 7):
        assert client.post("/api/v1/factory/energy/readings", headers=h,
                           json={**body, "period": f"2025-{m:02d}", "kwh": 5000 + 10 * m}).status_code == 201
    out = client.get("/api/v1/factory/energy/analysis?facility=Gudang%20Uji", headers=h).json()
    assert out["data_source"]["rows"] == 6 and out["summary"]["ike_kwh_m2_month_avg_12m"] == 9.0


@pytest.mark.parametrize("role,method,path,code", [
    ("auditor", "GET", "/api/v1/factory/energy/analysis", 200),
    ("auditor", "POST", "/api/v1/factory/energy/readings", 403),
    ("petani", "GET", "/api/v1/factory/energy/analysis", 403),
    ("driver", "POST", "/api/v1/labs/waste-energy/advise", 403),
    ("pengepul", "POST", "/api/v1/labs/feedstock/compare", 403),
])
def test_bioenergy_rbac(client, role, method, path, code):
    assert client.request(method, path, headers=demo_headers(client, role), json={}).status_code == code


def test_lab_endpoints_work_for_pabrik(client):
    h = demo_headers(client, "pabrik")
    assert len(client.get("/api/v1/labs/biomass/presets", headers=h).json()) == len(presets())
    r = client.post("/api/v1/labs/waste-energy/advise", headers=h, json={"preset": "kotoran_sapi", "ton_per_day": 15})
    assert r.status_code == 200 and r.json()["technologies"][0]["outputs"]["metana_m3_per_tahun"] > 0
    r = client.post("/api/v1/labs/feedstock/compare", headers=h, json={"feedstocks": [
        {"id": "a", "preset": "sekam_padi", "cost_per_ton": 400000}, {"id": "b", "preset": "tongkol_jagung", "cost_per_ton": 650000}]})
    assert r.status_code == 200 and r.json()["ranking"][0]["rank"] == 1
