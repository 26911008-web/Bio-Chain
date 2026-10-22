import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_quality_good_husk_is_grade_a(client, pabrik):
    r = client.post("/api/v1/labs/quality/score", headers=pabrik, json={"moisture": 11, "ash": 18, "volatile_matter": 66,
                                            "fixed_carbon": 16, "contamination": 1.5}).json()
    assert r["grade"] == "A"
    assert 37 <= r["pred_biochar_yield_pct_db"] <= 57


def test_quality_wet_husk_rejected(client, pabrik):
    r = client.post("/api/v1/labs/quality/score", headers=pabrik, json={"moisture": 30, "ash": 18, "volatile_matter": 66,
                                            "fixed_carbon": 16}).json()
    assert r["grade"] == "TOLAK"


def test_blend_meets_spec(client, pabrik):
    d = client.get("/api/v1/labs/blend/defaults", headers=pabrik).json()
    spec = d["products"]["biochar_tanah"]["spec"]
    r = client.post("/api/v1/labs/blend/recommend", headers=pabrik, json={"feedstocks": d["feedstocks"], "spec": spec, "target_ton": 50}).json()
    assert r["feasible"]
    assert sum(c["ton"] for c in r["composition"]) == 50
    assert r["blend_properties"]["ash"] <= spec["ash_max"] + 1e-6
    assert r["blend_properties"]["fixed_carbon"] >= spec["fixed_carbon_min"] - 1e-6


def test_blend_infeasible_reports_blocking_constraint(client, pabrik):
    d = client.get("/api/v1/labs/blend/defaults", headers=pabrik).json()
    spec = d["products"]["quick_light_charcoal"]["spec"]
    r = client.post("/api/v1/labs/blend/recommend", headers=pabrik, json={"feedstocks": d["feedstocks"], "spec": spec, "target_ton": 100}).json()
    assert not r["feasible"] and r["relax_one_of"]


def test_routes_respect_volume_capacity_and_beat_baseline(client, pabrik):
    r = client.post("/api/v1/labs/routes/optimize", headers=pabrik, json={"vehicle_m3": 30}).json()
    assert all(rt["load_m3"] <= 30 + 1e-6 for rt in r["routes"])
    served = sum(s["ton"] for rt in r["routes"] for s in rt["stops"])
    assert abs(served - r["summary"]["total_ton"]) < 0.1
    assert r["summary"]["total_km"] < r["summary"]["baseline_km"]


def test_all_five_engines_return_computation_details(client, pabrik):
    """T4: Kelima engine lama mengembalikan computation_details dengan steps tidak kosong
    dan nilai langkah terakhir = nilai hasil utama."""
    # 1. Quality
    q = client.post("/api/v1/labs/quality/score", headers=pabrik,
                    json={"moisture": 11, "ash": 18, "volatile_matter": 66, "fixed_carbon": 16, "contamination": 1.5}).json()
    assert "computation_details" in q
    cd_q = q["computation_details"]
    assert len(cd_q["steps"]) > 0
    assert cd_q["steps"][-1]["value"] == q["score"]
    assert len(cd_q["parameters_used"]) > 0

    # 2. Carbon
    c = client.post("/api/v1/labs/carbon/calculate", headers=pabrik,
                    json={"biomass_ton": 100, "distance_km": 25, "vehicle_type": "diesel_small"}).json()
    assert "computation_details" in c
    cd_c = c["computation_details"]
    assert len(cd_c["steps"]) > 0
    assert cd_c["steps"][-1]["value"] == c["net_reduction_tco2"]
    assert len(cd_c["parameters_used"]) > 0

    # 3. Forecast
    f = client.post("/api/v1/labs/forecast/supply", headers=pabrik,
                    json={"harvest_area_ha": 500, "month": 5, "year": 2026}).json()
    assert "computation_details" in f
    cd_f = f["computation_details"]
    assert len(cd_f["steps"]) > 0
    assert cd_f["steps"][-1]["value"] == f["predicted_supply_ton"]
    assert len(cd_f["parameters_used"]) > 0

    # 4. Incentive
    i = client.post("/api/v1/labs/incentive/calculate", headers=pabrik,
                    json={"farmer_xp": 120, "quantity_ton": 15, "grade": "A", "on_time": True, "is_peak_season": False}).json()
    assert "computation_details" in i
    cd_i = i["computation_details"]
    assert len(cd_i["steps"]) > 0
    assert cd_i["steps"][-1]["value"] == i["xp_earned"]
    assert len(cd_i["parameters_used"]) > 0

    # 5. Blending
    d = client.get("/api/v1/labs/blend/defaults", headers=pabrik).json()
    spec = d["products"]["biochar_tanah"]["spec"]
    b = client.post("/api/v1/labs/blend/recommend", headers=pabrik,
                    json={"feedstocks": d["feedstocks"], "spec": spec, "target_ton": 50}).json()
    assert "computation_details" in b
    cd_b = b["computation_details"]
    assert len(cd_b["steps"]) > 0
    assert cd_b["steps"][-1]["value"] == b["total_cost"]
    assert len(cd_b["parameters_used"]) > 0

