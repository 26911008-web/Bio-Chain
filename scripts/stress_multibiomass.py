"""Uji stres multi-node platform multi-biomassa (fase 5) terhadap server hidup.

    py scripts/stress_multibiomass.py --url http://127.0.0.1:8766 --users 40 --rounds 5 --out laporan.json

Pengguna virtual paralel memakai akun demo per peran:
  petani   : lapor tongkol jagung / sekam (komoditas acak)
  pengepul : berebut verifikasi lot, catat stok gudang (idempoten, dengan kirim ulang)
  pabrik   : optimasi blend, analisis rute konversi, analisis SEC
  auditor  : baca ledger abu & klaim karbon
Keluaran: jumlah request, error rate, latensi p50/p95/p99 per endpoint, dan pemeriksaan integritas akhir
(tiap lot paling banyak satu pemenang verifikasi, stok gudang = jumlah mutasi unik).
"""
import argparse
import asyncio
import json
import random
import statistics
import time
import uuid
from collections import defaultdict

import httpx

ACCOUNTS = {"petani": ("petani_sugeng", "sekam123"), "pengepul": ("pengepul_sleman", "kud2026"),
            "pabrik": ("pabrik_indmira", "pabrik2026"), "auditor": ("auditor_esg", "audit2026")}


async def main(url: str, users: int, rounds: int, out: str | None) -> dict:
    lat: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    async with httpx.AsyncClient(base_url=url, timeout=60) as c:
        tok = {}
        for role, (u, p) in ACCOUNTS.items():
            r = await c.post("/api/v1/auth/login", json={"identifier": u, "password": p})
            r.raise_for_status()
            tok[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        for code, price in (("tongkol_jagung", 650), ("serbuk_sengon", 500), ("sekam_padi", 450)):
            await c.put(f"/api/v1/biomass/{code}", headers=tok["pabrik"],
                        json={"changes": {"base_price_per_kg": price}, "source": "uji stres fase 5"})
        mills = (await c.get("/api/v1/farmer/mills", headers=tok["petani"])).json()
        wh = await c.post("/api/v1/collector/warehouses", headers=tok["pengepul"], json={"name": f"Stres {uuid.uuid4().hex[:6]}"})
        wh_id = wh.json()["id"]
        reported: list[int] = []
        sent_moves: dict[str, tuple[str, float]] = {}

        async def call(name, method, path, role, **kw):
            t0 = time.perf_counter()
            try:
                r = await c.request(method, path, headers=tok[role], **kw)
                expected_4xx = {409, 403} if name == "verify" else set()      # rebutan lot = hasil wajar, bukan error
                if r.status_code >= 500 or (r.status_code >= 400 and r.status_code not in expected_4xx):
                    errors[name] += 1
                return r
            except httpx.HTTPError:
                errors[name] += 1
                return None
            finally:
                lat[name].append((time.perf_counter() - t0) * 1000)

        async def vuser(i: int):
            rnd = random.Random(i)
            role = ("petani", "pengepul", "pabrik", "auditor")[i % 4]
            for _ in range(rounds):
                if role == "petani":
                    code = rnd.choice(["tongkol_jagung", "sekam_padi"])
                    r = await call("report", "POST", "/api/v1/farmer/harvest", role,
                                   json={"quantity_kg": rnd.randint(300, 900), "commodity": code,
                                         "mill_id": rnd.choice(mills)["id"], "client_event_id": uuid.uuid4().hex})
                    if r is not None and r.status_code == 201:
                        reported.append(r.json()["id"])
                elif role == "pengepul":
                    if reported:
                        hid = rnd.choice(reported)
                        await call("verify", "POST", "/api/v1/collector/verify", role,
                                   json={"harvest_id": hid, "weighed_kg": 500, "moisture": 14, "contamination": 1,
                                         "ash": 18, "volatile_matter": 66, "fixed_carbon": 16})
                    cid = uuid.uuid4().hex
                    code = rnd.choice(["tongkol_jagung", "sekam_padi"])
                    body = {"commodity": code, "movement": "masuk", "kg": 100, "moisture_pct": 15, "client_event_id": cid}
                    sent_moves[cid] = (code, 100)
                    for _ in range(2):                                     # kirim ulang antrean offline
                        await call("warehouse_in", "POST", f"/api/v1/collector/warehouses/{wh_id}/movements", role, json=body)
                elif role == "pabrik":
                    await call("blend_optimize", "POST", "/api/v1/factory/fuel-blend/optimize", role,
                               json={"preset": "pelet_4000_kcal", "target_kg": 10_000,
                                     "feeds": [{"code": "tongkol_jagung", "available_kg": 50_000},
                                               {"code": "serbuk_sengon", "available_kg": 50_000}]})
                    await call("conversion", "POST", "/api/v1/factory/conversion/analyse", role,
                               json={"code": rnd.choice(["sekam_padi", "tongkol_jagung", "ampas_tebu"]), "ton_per_month": 500})
                else:
                    await call("ash_list", "GET", "/api/v1/factory/ash", role)
                    await call("claims_list", "GET", "/api/v1/auditor/carbon-claims", role)

        t0 = time.perf_counter()
        await asyncio.gather(*[vuser(i) for i in range(users)])
        wall = time.perf_counter() - t0

        whs = (await c.get("/api/v1/collector/warehouses", headers=tok["pengepul"])).json()
        stock = {s["commodity"]: s["gross_kg"] for w in whs if w["id"] == wh_id for s in w["stock"]}
        expect = defaultdict(float)
        for code, kg in sent_moves.values():
            expect[code] += kg
        integrity = {"warehouse_stock_matches_unique_moves": {k: stock.get(k, 0) for k in expect} == dict(expect)}

    def pct(v, q):
        v = sorted(v)
        return round(v[min(len(v) - 1, int(q * len(v)))], 1)
    all_lat = [x for v in lat.values() for x in v]
    report = {"url": url, "virtual_users": users, "rounds": rounds, "wall_s": round(wall, 2),
              "requests": len(all_lat), "rps": round(len(all_lat) / wall, 1), "errors": dict(errors),
              "error_rate_pct": round(100 * sum(errors.values()) / max(1, len(all_lat)), 2),
              "latency_ms": {"p50": pct(all_lat, .5), "p95": pct(all_lat, .95), "p99": pct(all_lat, .99),
                             "mean": round(statistics.mean(all_lat), 1)},
              "by_endpoint": {k: {"n": len(v), "p50": pct(v, .5), "p95": pct(v, .95)} for k, v in sorted(lat.items())},
              "integrity": integrity}
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out")
    a = ap.parse_args()
    print(json.dumps(asyncio.run(main(a.url, a.users, a.rounds, a.out)), indent=2, ensure_ascii=False))
