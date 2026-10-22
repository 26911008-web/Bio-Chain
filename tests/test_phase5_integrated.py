"""Fase 5 — Uji terintegrasi multi-node & validasi sirkular (protokol multi-biomassa).

1. Transaksi multi-komoditas paralel: dua pengepul berebut lot tongkol jagung & sekam, lelang diterima bersamaan,
   stok gudang dari dua HP paralel + kirim ulang antrean offline.
2. Proteksi boiler: campuran berisiko slagging ditolak optimizer / ditandai BAHAYA.
3. Sirkular abu: abu lulus uji → ID Poktan; gagal → diblokir; alokasi ganda paralel → satu menang.
4. Stabilitas IKE: injeksi konsumsi tinggi → notifikasi anomali tepat (presisi & recall), beban parsial tanpa alarm.
Berjalan di SQLite dan PostgreSQL (BIOCHAIN_TEST_PG_OWNER_URL).
"""
import asyncio
import random
import uuid

import httpx

from app.engines.sec_monitor import _water_t
from app.main import app
from tests.test_field_ops import PROX, env  # noqa: F401  (fixture)


def _parallel(env, calls):
    """calls: [(who, method, path, json)] dikirim serentak lewat ASGI (bukan berurutan)."""
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=60) as c:
            return await asyncio.gather(*[c.request(m, f"/api/v1{p}", json=j, headers=env.headers[w]) for w, m, p, j in calls])
    return asyncio.run(go())


def _price(env, code, rp):
    env.ok("pabrik", "PUT", f"/biomass/{code}", {"changes": {"base_price_per_kg": rp}, "source": "uji fase 5"})


# ---------------------------------------------------------------- 1. transaksi multi-komoditas paralel
def test_parallel_multi_commodity_purchases(env):
    _price(env, "tongkol_jagung", 650)
    lots = []
    for farmer in ("petani", "petani2"):
        for i, code in enumerate(["tongkol_jagung", "sekam_padi"] * 3):
            h = env.ok(farmer, "POST", "/farmer/harvest", {"quantity_kg": 500 + 10 * i, "mill_id": env.mill["M01"],
                                                          "commodity": code}, status=201)
            lots.append((h["id"], code))
    body = lambda hid, code: ({"harvest_id": hid, "weighed_kg": 500, "moisture": 17, "contamination": 1}  # noqa: E731
                              if code == "tongkol_jagung" else {"harvest_id": hid, "weighed_kg": 500, **PROX})
    calls = [(who, "POST", "/collector/verify", body(hid, code)) for hid, code in lots for who in ("pengepul", "pengepul2")]
    random.Random(5).shuffle(calls)
    res = _parallel(env, calls)
    ok = [r.json() for r in res if r.status_code == 200]
    assert len(ok) == len(lots)                                                   # tiap lot tepat satu pemenang
    assert all(r.status_code in (200, 403, 409) for r in res)
    won = {r["harvest_id"]: r for r in ok}
    for hid, code in lots:
        assert won[hid]["commodity"] == code
        if code == "tongkol_jagung":                                              # basis kering vs MC acuan 15 %
            assert abs(won[hid]["total_price"] - 500 * (0.83 / 0.85) * 650) < 5      # kotoran 1 % ≤ toleransi 2 %: tidak dipotong

    # lelang tongkol jagung: dua tawaran diterima bersamaan → total ≤ stok
    lst = env.ok("petani", "POST", "/farmer/listings", {"quantity_kg": 1000, "commodity": "tongkol_jagung",
                                                         "allow_jemput": True, "ask_price_jemput": 700}, status=201)
    bids = [env.ok(w, "POST", "/collector/bids", {"listing_id": lst["id"], "scheme": "jemput", "price_per_kg": 720,
                                                   "quantity_kg": 700}, status=201) for w in ("pengepul", "pengepul2")]
    res = _parallel(env, [("petani", "POST", f"/farmer/listings/{lst['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 700})
                          for b in bids])
    accepted = [r.json() for r in res if r.status_code in (200, 201)]
    assert 1 <= len(accepted) <= 2
    total = sum(a.get("accepted_kg", a.get("quantity_kg", 0)) for a in accepted)
    assert total <= 1000 + 1e-6
    mine = env.ok("petani", "GET", "/farmer/harvests")
    assert all(h["commodity"] == "tongkol_jagung" for h in mine if h["id"] in {a.get("harvest_id") for a in accepted})

    # gudang: dua HP pengepul mencatat masuk paralel + kirim ulang antrean (idempoten)
    w = env.ok("pengepul", "POST", "/collector/warehouses", {"name": "Gudang Stres"}, status=201)
    moves = [{"commodity": c, "movement": "masuk", "kg": 100, "moisture_pct": 15, "client_event_id": f"st-{i}"}
             for i, c in enumerate(["tongkol_jagung", "sekam_padi"] * 10)]
    res = _parallel(env, [("pengepul", "POST", f"/collector/warehouses/{w['id']}/movements", m) for m in moves + moves])
    assert all(r.status_code in (201, 409) for r in res)
    stock = {s["commodity"]: s["gross_kg"] for s in env.ok("pengepul", "GET", "/collector/warehouses")[0]["stock"]}
    assert stock == {"tongkol_jagung": 1000, "sekam_padi": 1000}                  # 20 unik, replay tidak menggandakan


# ---------------------------------------------------------------- 2. proteksi boiler (slagging)
def test_slagging_blend_rejected_or_flagged(env):
    _price(env, "tongkol_jagung", 650)
    _price(env, "serbuk_sengon", 500)
    corn = {"code": "tongkol_jagung", "available_kg": 50_000}
    wood = {"code": "serbuk_sengon", "available_kg": 50_000}
    only = env.ok("pabrik", "POST", "/factory/fuel-blend/optimize",
                  {"preset": "pelet_4000_kcal", "target_kg": 10_000, "feeds": [corn]})
    assert only["feasible"] is False                                              # ditolak: AI > 0,34 / kalori
    mix = env.ok("pabrik", "POST", "/factory/fuel-blend/optimize",
                 {"preset": "pelet_4000_kcal", "target_kg": 10_000, "feeds": [corn, wood]})
    assert mix["feasible"] and mix["properties"]["indices"]["alkali_index"] <= 0.34 + 1e-6
    assert mix["feasibility_card"]["verdict"] == "LAYAK"
    hot = env.ok("pabrik", "POST", "/factory/fuel-blend/evaluate",
                 {"feeds": [corn, wood], "shares_pct": {"tongkol_jagung": 100}, "product_moisture_pct": 10})
    assert hot["slagging_verdict"] == "BAHAYA"
    assert "Risiko Tinggi Terak/Slagging pada Boiler Industri" in hot["warnings"][0]
    conv = env.ok("pabrik", "POST", "/factory/conversion/analyse", {"code": "tongkol_jagung", "ton_per_month": 300})
    assert any("alkali" in w for w in conv["warnings"])                           # rute energi juga memperingatkan


# ---------------------------------------------------------------- 3. sirkular abu → Poktan
def test_passing_ash_assigned_to_farmer_group_and_failing_blocked(env):
    g1 = env.ok("pabrik", "POST", "/factory/farmer-groups", {"name": "Poktan Makmur", "kecamatan": "Godean",
                                                             "kabupaten": "Sleman", "leader_name": "Bu Sri",
                                                             "leader_user_id": env.uid["petani"]}, status=201)
    g2 = env.ok("pabrik", "POST", "/factory/farmer-groups", {"name": "Poktan Lestari", "kecamatan": "Moyudan",
                                                             "kabupaten": "Sleman", "leader_name": "Pak Joko",
                                                             "leader_user_id": env.uid["petani2"]}, status=201)
    ok = env.ok("pabrik", "POST", "/factory/ash", {"ash_type": "silica_ash", "source_commodity": "sekam_padi",
                                                   "quantity_kg": 400}, status=201)
    env.ok("pabrik", "POST", f"/factory/ash/{ok['id']}/lab", {"pb_ppm": 8, "cd_ppm": 0.3, "as_ppm": 1.5, "hg_ppm": 0.05,
                                                              "lab_report_no": "F5-LULUS"})
    res = _parallel(env, [("pabrik", "POST", f"/factory/ash/{ok['id']}/allocate", {"farmer_group_id": g["id"]})
                          for g in (g1, g2)])
    codes = sorted(r.status_code for r in res)
    assert codes[0] == 200 and codes.count(200) == 1                              # alokasi ganda: satu menang
    winner = next(r.json() for r in res if r.status_code == 200)
    assert winner["farmer_group_id"] in (g1["id"], g2["id"]) and winner["status"] == "dialokasikan"
    leader = "petani" if winner["farmer_group_id"] == g1["id"] else "petani2"
    assert [a["code"] for a in env.ok(leader, "GET", "/farmer/ash")] == [ok["code"]]
    bad = env.ok("pabrik", "POST", "/factory/ash", {"ash_type": "fly_ash", "quantity_kg": 300}, status=201)
    r = env.ok("pabrik", "POST", f"/factory/ash/{bad['id']}/lab", {"pb_ppm": 9, "cd_ppm": 3.1, "as_ppm": 1,
                                                                   "lab_report_no": "F5-GAGAL"})
    assert r["heavy_metal_status"] == "gagal" and "Cd 3.1" in r["limits_snapshot"]["notes"][0]
    assert env.call("pabrik", "POST", f"/factory/ash/{bad['id']}/allocate", {"farmer_group_id": g1["id"]}).status_code == 409


# ---------------------------------------------------------------- 4. stabilitas IKE
def test_injected_power_spikes_flagged_precisely(env):
    rnd = random.Random(11)
    spikes, partial, wet = {22, 31, 38}, {19, 27, 35}, {25, 33}
    logs = []
    for i in range(45):
        util = 0.6 if (i < 14 and i % 4 == 0) else (0.45 if i in partial else 0.9)
        mc = 24 if i in wet else 14
        t = 2.0 * 8 * util
        e = 400 * 8 + 250 * t + 3000 * _water_t(t, mc, 10)
        if i in spikes:
            e *= 1.3                                                              # injeksi konsumsi daya tinggi
        e *= 1 + rnd.gauss(0, 0.015)
        logs.append({"log_date": f"2026-08-{i + 1:02d}" if i < 31 else f"2026-09-{i - 30:02d}", "kwh_total": e / 3.6,
                     "operating_hours": 8, "product_ton": t, "feed_moisture_pct": mc, "rated_capacity_t_h": 2,
                     "client_event_id": f"ike-{uuid.uuid4().hex[:8]}-{i}"})
    env.ok("pabrik", "POST", "/factory/energy/ops-logs", {"facility": "Stres IKE", "logs": logs}, status=201)
    a = env.ok("pabrik", "GET", "/factory/energy/ops-analysis?facility=Stres%20IKE&feed_code=sekam_padi")
    action = {i for i, row in enumerate(a["rows"]) if row["alert"] == "aksi"}
    warn = {i for i, row in enumerate(a["rows"]) if row["alert"] == "peringatan"}
    assert action == spikes                                                       # alarm aksi: presisi & recall 100 %
    assert len(warn) <= 1                                                         # peringatan ±2σ acak ≈ 2,3 %/log (statistik)
    assert not ((action | warn) & partial) and not ((action | warn) & wet)       # beban parsial & basah: tanpa alarm
    wet_ind = {a["rows"][i]["label"] for i in wet}
    assert wet_ind <= {x["label"] for x in a["alerts"] if x["code"] == "pengering_bahan_basah"}


# ---------------------------------------------------------------- 5. race status lain (SQLite mengabaikan FOR UPDATE)
def test_double_click_biochar_handover_debits_wallet_once(env):
    async def credit(s):
        from app.models.ledger import BiocharLedgerEntry
        s.add(BiocharLedgerEntry(farmer_id=env.uid["petani"], entry_type="adjustment", amount_kg=500, note="uji",
                                 created_by_id=env.uid["pabrik"]))
        await s.commit()
    env.q(credit)
    rid = env.ok("petani", "POST", "/farmer/biochar/redeem", {"kg": 200, "land_area_ha": 0.25}, status=201)["id"]
    res = _parallel(env, [("pabrik", "POST", f"/factory/biochar-redemptions/{rid}/handover", {}) for _ in range(4)])
    assert sorted(r.status_code for r in res).count(200) == 1
    w = env.ok("petani", "GET", "/farmer/wallet")
    assert sum(e["amount_kg"] for e in w["entries"] if e["type"] == "redemption") == -200


def test_parallel_auditor_decisions_record_one(env):
    from tests.test_carbon_claims import LAB, _production
    _production(env)
    c = env.ok("pabrik", "POST", "/factory/carbon-claims", LAB, status=201)
    res = _parallel(env, [("auditor", "POST", f"/auditor/carbon-claims/{c['id']}/decision",
                           {"decision": d, "note": f"Putusan paralel {d} untuk uji"}) for d in ("diverifikasi", "ditolak")])
    assert sorted(r.status_code for r in res) == [200, 409]
