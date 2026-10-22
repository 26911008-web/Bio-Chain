"""Engine ⑤ — Route Optimizer: CVRP berbatas VOLUME (Clarke-Wright savings + 2-opt).

Sekam padi sangat ringan (densitas curah ~100-120 kg/m3), sehingga bak truk penuh secara
volume jauh sebelum batas tonase tercapai. Kapasitas kendaraan karena itu dihitung dalam m3.
Jarak = haversine x faktor jalan; versi produksi memakai matriks OSRM / pgRouting.
"""

import math

from pydantic import BaseModel, Field

ROAD_FACTOR = 1.3


class RouteRequest(BaseModel):
    mill_ids: list[str] | None = None
    vehicle_m3: float = Field(30, gt=0, description="Volume bak kendaraan (truk engkel bak tinggi ~30 m3)")
    bulk_density_kg_m3: float = Field(110, gt=0)
    cost_per_km: float = Field(4_000, ge=0, description="Rp/km (BBM + sopir + penyusutan)")


def road_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * ROAD_FACTOR


def _route_km(depot, route, pts) -> float:
    path = [depot] + [pts[i] for i in route] + [depot]
    return sum(road_km(path[k], path[k + 1]) for k in range(len(path) - 1))


def _two_opt(depot, route, pts):
    best, improved = route[:], True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                if _route_km(depot, cand, pts) + 1e-9 < _route_km(depot, best, pts):
                    best, improved = cand, True
    return best


def plan_routes(depot: dict, mills: list[dict], req: RouteRequest) -> dict:
    cap = req.vehicle_m3
    depot_pt = (depot["lat"], depot["lon"])

    # Pecah penggilingan yang volumenya > kapasitas: trip penuh langsung + sisa ikut savings.
    stops, direct_trips = [], []
    for m in mills:
        vol = m["stock_ton"] * 1000 / req.bulk_density_kg_m3
        while vol > cap:
            direct_trips.append({"mill": m, "m3": cap})
            vol -= cap
        if vol > 1e-6:
            stops.append({"mill": m, "m3": vol})

    pts = [(s["mill"]["lat"], s["mill"]["lon"]) for s in stops]
    d0 = [road_km(depot_pt, p) for p in pts]
    routes = {i: [i] for i in range(len(stops))}
    load = {i: stops[i]["m3"] for i in range(len(stops))}
    owner = {i: i for i in range(len(stops))}

    savings = sorted(
        ((d0[i] + d0[j] - road_km(pts[i], pts[j]), i, j)
         for i in range(len(stops)) for j in range(i + 1, len(stops))),
        reverse=True,
    )
    for s, i, j in savings:
        ri, rj = owner[i], owner[j]
        if s <= 0 or ri == rj or load[ri] + load[rj] > cap:
            continue
        a, b = routes[ri], routes[rj]
        if a[-1] == i and b[0] == j:
            merged = a + b
        elif a[0] == i and b[-1] == j:
            merged = b + a
        elif a[-1] == i and b[-1] == j:
            merged = a + b[::-1]
        elif a[0] == i and b[0] == j:
            merged = a[::-1] + b
        else:
            continue  # i atau j bukan ujung rute
        routes[ri], load[ri] = merged, load[ri] + load[rj]
        for n in b:
            owner[n] = ri
        del routes[rj], load[rj]

    result, total_km = [], 0.0
    for rid, r in routes.items():
        r = _two_opt(depot_pt, r, pts)
        km = _route_km(depot_pt, r, pts)
        total_km += km
        result.append(_route_out(depot, [stops[i] for i in r], km, req))
    for t in direct_trips:
        km = 2 * road_km(depot_pt, (t["mill"]["lat"], t["mill"]["lon"]))
        total_km += km
        result.append(_route_out(depot, [t], km, req))

    total_ton = sum(m["stock_ton"] for m in mills)
    # Baseline: tiap penggilingan dijemput terpisah (pola manual saat ini).
    baseline_km = sum(
        2 * road_km(depot_pt, (m["lat"], m["lon"])) * math.ceil(m["stock_ton"] * 1000 / req.bulk_density_kg_m3 / cap)
        for m in mills
    )
    return {
        "routes": sorted(result, key=lambda r: -r["load_m3"]),
        "summary": {
            "mills": len(mills),
            "total_ton": round(total_ton, 2),
            "vehicles_trips": len(result),
            "total_km": round(total_km, 1),
            "total_cost": round(total_km * req.cost_per_km),
            "cost_per_ton": round(total_km * req.cost_per_km / total_ton) if total_ton else 0,
            "baseline_km": round(baseline_km, 1),
            "saving_pct": round(100 * (1 - total_km / baseline_km), 1) if baseline_km else 0,
            "max_ton_per_trip": round(cap * req.bulk_density_kg_m3 / 1000, 2),
        },
    }


def _route_out(depot, route_stops, km, req):
    m3 = sum(s["m3"] for s in route_stops)
    return {
        "stops": [{"id": s["mill"]["id"], "name": s["mill"]["name"], "m3": round(s["m3"], 1),
                   "ton": round(s["m3"] * req.bulk_density_kg_m3 / 1000, 2)} for s in route_stops],
        "path": [[depot["lat"], depot["lon"]]] + [[s["mill"]["lat"], s["mill"]["lon"]] for s in route_stops]
                + [[depot["lat"], depot["lon"]]],
        "km": round(km, 1),
        "load_m3": round(m3, 1),
        "load_ton": round(m3 * req.bulk_density_kg_m3 / 1000, 2),
        "utilization_pct": round(100 * m3 / req.vehicle_m3, 1),
    }
