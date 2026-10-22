"""Engine ⑤ — Route Optimizer: CVRP berbatas VOLUME.

Sekam padi sangat ringan (densitas curah ~100-120 kg/m3), sehingga bak truk penuh secara
volume jauh sebelum batas tonase tercapai. Kapasitas kendaraan karena itu dihitung dalam m3.
Jarak = haversine x faktor jalan; versi produksi memakai matriks OSRM / pgRouting.

Dua solver, dipilih otomatis berdasarkan ukuran masalah (lihat `plan_routes`):
- exact     : Held-Karp per subset + DP set-partitioning, O(2^n·n² + 3^n). Optimal terbukti, n ≤ 12.
- heuristic : Clarke-Wright savings granular (k-tetangga terdekat) + local search
              (relocate, swap, 2-opt dengan evaluasi delta O(1)) + iterated local search
              ruin & recreate, seluruhnya di bawah anggaran waktu.
Modul ini murni komputasi: tidak bergantung pada FastAPI/DB.
"""

import math
import random
import time

import numpy as np

from ..params import P
from ..schemas.routing import RouteRequest

ROAD_FACTOR = 1.3                # DEFAULT; nilai aktif: P("logistik.road_factor")
EARTH_RADIUS_KM = 6371.0
EXACT_AUTO_MAX = 10      # mode auto: exact sampai sekian titik (≈ <50 ms)
EXACT_HARD_MAX = 12      # mode exact eksplisit: di atas ini 3^n meledak (> 500 ms)
NEIGHBORS_SAVINGS = 100  # granularitas konstruksi: pasangan savings hanya antar k-tetangga terdekat
NEIGHBORS_LS = 20        # granularitas local search (Toth & Vigo 2003)
ILS_MAX_ITERS = 400      # batas iterasi ruin & recreate (selain anggaran waktu)
ILS_MAX_RUIN = 10        # maksimum titik yang dicabut per iterasi
ILS_BLINK = 0.01         # peluang melewati posisi sisip (SISR "blinks")
ILS_T0 = 0.02            # ambang awal threshold accepting (2% dari km terbaik)
EPS = 1e-9

REFERENCES = [
    "Clarke, G. & Wright, J.W. (1964). Scheduling of vehicles from a central depot to a number of "
    "delivery points. Operations Research 12(4):568-581.",
    "Toth, P. & Vigo, D. (2003). The granular tabu search and its application to the vehicle-routing "
    "problem. INFORMS Journal on Computing 15(4):333-346.",
    "Vidal, T. (2022). Hybrid genetic search for the CVRP: Open-source implementation and SWAP* "
    "neighborhood. Computers & Operations Research 140:105643.",
    "Wouda, N.A., Lan, L. & Kool, W. (2024). PyVRP: A high-performance VRP solver package. "
    "INFORMS Journal on Computing 36(4):943-955. doi:10.1287/ijoc.2023.0055",
    "Costa, L., Contardo, C. & Desaulniers, G. (2019). Exact branch-price-and-cut algorithms for "
    "vehicle routing. Transportation Science 53(4):946-985.",
    "Christiaens, J. & Vanden Berghe, G. (2020). Slack induction by string removals for vehicle routing "
    "problems. Transportation Science 54(2):417-433.",
    "Haimovich, M. & Rinnooy Kan, A.H.G. (1985). Bounds and heuristics for capacitated routing "
    "problems. Mathematics of Operations Research 10(4):527-542.",
]

__all__ = ["RouteRequest", "SolverLimitError", "plan_routes", "road_km", "distance_matrix",
           "solve_exact", "solve_heuristic", "lower_bound_km", "route_km"]


class SolverLimitError(ValueError):
    """Permintaan melebihi batas komputasi yang dijamin (mis. mode exact untuk n terlalu besar)."""


# ---------------------------------------------------------------- jarak
def road_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h)) * P("logistik.road_factor")


def distance_matrix(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Matriks jarak jalan (n×n), haversine tanpa trigonometri per pasangan.

    sin²(Δ/2) = (1 − cos a·cos b − sin a·sin b)/2, sehingga
    h = ½·(1 − sinφᵢ·sinφⱼ − cosφᵢ·cosφⱼ·(cosλᵢ·cosλⱼ + sinλᵢ·sinλⱼ)): trigonometri hanya O(n),
    sisanya hasil kali luar (BLAS). Galat pembatalan < 1e-7 km pada jarak 1 km.
    """
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    sp, cp, sl, cl = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    cos_dlon = np.outer(cl, cl) + np.outer(sl, sl)
    h = 0.5 * (1.0 - np.outer(sp, sp) - np.outer(cp, cp) * cos_dlon)
    np.clip(h, 0.0, 1.0, out=h)
    D = (2 * EARTH_RADIUS_KM * P("logistik.road_factor")) * np.arcsin(np.sqrt(h))
    np.fill_diagonal(D, 0.0)
    return D


def route_km(route: list[int], D: np.ndarray) -> float:
    """Panjang rute depot(0) → route → depot(0)."""
    if not route:
        return 0.0
    p = np.fromiter((0, *route, 0), int)
    return float(D[p[:-1], p[1:]].sum())


def lower_bound_km(D: np.ndarray, q: np.ndarray, cap: float) -> float:
    """Batas bawah CVRP yang valid untuk jarak metrik, O(n²):
    - radial (Haimovich & Rinnooy Kan 1985): rute berisi S ≥ 2·max d0 ≥ 2·Σ q·d0 / Q;
    - MST: gabungan semua rute (lewat depot) memuat spanning tree seluruh titik.
    """
    if len(q) == 0:
        return 0.0
    d0 = D[0, 1:]
    radial = max(2 * float(q @ d0) / cap, 2 * float(d0.max()))
    return max(radial, mst_weight(D))


def mst_weight(D: np.ndarray) -> float:
    """Prim padat: n iterasi × O(n) operasi vektor = O(n²), tanpa struktur heap."""
    n = len(D)
    in_tree = np.zeros(n, dtype=bool)
    in_tree[0] = True
    dist = D[0].copy()
    dist[0] = np.inf
    total = 0.0
    for _ in range(n - 1):
        j = int(dist.argmin())
        total += float(dist[j])
        in_tree[j] = True
        dist = np.minimum(dist, D[j])
        dist[in_tree] = np.inf
    return total


# ---------------------------------------------------------------- exact
def solve_exact(D: np.ndarray, q: np.ndarray, cap: float) -> tuple[list[list[int]], dict]:
    """Solusi optimal: Held-Karp untuk biaya TSP tiap subset layak, lalu DP set-partitioning.

    Node 1..n di D adalah titik jemput, 0 adalah depot. Mengembalikan rute (indeks 1-based).
    """
    n = len(q)
    if n > EXACT_HARD_MAX:
        raise SolverLimitError(f"Mode exact dibatasi {EXACT_HARD_MAX} titik (diminta {n}).")
    full = 1 << n
    bits = ((np.arange(full)[:, None] >> np.arange(n)) & 1).astype(bool)
    feasible = bits @ q <= cap + EPS
    Dn, d0 = D[1:, 1:], D[0, 1:]

    # Held-Karp maju: dp[mask, j] = jalur termurah dari depot melewati mask, berakhir di j.
    dp = np.full((full, n), np.inf)
    parent = np.full((full, n), -1, dtype=np.int64)
    dp[1 << np.arange(n), np.arange(n)] = d0
    idx = np.arange(n)
    for mask in range(1, full):
        if not feasible[mask]:
            continue  # q > 0 ⇒ superset dari subset tak layak juga tak layak
        cand = dp[mask][:, None] + Dn                     # (dari i) → (ke j)
        arg = cand.argmin(axis=0)
        best = cand[arg, idx]
        js = idx[~bits[mask] & np.isfinite(best)]
        if js.size == 0:
            continue
        nm = mask | (1 << js)
        ok = feasible[nm] & (best[js] < dp[nm, js])
        dp[nm[ok], js[ok]] = best[js[ok]]
        parent[nm[ok], js[ok]] = arg[js[ok]]
    closed = dp + d0[None, :]
    tour = np.where(feasible, closed.min(axis=1), np.inf)
    tour[0] = 0.0

    # DP partisi: best[mask] = min_{S ∋ bit terendah, S ⊆ mask, S layak} tour[S] + best[mask \ S].
    feas_masks = np.flatnonzero(feasible)[1:]
    by_low = [feas_masks[(feas_masks & (1 << b)) != 0] for b in range(n)]
    by_low = [m[(m & ((1 << b) - 1)) == 0] for b, m in enumerate(by_low)]   # b = bit terendah
    best = np.full(full, np.inf)
    best[0] = 0.0
    choice = np.zeros(full, dtype=np.int64)
    for mask in range(1, full):
        low = (mask & -mask).bit_length() - 1
        cands = by_low[low]
        cands = cands[(cands & ~mask) == 0]
        vals = tour[cands] + best[mask ^ cands]
        k = int(vals.argmin())
        best[mask], choice[mask] = vals[k], cands[k]

    routes, mask = [], full - 1
    while mask:
        S = int(choice[mask])
        j = int(closed[S].argmin())
        path, m = [], S
        while j >= 0:
            path.append(j + 1)
            j, m = int(parent[m, j]), m ^ (1 << j)
        routes.append(path[::-1])
        mask ^= S
    stats = {"subsets_total": full, "subsets_feasible": int(feasible.sum()), "optimum_km": round(float(best[-1]), 3)}
    return routes, stats


# ---------------------------------------------------------------- heuristic
def _neighbors(D: np.ndarray, k: int) -> np.ndarray:
    """k tetangga terdekat tiap titik (indeks 1-based); O(n²) via argpartition."""
    Dn = D[1:, 1:].copy()
    np.fill_diagonal(Dn, np.inf)
    k = min(k, len(Dn) - 1)
    nb = np.argpartition(Dn, k - 1, axis=1)[:, :k]
    order = np.take_along_axis(Dn, nb, axis=1).argsort(axis=1)
    return np.take_along_axis(nb, order, axis=1) + 1


def _savings(D: np.ndarray, q: np.ndarray, cap: float, nb: np.ndarray) -> tuple[list[list[int]], int]:
    """Clarke-Wright paralel pada daftar savings granular: O(n·k log(n·k))."""
    n = len(q)
    i = np.repeat(np.arange(1, n + 1), nb.shape[1])
    j = nb.ravel()
    a, b = np.minimum(i, j), np.maximum(i, j)
    pairs = np.unique(a * (n + 1) + b)
    a, b = pairs // (n + 1), pairs % (n + 1)
    s = D[0, a] + D[0, b] - D[a, b]
    keep = s > EPS
    a, b, s = a[keep], b[keep], s[keep]
    order = np.argsort(-s, kind="stable")

    routes = {u: [u] for u in range(1, n + 1)}
    load = {u: float(q[u - 1]) for u in range(1, n + 1)}
    owner = list(range(n + 1))
    merges = 0
    for u, v in zip(a[order].tolist(), b[order].tolist()):
        ru, rv = owner[u], owner[v]
        if ru == rv or load[ru] + load[rv] > cap + EPS:
            continue
        x, y = routes[ru], routes[rv]
        if x[-1] == u and y[0] == v:
            merged = x + y
        elif x[0] == u and y[-1] == v:
            merged = y + x
        elif x[-1] == u and y[-1] == v:
            merged = x + y[::-1]
        elif x[0] == u and y[0] == v:
            merged = x[::-1] + y
        else:
            continue  # u atau v bukan ujung rute
        routes[ru], load[ru] = merged, load[ru] + load[rv]
        for w in y:
            owner[w] = ru
        del routes[rv], load[rv]
        merges += 1
    return list(routes.values()), merges


def _two_opt(route: list[int], D: np.ndarray) -> tuple[list[int], int]:
    """2-opt intra-rute dengan evaluasi delta O(1) per kandidat, divektorisasi per i: O(L²)/pass."""
    if len(route) < 3:
        return route, 0
    p = np.fromiter((0, *route, 0), int)
    moves, improved = 0, True
    while improved:
        improved = False
        for i in range(len(p) - 3):
            js = np.arange(i + 2, len(p) - 1)
            a, b, c, d = p[i], p[i + 1], p[js], p[js + 1]
            delta = D[a, c] + D[b, d] - D[a, b] - D[c, d]
            m = int(delta.argmin())
            if delta[m] < -EPS:
                j = int(js[m])
                p[i + 1:j + 1] = p[i + 1:j + 1][::-1].copy()
                moves += 1
                improved = True
    return p[1:-1].tolist(), moves


def _local_search(routes: list[list[int]], D: np.ndarray, q: np.ndarray, cap: float,
                  nb: np.ndarray, deadline: float, Dl: list | None = None) -> tuple[list[list[int]], dict]:
    """Relocate & swap antar-rute (dibatasi k-tetangga) + 2-opt, first-improvement, hingga konvergen
    atau anggaran waktu habis. Tiap pass O(n·k) evaluasi delta."""
    n = len(q)
    route_of = np.zeros(n + 1, dtype=np.int64)
    for r, rt in enumerate(routes):
        route_of[rt] = r
    load = [float(q[np.asarray(rt) - 1].sum()) for rt in routes]
    stats = {"passes": 0, "relocate": 0, "swap": 0, "two_opt": 0, "stopped_by": "converged"}
    dirty = set(range(len(routes)))
    Dl = D.tolist() if Dl is None else Dl        # akses skalar list jauh lebih cepat dari ndarray
    ql = [0.0, *q.tolist()]
    nbl = nb.tolist()

    def ends(rt, p):
        return (rt[p - 1] if p > 0 else 0), (rt[p + 1] if p < len(rt) - 1 else 0)

    while True:
        for r in dirty:
            if routes[r]:
                routes[r], m = _two_opt(routes[r], D)
                stats["two_opt"] += m
        dirty = set()
        stats["passes"] += 1
        for u in range(1, n + 1):
            if time.perf_counter() > deadline:
                stats["stopped_by"] = "time_budget"
                return [r for r in routes if r], stats
            ru = int(route_of[u])
            rt_u = routes[ru]
            pu = rt_u.index(u)
            pr, nx = ends(rt_u, pu)
            rem_gain = Dl[pr][u] + Dl[u][nx] - Dl[pr][nx]
            best_gain, best_move = EPS, None
            for v in nbl[u - 1]:
                rv = int(route_of[v])
                if rv == ru:
                    continue
                rt_v = routes[rv]
                pv = rt_v.index(v)
                vp, vn = ends(rt_v, pv)
                if load[rv] + ql[u] <= cap + EPS:                       # relocate u ke sebelah v
                    for x, y, at in ((vp, v, pv), (v, vn, pv + 1)):
                        g = rem_gain - (Dl[x][u] + Dl[u][y] - Dl[x][y])
                        if g > best_gain:
                            best_gain, best_move = g, ("relocate", rv, at, None)
                if (load[ru] - ql[u] + ql[v] <= cap + EPS and load[rv] - ql[v] + ql[u] <= cap + EPS
                        and v not in (pr, nx)):                          # swap u ↔ v
                    g = (Dl[pr][u] + Dl[u][nx] - Dl[pr][v] - Dl[v][nx]
                         + Dl[vp][v] + Dl[v][vn] - Dl[vp][u] - Dl[u][vn])
                    if g > best_gain:
                        best_gain, best_move = g, ("swap", rv, pv, v)
            if best_move is None:
                continue
            kind, rv, at, v = best_move
            if kind == "relocate":
                rt_u.pop(pu)
                routes[rv].insert(at, u)
                route_of[u] = rv
                load[ru] -= ql[u]
                load[rv] += ql[u]
            else:
                rt_u[pu], routes[rv][at] = v, u
                route_of[u], route_of[v] = rv, ru
                load[ru] += ql[v] - ql[u]
                load[rv] += ql[u] - ql[v]
            stats[kind] += 1
            dirty |= {ru, rv}
        if not dirty:
            return [r for r in routes if r], stats


def _ruin_recreate(routes: list[list[int]], Dl: list, ql: list, cap: float, nbl: list,
                   rng: random.Random, max_ruin: int) -> list[list[int]]:
    """Ruin: cabut satu titik acak + tetangga terdekatnya (string removal ala SISR).
    Recreate: cheapest insertion granular (hanya rute milik tetangga), atau rute baru bila tak muat."""
    seed = rng.randrange(1, len(ql))
    removed = {seed, *nbl[seed - 1][:rng.randint(1, max_ruin - 1)]}
    routes = [[u for u in r if u not in removed] for r in routes]
    routes = [r for r in routes if r]
    route_of = {u: i for i, r in enumerate(routes) for u in r}
    load = [sum(ql[u] for u in r) for r in routes]
    order = list(removed)                                       # urutan sisip acak antar-iterasi (SISR)
    rng.shuffle(order)
    sort_key = rng.choice((None, lambda u: -Dl[0][u], lambda u: Dl[0][u], lambda u: -ql[u]))
    if sort_key:
        order.sort(key=sort_key)
    for u in order:
        best_cost, best_at = 2 * Dl[0][u], None                 # opsi rute baru
        for ri in sorted({route_of[v] for v in nbl[u - 1] if v in route_of}):
            if load[ri] + ql[u] > cap + EPS:
                continue
            p = [0, *routes[ri], 0]
            for k in range(len(p) - 1):
                if rng.random() < ILS_BLINK:                    # "blink": sesekali lewati posisi
                    continue
                c = Dl[p[k]][u] + Dl[u][p[k + 1]] - Dl[p[k]][p[k + 1]]
                if c < best_cost:
                    best_cost, best_at = c, (ri, k)
        if best_at is None:
            routes.append([u])
            load.append(ql[u])
            route_of[u] = len(routes) - 1
        else:
            ri, k = best_at
            routes[ri].insert(k, u)
            load[ri] += ql[u]
            route_of[u] = ri
    return routes


def solve_heuristic(D: np.ndarray, q: np.ndarray, cap: float, time_budget_ms: int = 250,
                    k_savings: int = NEIGHBORS_SAVINGS, k_ls: int = NEIGHBORS_LS,
                    max_ils_iters: int = ILS_MAX_ITERS, seed: int = 0) -> tuple[list[list[int]], dict]:
    """Granular Clarke-Wright → local search → iterated local search (ruin & recreate) sampai anggaran
    waktu atau batas iterasi habis. Anggaran mencakup seluruh tahap. Deterministik untuk `seed` tetap
    selama anggaran waktu tidak memotong iterasi."""
    t0 = time.perf_counter()
    deadline = t0 + time_budget_ms / 1000
    n = len(q)
    if n == 1:
        return [[1]], {"merges": 0, "neighbors_k_savings": 0, "neighbors_k_ls": 0, "construction_km": route_km([1], D),
                       "local_search": {"passes": 0, "relocate": 0, "swap": 0, "two_opt": 0, "stopped_by": "converged"},
                       "ils": {"iterations": 0, "improvements": 0, "stopped_by": "trivial"}}
    # Daftar savings granular adaptif: n besar → k lebih kecil agar konstruksi (tidak dapat diinterupsi)
    # muat dalam anggaran waktu; ILS menutup selisih kualitasnya.
    k_savings = min(k_savings, max(60, 60_000 // max(n, 1)))
    nb_s = _neighbors(D, k_savings)
    routes, merges = _savings(D, q, cap, nb_s)
    construction_km = sum(route_km(r, D) for r in routes)
    nb = nb_s[:, :k_ls]                     # tetangga sudah terurut jarak → cukup dipotong
    Dl, ql, nbl = D.tolist(), [0.0, *q.tolist()], nb.tolist()
    t1 = time.perf_counter()
    routes, ls = _local_search(routes, D, q, cap, nb, deadline, Dl)
    ls_km = best_km = sum(route_km(r, D) for r in routes)
    t2 = time.perf_counter()
    ls["elapsed_ms"] = round((t2 - t1) * 1000, 3)

    rng = random.Random(seed)
    max_ruin = max(2, min(ILS_MAX_RUIN, n // 2, nb.shape[1] + 1))
    ils = {"iterations": 0, "improvements": 0, "max_ruin": max_ruin, "stopped_by": "iteration_cap"}
    best, cur, cur_km = routes, routes, best_km
    t_ils, budget = time.perf_counter(), max(deadline - time.perf_counter(), 1e-9)
    while ils["iterations"] < max_ils_iters:
        now = time.perf_counter()
        if now > deadline:
            ils["stopped_by"] = "time_budget"
            break
        cand = _ruin_recreate(cur, Dl, ql, cap, nbl, rng, max_ruin)
        cand, _ = _local_search(cand, D, q, cap, nb, deadline, Dl)
        km = sum(route_km(r, D) for r in cand)
        ils["iterations"] += 1
        # Threshold accepting: ambang turun linear dari ILS_T0·km_terbaik ke 0 (progres iterasi/waktu).
        progress = max(ils["iterations"] / max_ils_iters, (now - t_ils) / budget)
        if km < cur_km + ILS_T0 * best_km * (1 - progress):
            cur, cur_km = cand, km
        if km < best_km - EPS:
            best, best_km = cand, km
            ils["improvements"] += 1
    ils["improvement_km"] = round(ls_km - best_km, 3)
    ils["elapsed_ms"] = round((time.perf_counter() - t2) * 1000, 3)
    return best, {"construction_elapsed_ms": round((t1 - t0) * 1000, 3), "merges": merges,
                  "neighbors_k_savings": int(nb_s.shape[1]), "neighbors_k_ls": int(nb.shape[1]),
                    "construction_km": round(construction_km, 3), "local_search": ls, "ils": ils}


# ---------------------------------------------------------------- orkestrasi
class _Trail:
    """Pencatat langkah komputasi untuk `computation_details`."""

    def __init__(self):
        self.steps, self._t = [], time.perf_counter()

    def add(self, name, explanation, formula=None, complexity=None, elapsed_ms=None, **result):
        """elapsed_ms eksplisit dipakai bila beberapa tahap diukur di dalam satu pemanggilan solver."""
        now = time.perf_counter()
        self.steps.append({"step": len(self.steps) + 1, "name": name, "explanation": explanation,
                           "formula": formula, "complexity": complexity, "result": result,
                           "elapsed_ms": round((now - self._t) * 1000 if elapsed_ms is None else elapsed_ms, 3)})
        self._t = now


def plan_routes(depot: dict, mills: list[dict], req: RouteRequest) -> dict:
    t_start = time.perf_counter()
    trail = _Trail()
    cap, rho = req.vehicle_m3, req.bulk_density_kg_m3

    # 1. Pecah penggilingan yang volumenya > kapasitas: trip penuh langsung + sisa ikut solver.
    stops, direct_trips = [], []
    for m in mills:
        vol = max(float(m["stock_ton"]), 0.0) * 1000 / rho
        full_trips = max(math.ceil(vol / cap - EPS) - 1, 0)
        direct_trips += [{"mill": m, "m3": cap}] * full_trips
        vol -= full_trips * cap
        if vol > 1e-6:
            stops.append({"mill": m, "m3": vol})
    n = len(stops)
    trail.add("Konversi tonase → volume & pemecahan muatan",
              "Sekam ringan sehingga kapasitas truk dibatasi volume. Penggilingan dengan volume > kapasitas "
              "dilayani trip penuh langsung; sisanya menjadi titik jemput untuk solver.",
              formula="V_i = ton_i × 1000 / ρ;  trip_langsung_i = ⌈V_i / Q⌉ − 1",
              complexity="O(m)", mills=len(mills), pickup_points=n, direct_full_trips=len(direct_trips),
              vehicle_m3=cap, bulk_density_kg_m3=rho)

    # 2. Matriks jarak.
    lat = np.array([depot["lat"], *(s["mill"]["lat"] for s in stops)], float)
    lon = np.array([depot["lon"], *(s["mill"]["lon"] for s in stops)], float)
    D = distance_matrix(lat, lon)
    q = np.array([s["m3"] for s in stops], float)
    if not np.isfinite(D).all():
        raise ValueError("Koordinat tidak valid menghasilkan jarak non-finite.")
    trail.add("Matriks jarak (vektorisasi NumPy)",
              "Jarak great-circle dikali faktor jalan untuk seluruh pasangan titik sekaligus.",
              formula="d_ij = 2R·asin(√(sin²(Δφ/2) + cosφ_i·cosφ_j·sin²(Δλ/2))) × 1.3",
              complexity="O(n²)", matrix_size=f"{n + 1}×{n + 1}", road_factor=P("logistik.road_factor"))

    # 3. Solver.
    if n == 0:
        mode_used, reason, routes = "trivial", "Tidak ada titik sisa; semua muatan berupa trip penuh langsung.", []
    elif req.mode == "exact" or (req.mode == "auto" and n <= EXACT_AUTO_MAX):
        if n > EXACT_HARD_MAX:
            raise SolverLimitError(
                f"Mode exact hanya dijamin < 500 ms untuk ≤ {EXACT_HARD_MAX} titik jemput; permintaan berisi {n}. "
                "Gunakan mode 'auto' atau 'heuristic'.")
        mode_used = "exact"
        reason = (f"{n} titik ≤ {EXACT_AUTO_MAX}: ruang solusi cukup kecil untuk dihitung optimal."
                  if req.mode == "auto" else "Diminta eksplisit.")
        routes, st = solve_exact(D, q, cap)
        trail.add("Held-Karp per subset + DP set-partitioning",
                  "Biaya tur optimal dihitung untuk setiap himpunan titik yang muat satu truk, lalu dipilih "
                  "kombinasi himpunan disjoint yang menutup semua titik dengan jarak total minimum.",
                  formula="C(S) = min_j HK(S, j) + d_j0;  F(M) = min_{S⊆M, S∋min(M), q(S)≤Q} C(S) + F(M∖S)",
                  complexity="O(2ⁿ·n² + 3ⁿ)", **st)
    else:
        mode_used = "heuristic"
        reason = (f"{n} titik > {EXACT_AUTO_MAX}: masalah NP-hard, dipakai heuristik dengan anggaran "
                  f"{req.time_budget_ms} ms." if req.mode == "auto" else "Diminta eksplisit.")
        # Anggaran end-to-end: waktu pra-proses (matriks jarak) dipotong dari jatah solver.
        used_ms = (time.perf_counter() - t_start) * 1000
        routes, st = solve_heuristic(D, q, cap, max(10, int(req.time_budget_ms - used_ms)))
        ls, ils = st.pop("local_search"), st.pop("ils")
        t_construct = st.pop("construction_elapsed_ms", None)
        trail.add("Konstruksi Clarke-Wright savings (granular)",
                  "Gabungkan dua rute bila menjemput keduanya dalam satu trip menghemat jarak; hanya pasangan "
                  "k-tetangga terdekat yang dievaluasi, diurutkan dari penghematan terbesar.",
                  formula="s_ij = d_0i + d_0j − d_ij  (gabung bila s_ij > 0 dan V_r + V_s ≤ Q)",
                  complexity="O(n·k·log(n·k))", elapsed_ms=t_construct, **st)
        trail.add("Local search: relocate, swap, 2-opt",
                  "Pindahkan / tukar titik antar-rute dan balik segmen dalam rute selama total jarak turun dan "
                  "kapasitas tetap terpenuhi; berhenti saat tidak ada perbaikan atau anggaran waktu habis.",
                  formula="Δ_2opt = d_ac + d_bd − d_ab − d_cd;  terapkan bila Δ < 0",
                  complexity="O(n·k) per pass + O(L²) per rute", **ls)
        trail.add("Iterated local search: ruin & recreate",
                  "Sisa anggaran waktu dipakai untuk keluar dari optimum lokal: cabut sekelompok titik yang "
                  "berdekatan, sisipkan ulang di posisi termurah, lalu perbaiki dengan local search. Solusi sedikit "
                  "lebih buruk masih diterima di awal (ambang menurun) agar pencarian tidak terjebak; solusi "
                  "terbaik selalu disimpan.",
                  formula="biaya_sisip(u, i→j) = d_iu + d_uj − d_ij;  terima bila km_baru < km_kini + T0·km_terbaik·(1 − progres)",
                  complexity="O(r·k·L + pass LS) per iterasi", **ils)

    # 4. Kualitas solusi & baseline.
    solver_km = sum(route_km(r, D) for r in routes)
    direct_km = sum(2 * road_km((depot["lat"], depot["lon"]), (t["mill"]["lat"], t["mill"]["lon"]))
                    for t in direct_trips)
    total_km = solver_km + direct_km
    lb = direct_km + (solver_km if mode_used != "heuristic" else lower_bound_km(D, q, cap))
    gap = 100 * (total_km - lb) / total_km if total_km > EPS else 0.0
    depot_pt = (depot["lat"], depot["lon"])
    baseline_km = sum(
        2 * road_km(depot_pt, (m["lat"], m["lon"])) * math.ceil(max(m["stock_ton"], 0) * 1000 / rho / cap - EPS)
        for m in mills
    )
    trail.add("Batas bawah & pembanding",
              "Batas bawah membuktikan seberapa jauh (paling buruk) solusi dari optimal. Pembanding: setiap "
              "penggilingan dijemput terpisah (pola manual saat ini).",
              formula="LB = Σ trip_langsung + max(2·Σ V_i·d_0i / Q, 2·max d_0i, bobot MST)",
              complexity="O(n²)", lower_bound_km=round(lb, 2), gap_upper_bound_pct=round(gap, 2),
              baseline_km=round(baseline_km, 2))

    result = [_route_out(depot, [stops[i - 1] for i in r], route_km(r, D), req) for r in routes]
    result += [_route_out(depot, [t], 2 * road_km(depot_pt, (t["mill"]["lat"], t["mill"]["lon"])), req)
               for t in direct_trips]
    total_ton = sum(max(m["stock_ton"], 0) for m in mills)
    total_cost = total_km * req.cost_per_km
    return {
        "routes": sorted(result, key=lambda r: -r["load_m3"]),
        "summary": {
            "mills": len(mills),
            "total_ton": round(total_ton, 2),
            "vehicles_trips": len(result),
            "total_km": round(total_km, 1),
            "total_cost": round(total_cost),
            "cost_per_ton": round(total_cost / total_ton) if total_ton > EPS else 0,
            "baseline_km": round(baseline_km, 1),
            "saving_pct": round(100 * (1 - total_km / baseline_km), 1) if baseline_km > EPS else 0.0,
            "max_ton_per_trip": round(cap * rho / 1000, 2),
            "algorithm": {"exact": "Held-Karp + set-partitioning DP (optimal)",
                          "heuristic": "Granular Clarke-Wright + relocate/swap/2-opt + ruin & recreate ILS",
                          "trivial": "Trip penuh langsung"}[mode_used],
        },
        "computation_details": {
            "problem": {"type": "CVRP berbatas volume (NP-hard)", "pickup_points": n,
                        "direct_full_trips": len(direct_trips), "vehicle_m3": cap,
                        "objective": "Minimasi total km; armada tidak dibatasi; setiap titik dijemput tepat sekali",
                        "distance_model": f"haversine × {P('logistik.road_factor')}"},
            "mode_requested": req.mode,
            "mode_used": mode_used,
            "mode_reason": reason,
            "steps": trail.steps,
            "quality": {"objective_km": round(total_km, 2), "lower_bound_km": round(lb, 2),
                        "gap_upper_bound_pct": round(gap, 2), "proven_optimal": mode_used != "heuristic"},
            "references": REFERENCES,
            "total_elapsed_ms": round((time.perf_counter() - t_start) * 1000, 3),
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
