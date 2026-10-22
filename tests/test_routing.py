"""Tes Engine ⑤ Route Optimizer: kebenaran (vs brute force), invarian, edge case, API, dan latensi.

Benchmark tabel:  py -m tests.test_routing
"""

import itertools
import math
import random
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engines.routing import (EXACT_HARD_MAX, distance_matrix, lower_bound_km, plan_routes, road_km,
                                 route_km, solve_exact, solve_heuristic)
from app.main import app
from app.routers.routing import get_supply_network
from app.schemas.routing import RouteRequest, RouteResponse

DEPOT = {"id": "plant", "name": "Pabrik uji", "lat": -7.745, "lon": 110.362}
LATENCY_SLO_MS = 500


def make_mills(n: int, seed: int = 0, ton=(0.3, 1.8)) -> list[dict]:
    r = random.Random(seed)
    return [{"id": f"T{i:04d}", "name": f"Mock #{i}", "lat": -7.7 + r.uniform(-0.15, 0.15),
             "lon": 110.45 + r.uniform(-0.25, 0.25), "stock_ton": round(r.uniform(*ton), 1)} for i in range(n)]


def instance(n: int, seed: int = 0):
    """(D, q) acak: depot di indeks 0, volume m3 per titik."""
    r = np.random.default_rng(seed)
    lat = np.r_[DEPOT["lat"], -7.7 + r.uniform(-0.15, 0.15, n)]
    lon = np.r_[DEPOT["lon"], 110.45 + r.uniform(-0.25, 0.25, n)]
    return distance_matrix(lat, lon), r.uniform(3, 16, n)


def brute_force_cvrp(D, q, cap) -> float:
    """Ground truth untuk n kecil: semua partisi himpunan × semua permutasi tiap blok."""
    def partitions(items):
        if not items:
            yield []
            return
        first, rest = items[0], items[1:]
        for p in partitions(rest):
            for k in range(len(p)):
                yield p[:k] + [[first] + p[k]] + p[k + 1:]
            yield [[first]] + p

    def tsp(block):
        return min(route_km(list(perm), D) for perm in itertools.permutations(block))

    best = math.inf
    for p in partitions(list(range(1, len(q) + 1))):
        if all(q[np.array(b) - 1].sum() <= cap + 1e-9 for b in p):
            best = min(best, sum(tsp(b) for b in p))
    return best


def assert_valid_solution(routes, q, cap):
    visited = sorted(u for r in routes for u in r)
    assert visited == list(range(1, len(q) + 1)), "setiap titik dijemput tepat sekali"
    assert all(q[np.array(r) - 1].sum() <= cap + 1e-6 for r in routes), "kapasitas volume dilanggar"


@pytest.fixture
def mock_network():
    return DEPOT, make_mills(40, seed=7)


@pytest.fixture
def client(mock_network):
    app.dependency_overrides[get_supply_network] = lambda: mock_network
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- unit: matematika
def test_distance_matrix_matches_scalar_haversine():
    mills = make_mills(15, seed=3)
    pts = [(DEPOT["lat"], DEPOT["lon"])] + [(m["lat"], m["lon"]) for m in mills]
    D = distance_matrix(*np.array(pts).T)
    ref = np.array([[road_km(a, b) for b in pts] for a in pts])
    np.testing.assert_allclose(D, ref, atol=1e-6)          # < 1 mm; formulasi hasil-kali-luar
    np.testing.assert_allclose(D, D.T)
    assert np.all(np.diag(D) == 0)


@pytest.mark.parametrize("seed", range(4))
def test_exact_equals_brute_force(seed):
    D, q = instance(6, seed)
    routes, stats = solve_exact(D, q, cap=30)
    assert_valid_solution(routes, q, 30)
    opt = sum(route_km(r, D) for r in routes)
    assert opt == pytest.approx(brute_force_cvrp(D, q, 30), rel=1e-9)
    assert stats["optimum_km"] == pytest.approx(opt, abs=1e-3)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("cap", [30, 60])
def test_heuristic_close_to_optimum_and_bounds_hold(seed, cap):
    D, q = instance(10, seed)
    opt = sum(route_km(r, D) for r in solve_exact(D, q, cap)[0])
    routes, _ = solve_heuristic(D, q, cap)
    assert_valid_solution(routes, q, cap)
    heur = sum(route_km(r, D) for r in routes)
    assert lower_bound_km(D, q, cap) <= opt + 1e-9 <= heur + 2e-9
    assert heur <= opt * 1.02, f"gap heuristik {100 * (heur / opt - 1):.2f}% > 2%"


@pytest.mark.parametrize("n,cap", [(150, 30), (150, 120), (400, 30)])
def test_heuristic_invariants_at_scale(n, cap):
    D, q = instance(n, seed=n)
    routes, stats = solve_heuristic(D, q, cap, time_budget_ms=1_000)
    assert_valid_solution(routes, q, cap)
    assert sum(route_km(r, D) for r in routes) <= stats["construction_km"] + 1e-6, "local search tidak boleh memperburuk"


def test_exact_rejects_oversized_instance():
    D, q = instance(EXACT_HARD_MAX + 1)
    with pytest.raises(ValueError):
        solve_exact(D, q, 30)


# ---------------------------------------------------------------- unit: orkestrasi & edge case
def test_oversized_mill_becomes_direct_full_trips():
    mill = {"id": "BIG", "name": "Besar", "lat": -7.70, "lon": 110.40, "stock_ton": 8.0}   # 72.7 m3
    out = plan_routes(DEPOT, [mill], RouteRequest(vehicle_m3=30))
    assert [r["load_m3"] for r in out["routes"]] == [30.0, 30.0, 12.7]
    assert out["computation_details"]["problem"]["direct_full_trips"] == 2
    assert out["summary"]["total_km"] == pytest.approx(out["summary"]["baseline_km"], abs=0.2)


def test_exactly_full_mill_is_single_trip():
    mill = {"id": "F", "name": "Pas", "lat": -7.70, "lon": 110.40, "stock_ton": 3.3}       # 30 m3 tepat
    out = plan_routes(DEPOT, [mill], RouteRequest(vehicle_m3=30))
    assert len(out["routes"]) == 1


def test_zero_stock_has_no_division_by_zero():
    mills = [dict(m, stock_ton=0) for m in make_mills(5)]
    out = plan_routes(DEPOT, mills, RouteRequest())
    assert out["routes"] == []
    assert out["summary"]["cost_per_ton"] == 0 and out["summary"]["saving_pct"] == 0
    assert out["computation_details"]["mode_used"] == "trivial"


def test_duplicate_coordinates_are_handled():
    m = make_mills(1)[0]
    mills = [dict(m, id=f"D{i}") for i in range(6)]
    out = plan_routes(DEPOT, mills, RouteRequest(mode="heuristic"))
    assert sum(len(r["stops"]) for r in out["routes"]) == 6


@pytest.mark.parametrize("n,expected", [(EXACT_HARD_MAX - 2, "exact"), (40, "heuristic")])
def test_auto_mode_selection(n, expected):
    out = plan_routes(DEPOT, make_mills(n, seed=1), RouteRequest(mode="auto"))
    cd = out["computation_details"]
    assert cd["mode_used"] == expected
    assert cd["quality"]["proven_optimal"] is (expected == "exact")
    assert cd["quality"]["lower_bound_km"] <= cd["quality"]["objective_km"] + 1e-6


def test_step_timings_are_attributed_per_phase():
    out = plan_routes(DEPOT, make_mills(60, seed=2), RouteRequest(mode="heuristic", time_budget_ms=100))
    cd = out["computation_details"]
    steps = {s["name"].split(":")[0]: s["elapsed_ms"] for s in cd["steps"]}
    assert steps["Iterated local search"] > steps["Konstruksi Clarke-Wright savings (granular)"]
    assert sum(steps.values()) <= cd["total_elapsed_ms"] + 1


def test_single_point_heuristic():
    out = plan_routes(DEPOT, make_mills(1), RouteRequest(mode="heuristic"))
    assert len(out["routes"]) == 1 and out["computation_details"]["mode_used"] == "heuristic"


# ---------------------------------------------------------------- API
def test_api_returns_explainable_payload(client, pabrik):
    r = client.post("/api/v1/labs/routes/optimize", headers=pabrik, json={"vehicle_m3": 30})
    assert r.status_code == 200
    body = RouteResponse.model_validate(r.json())
    steps = body.computation_details.steps
    assert [s.step for s in steps] == list(range(1, len(steps) + 1))
    assert all(s.explanation and s.elapsed_ms >= 0 for s in steps)
    assert body.summary.total_km < body.summary.baseline_km
    assert all(rt.load_m3 <= 30 + 1e-6 for rt in body.routes)
    served = sum(s.ton for rt in body.routes for s in rt.stops)
    assert served == pytest.approx(body.summary.total_ton, abs=0.15)


def test_api_filters_mill_ids(client, mock_network, pabrik):
    ids = [m["id"] for m in mock_network[1][:4]]
    body = client.post("/api/v1/labs/routes/optimize", headers=pabrik, json={"mill_ids": ids}).json()
    assert {s["id"] for rt in body["routes"] for s in rt["stops"]} == set(ids)
    assert body["computation_details"]["mode_used"] == "exact"


def test_api_exact_over_limit_is_422(client, pabrik):
    r = client.post("/api/v1/labs/routes/optimize", headers=pabrik, json={"mode": "exact"})
    assert r.status_code == 422 and "exact" in r.json()["detail"]


def test_api_unknown_mill_ids_is_422(client, pabrik):
    assert client.post("/api/v1/labs/routes/optimize", headers=pabrik, json={"mill_ids": ["NOPE"]}).status_code == 422


@pytest.mark.parametrize("payload", [{"vehicle_m3": 0}, {"bulk_density_kg_m3": -1}, {"mode": "magic"},
                                     {"time_budget_ms": 0}])
def test_api_rejects_invalid_input(client, pabrik, payload):
    assert client.post("/api/v1/labs/routes/optimize", headers=pabrik, json=payload).status_code == 422


# ---------------------------------------------------------------- benchmark (SLO latensi)
def _latency_ms(n: int, cap: float, runs: int = 7) -> tuple[float, float]:
    """(median, terburuk) dari beberapa run setelah pemanasan. SLO dinilai pada median:
    run terburuk tunggal di mesin bersama mencerminkan noise penjadwalan OS, bukan biaya algoritma."""
    mills, req = make_mills(n, seed=n), RouteRequest(vehicle_m3=cap)
    plan_routes(DEPOT, mills, req)  # pemanasan (warmup)
    samples = []
    for _ in range(runs):
        t = time.perf_counter()
        plan_routes(DEPOT, mills, req)
        samples.append((time.perf_counter() - t) * 1000)
    samples.sort()
    return samples[len(samples) // 2], samples[-1]


@pytest.mark.perf
@pytest.mark.parametrize("n,cap", [(10, 30), (12, 30), (100, 30), (500, 30), (1000, 30), (1000, 300)])
def test_latency_slo(n, cap):
    med, worst = _latency_ms(n, cap)
    print(f"\n  n={n:>5} cap={cap:>4} m3  median = {med:7.1f} ms  terburuk = {worst:7.1f} ms")
    assert med < LATENCY_SLO_MS


if __name__ == "__main__":
    print(f"{'n':>6} {'cap':>5} {'mode':>10} {'worst ms':>9} {'km':>10} {'trip':>5} {'gap≤%':>6}")
    for n, cap in [(10, 30), (12, 30), (36, 30), (100, 30), (200, 300), (500, 30), (1000, 30), (1000, 300)]:
        out = plan_routes(DEPOT, make_mills(n, seed=n), RouteRequest(vehicle_m3=cap))
        cd = out["computation_details"]
        print(f"{n:>6} {cap:>5} {cd['mode_used']:>10} {_latency_ms(n, cap)[1]:>9.1f} "
              f"{out['summary']['total_km']:>10.1f} {out['summary']['vehicles_trips']:>5} "
              f"{cd['quality']['gap_upper_bound_pct']:>6.1f}")
