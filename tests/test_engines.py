import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_quality_good_husk_is_grade_a(client):
    r = client.post("/quality/score", json={"moisture": 11, "ash": 18, "volatile_matter": 66,
                                            "fixed_carbon": 16, "contamination": 1.5}).json()
    assert r["grade"] == "A"
    assert 37 <= r["pred_biochar_yield_pct_db"] <= 57


def test_quality_wet_husk_rejected(client):
    r = client.post("/quality/score", json={"moisture": 30, "ash": 18, "volatile_matter": 66,
                                            "fixed_carbon": 16}).json()
    assert r["grade"] == "TOLAK"


def test_blend_meets_spec(client):
    d = client.get("/blend/defaults").json()
    spec = d["products"]["biochar_tanah"]["spec"]
    r = client.post("/blend/recommend", json={"feedstocks": d["feedstocks"], "spec": spec, "target_ton": 50}).json()
    assert r["feasible"]
    assert sum(c["ton"] for c in r["composition"]) == 50
    assert r["blend_properties"]["ash"] <= spec["ash_max"] + 1e-6
    assert r["blend_properties"]["fixed_carbon"] >= spec["fixed_carbon_min"] - 1e-6


def test_blend_infeasible_reports_blocking_constraint(client):
    d = client.get("/blend/defaults").json()
    spec = d["products"]["quick_light_charcoal"]["spec"]
    r = client.post("/blend/recommend", json={"feedstocks": d["feedstocks"], "spec": spec, "target_ton": 100}).json()
    assert not r["feasible"] and r["relax_one_of"]


def test_routes_respect_volume_capacity_and_beat_baseline(client):
    r = client.post("/routes/optimize", json={"vehicle_m3": 30}).json()
    assert all(rt["load_m3"] <= 30 + 1e-6 for rt in r["routes"])
    served = sum(s["ton"] for rt in r["routes"] for s in rt["stops"])
    assert abs(served - r["summary"]["total_ton"]) < 0.1
    assert r["summary"]["total_km"] < r["summary"]["baseline_km"]

