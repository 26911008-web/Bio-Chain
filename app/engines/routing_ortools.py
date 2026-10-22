"""Engine ⑤b — Alokasi armada & rute hijau dengan Google OR-Tools (CVRP multi-kendaraan).

Dipakai pabrik untuk membagi panen terverifikasi ke beberapa supir sekaligus (`/factory/dispatch/optimize`)
dan sebagai mode `ortools` di `/routes/optimize`. Algoritma TIDAK ditulis sendiri: model & pencarian memakai
solver routing OR-Tools (konstruksi PATH_CHEAPEST_ARC + metaheuristik GUIDED_LOCAL_SEARCH, berbatas waktu).

Fungsi objektif = gram CO₂e. OR-Tools hanya mendukung biaya busur yang tidak bergantung muatan, sehingga
dipakai pendekatan load-aware: muatan saat meninggalkan titik i ≥ q_i (volume yang baru dijemput di i), maka

    biaya(i→j) = d_ij × [f_kosong + (f_penuh − f_kosong) × kg_i / muatan_maks] × EF_campuran   (gram CO₂e)

Ini batas bawah biaya emisi sebenarnya (Pollution-Routing Problem, Bektaş & Laporte 2011) yang mendorong
penjemputan berat di akhir rute (dekat depot). Emisi PERSIS (muatan kumulatif) dihitung ulang setelah solusi
dengan Engine ⑫. Kapasitas = volume bak (m³) per kendaraan — sekam terbatas volume, bukan berat.
Titik yang tidak muat di armada tersedia tidak dipaksakan: dilaporkan sebagai `unassigned` (disjunction).
"""

import math
import time

import numpy as np

from .emission import emissions_from_plan, fuel_factors
from .routing import distance_matrix

try:                                     # dependensi opsional: tanpa OR-Tools, endpoint memberi 503 yang jelas
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    ORTOOLS_AVAILABLE = True
except ImportError:                      # pragma: no cover
    ORTOOLS_AVAILABLE = False

SCALE_M3 = 1000                          # OR-Tools butuh bilangan bulat: m³ → liter
DROP_PENALTY_G = 10**12                  # jauh di atas biaya rute mana pun → titik hanya dibuang bila tidak muat

REFERENCES = [
    "Google OR-Tools 9.15 — Vehicle Routing (CVRP), developers.google.com/optimization/routing/cvrp",
    "Bektaş, T. & Laporte, G. (2011). The Pollution-Routing Problem. Transportation Research Part B 45(8):1232-1250.",
    "Voudouris, C. & Tsang, E. (1999). Guided local search. European Journal of Operational Research 113(2):469-499.",
]


class OrToolsUnavailable(RuntimeError):
    pass


def solve_fleet(depot: dict, stops: list[dict], vehicles: list[dict], time_limit_ms: int = 1000) -> dict:
    """depot {lat, lon}; stops [{id, lat, lon, kg}]; vehicles [{id, m3}]. Mengembalikan rute per kendaraan."""
    if not ORTOOLS_AVAILABLE:
        raise OrToolsUnavailable("Pustaka OR-Tools belum terpasang: pip install ortools")
    if not vehicles:
        raise ValueError("Minimal satu kendaraan/supir.")
    t0 = time.perf_counter()
    rho = P("logistik.bulk_density_kg_m3")
    payload = P("logistik.vehicle_payload_kg")
    f0, f1 = P("logistik.fuel_l_per_km_empty"), P("logistik.fuel_l_per_km_full")
    ef = fuel_factors()["wtw_kg_per_l"]

    lat = np.array([depot["lat"], *(s["lat"] for s in stops)], float)
    lon = np.array([depot["lon"], *(s["lon"] for s in stops)], float)
    D = distance_matrix(lat, lon)
    kg = [0.0] + [float(s["kg"]) for s in stops]
    m3 = [0] + [math.ceil(k / rho * SCALE_M3) for k in kg[1:]]
    # biaya gram CO₂e per km saat meninggalkan node i (lihat docstring)
    g_per_km = [(f0 + (f1 - f0) * min(1.0, k / payload)) * ef * 1000 for k in kg]

    n = len(stops) + 1
    manager = pywrapcp.RoutingIndexManager(n, len(vehicles), 0)
    routing = pywrapcp.RoutingModel(manager)

    def cost_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(round(D[a, b] * g_per_km[a]))

    cost_idx = routing.RegisterTransitCallback(cost_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_idx)

    def demand_cb(i):
        return m3[manager.IndexToNode(i)]

    dem_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    caps = [int(v["m3"] * SCALE_M3) for v in vehicles]
    routing.AddDimensionWithVehicleCapacity(dem_idx, 0, caps, True, "Volume")
    # Dimensi kedua: berat. Sekam padat (dipres/basah) bisa mencapai batas muatan sebelum bak penuh.
    kg_int = [int(round(k)) for k in kg]
    wt_idx = routing.RegisterUnaryTransitCallback(lambda i: kg_int[manager.IndexToNode(i)])
    wcaps = [int(v.get("payload_kg") or payload) for v in vehicles]
    routing.AddDimensionWithVehicleCapacity(wt_idx, 0, wcaps, True, "Weight")
    for node in range(1, n):
        routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY_G)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(max(50, int(time_limit_ms)))
    sol = routing.SolveWithParameters(params)
    if sol is None:
        raise ValueError("OR-Tools tidak menemukan solusi layak.")

    routes, assigned = [], set()
    for v_i, v in enumerate(vehicles):
        idx, seq = routing.Start(v_i), []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node:
                seq.append(node)
            idx = sol.Value(routing.NextVar(idx))
        if not seq:
            continue
        assigned.update(seq)
        path = [0, *seq, 0]
        legs, load = [], 0.0
        for a, b in zip(path, path[1:]):
            load += kg[a]
            legs.append((float(D[a, b]), load))      # muatan kumulatif saat meninggalkan a
        load_kg = sum(kg[i] for i in seq)
        em = emissions_from_plan(legs, load_kg)
        routes.append({
            "vehicle_id": v["id"], "vehicle_m3": v["m3"],
            "stops": [stops[i - 1]["id"] for i in seq],
            "km": round(sum(km for km, _ in legs), 2),
            "load_kg": round(load_kg, 1),
            "load_m3": round(load_kg / rho, 2),
            "utilization_pct": round(100 * load_kg / rho / v["m3"], 1),
            "fuel_l": em["fuel_l"], "co2e_wtw_kg": em["co2e_wtw_kg"],
            "co2e_kg_per_ton_husk": em["co2e_kg_per_ton_husk"],
            "path": [[float(lat[i]), float(lon[i])] for i in path],
        })
    unassigned = [stops[i - 1]["id"] for i in range(1, n) if i not in assigned]
    total_co2 = sum(r["co2e_wtw_kg"] for r in routes)
    total_kg = sum(r["load_kg"] for r in routes)
    return {
        "routes": routes,
        "unassigned": unassigned,
        "summary": {
            "vehicles_used": len(routes), "vehicles_available": len(vehicles),
            "total_km": round(sum(r["km"] for r in routes), 2),
            "total_fuel_l": round(sum(r["fuel_l"] for r in routes), 2),
            "total_co2e_wtw_kg": round(total_co2, 3),
            "co2e_kg_per_ton_husk": round(total_co2 / (total_kg / 1000), 3) if total_kg > 0 else None,
            "total_cost_rp": round(sum(r["km"] for r in routes) * P("logistik.cost_per_km")),
        },
        "computation_details": {
            "solver": "Google OR-Tools RoutingModel (CVRP, kapasitas volume per kendaraan)",
            "first_solution": "PATH_CHEAPEST_ARC", "metaheuristic": "GUIDED_LOCAL_SEARCH",
            "time_limit_ms": int(time_limit_ms),
            "objective": "Minimasi gram CO₂e WTW (biaya busur load-aware: d_ij × BBM(kg_i) × EF)",
            "capacity": "Σ m³ jemput ≤ m³ bak kendaraan (kg ÷ densitas curah)",
            "unassigned_rule": "Titik yang tidak muat di armada tersedia dilepas (disjunction), bukan dipaksakan",
            "objective_value_g": sol.ObjectiveValue() if not unassigned else None,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "references": REFERENCES,
        },
    }
