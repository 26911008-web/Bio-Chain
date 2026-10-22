"""Skenario lapangan nyata (audit SOP PETA_FLOW, Okt 2026): sinyal putus saat pickup, stop gagal, pengepul batal
saat truk di jalan, retur sekam basah/berjamur, sortir sebagian di QC, jejak GPS offline → emisi ISO 14083,
alokasi armada OR-Tools, stok produk jadi, dan harga beli terikat kadar air.

Berjalan di SQLite terisolasi; dengan BIOCHAIN_TEST_PG_OWNER_URL juga di skema PostgreSQL per tes.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import models  # noqa: F401
from app import params
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.engines.emission import TrackPoint, clean_track, emissions_from_plan, fuel_factors
from app.engines.factory_econ import process_yields
from app.engines.quality import farmgate_price
from app.main import app
from app.models.factory_ops import FinishedGoodsMovement, ReturnCase
from app.models.harvest import Mill
from app.models.ledger import CustodyEvent
from app.models.route import RouteStop, RouteTrackPoint
from app.models.user import User, UserRole
from tests.conftest import isolated_engine

PERSONAS = {"petani": UserRole.PETANI, "petani2": UserRole.PETANI, "pengepul": UserRole.PENGEPUL,
            "pengepul2": UserRole.PENGEPUL, "supir": UserRole.DRIVER, "supir2": UserRole.DRIVER,
            "pabrik": UserRole.PABRIK, "auditor": UserRole.AUDITOR, "admin": UserRole.ADMIN}
MILLS = [("M01", -7.768, 110.293), ("M02", -7.722, 110.300), ("M03", -7.700, 110.350), ("M04", -7.763, 110.472)]
PROX = {"moisture": 11.0, "ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0, "contamination": 1.0}
LAB = {"ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0}
PRICES = {"pabrik.price_pellet_per_kg": 1_800.0, "pabrik.price_biochar_per_kg": 3_000.0,
          "pabrik.price_silica_per_kg": 12_000.0}


@pytest.fixture
def env(tmp_path):
    params.reset_cache()
    params._values.update(PRICES)
    engine, drop_schema = isolated_engine(tmp_path, "field.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (name, role) in enumerate(PERSONAS.items()):
                s.add(User(username=name, phone=f"0821{i:07d}", password_hash="x", full_name=name, role=role,
                           is_active=True, lat=-7.70, lon=110.35))
            for code, lat, lon in MILLS:
                s.add(Mill(code=code, name=f"Penggilingan {code}", kecamatan="Sleman", lat=lat, lon=lon))
            await s.commit()
            users = {u.username: u.id for u in (await s.execute(select(User))).scalars()}
            mills = {m.code: m.id for m in (await s.execute(select(Mill))).scalars()}
            return users, mills

    ids, mills = asyncio.run(setup())

    async def override():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    tokens = {n: create_access_token(ids[n], r.value) for n, r in PERSONAS.items()}

    class E:
        uid, mill = ids, mills
        headers = {n: {"Authorization": f"Bearer {t}"} for n, t in tokens.items()}

        def call(self, who, method, path, json=None):
            return client.request(method, f"/api/v1{path}", json=json, headers=self.headers[who])

        def ok(self, who, method, path, json=None, status=200):
            r = self.call(who, method, path, json)
            assert r.status_code == status, f"{who} {method} {path} → {r.status_code}: {r.text}"
            return r.json()

        def q(self, fn):
            async def run():
                async with Session() as s:
                    return await fn(s)
            return asyncio.run(run())

    yield E()
    app.dependency_overrides.pop(get_db, None)
    params.reset_cache()
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


def verified(env, mill="M01", kg=1000.0, farmer="petani", **prox):
    h = env.ok(farmer, "POST", "/farmer/harvest", {"quantity_kg": kg, "mill_id": env.mill[mill]}, status=201)
    env.ok("pengepul", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": kg, **{**PROX, **prox}})
    return h


def dispatched(env, harvests, driver="supir", start=True):
    r = env.ok("pabrik", "POST", "/factory/dispatch",
               {"driver_id": env.uid[driver], "harvest_ids": [h["id"] for h in harvests]}, status=201)
    if start:
        env.ok(driver, "POST", f"/driver/start-route?route_id={r['route_id']}")
    return r


def pickup(env, route, i, h, driver="supir", **extra):
    return env.ok(driver, "POST", "/driver/confirm-pickup",
                  {"route_stop_id": route["stops"][i]["route_stop_id"], "qr_code": h["qr_code"],
                   "actual_ton": 1.0, **extra})


# ---------------------------------------------------------------- jaringan putus saat pickup (store & forward)
def test_pickup_retry_after_lost_response_is_not_duplicated(env):
    """Server sudah commit, tapi respons hilang (sinyal putus). Antrean HP mengirim ulang dengan
    client_event_id yang sama → 200 'already_confirmed', satu custody event, satu resi."""
    h = verified(env)
    route = dispatched(env, [h])
    body = {"route_stop_id": route["stops"][0]["route_stop_id"], "qr_code": h["qr_code"], "actual_ton": 1.0,
            "client_event_id": str(uuid.uuid4()),
            "client_recorded_at": (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()}
    first = env.ok("supir", "POST", "/driver/confirm-pickup", body)
    for _ in range(3):                                   # outbox mencoba ulang berkali-kali
        again = env.ok("supir", "POST", "/driver/confirm-pickup", body)
        assert again["already_confirmed"] is True
    assert first["already_confirmed"] is False

    async def count(s):
        return (await s.execute(select(func.count()).select_from(CustodyEvent)
                                .where(CustodyEvent.harvest_id == h["id"], CustodyEvent.stage == "driver_pickup"))).scalar()
    assert env.q(count) == 1


def test_concurrent_replays_from_two_tabs_create_one_pickup(env):
    h = verified(env)
    route = dispatched(env, [h])
    body = {"route_stop_id": route["stops"][0]["route_stop_id"], "qr_code": h["qr_code"],
            "client_event_id": str(uuid.uuid4())}

    async def burst():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await asyncio.gather(*[c.post("/api/v1/driver/confirm-pickup", json=body,
                                                 headers=env.headers["supir"]) for _ in range(4)])
    codes = sorted(r.status_code for r in asyncio.run(burst()))
    assert all(c in (200, 409) for c in codes) and 200 in codes

    async def count(s):
        return (await s.execute(select(func.count()).select_from(CustodyEvent)
                                .where(CustodyEvent.harvest_id == h["id"], CustodyEvent.stage == "driver_pickup"))).scalar()
    assert env.q(count) == 1


def test_offline_gps_track_upload_is_idempotent_and_drives_emissions(env):
    h1, h2 = verified(env, "M01"), verified(env, "M04")
    route = dispatched(env, [h1, h2])
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    # Jejak depot → M01 → M04 → depot, 1 titik/menit; satu glitch GPS 200 km & satu titik akurasi buruk
    path = [(-7.745, 110.362), (-7.768, 110.293), (-7.763, 110.472), (-7.745, 110.362)]
    pts, k = [], 0
    for (a_lat, a_lon), (b_lat, b_lon) in zip(path, path[1:]):
        for s in range(20):
            f = s / 20
            pts.append({"client_point_id": f"p-{route['route_id']}-{k:04d}",
                        "recorded_at": (t0 + timedelta(minutes=k)).isoformat(),
                        "lat": a_lat + (b_lat - a_lat) * f, "lon": a_lon + (b_lon - a_lon) * f, "accuracy_m": 8})
            k += 1
    pts.append({"client_point_id": f"p-{route['route_id']}-9999", "recorded_at": (t0 + timedelta(minutes=k)).isoformat(),
                "lat": path[-1][0], "lon": path[-1][1], "accuracy_m": 8})
    pts.insert(30, {"client_point_id": "glitch-0001", "recorded_at": (t0 + timedelta(minutes=29, seconds=30)).isoformat(),
                    "lat": -9.5, "lon": 110.4, "accuracy_m": 10})
    pts.insert(10, {"client_point_id": "blurry-0001", "recorded_at": (t0 + timedelta(minutes=9, seconds=30)).isoformat(),
                    "lat": -7.70, "lon": 110.20, "accuracy_m": 900})
    pickup(env, route, 0, h1, client_recorded_at=(t0 + timedelta(minutes=20)).isoformat())
    pickup(env, route, 1, h2, client_recorded_at=(t0 + timedelta(minutes=40)).isoformat())

    half = len(pts) // 2
    up1 = env.ok("supir", "POST", "/driver/track", {"route_id": route["route_id"], "points": pts[:half]})
    again = env.ok("supir", "POST", "/driver/track", {"route_id": route["route_id"], "points": pts[:half]})
    assert up1["inserted"] == half and again["inserted"] == 0 and again["duplicates_ignored"] == half

    done = env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    partial_km = done["emissions"]["total_km"]
    # Sisa jejak tiba SETELAH rute selesai (sinyal baru kembali di pabrik) → emisi dihitung ulang
    late = env.ok("supir", "POST", "/driver/track", {"route_id": route["route_id"], "points": pts[half:]})
    assert late["inserted"] == len(pts) - half and late["emissions_recomputed"] is True

    r = env.ok("pabrik", "GET", "/factory/routes")[0]
    assert r["actual_km"] > partial_km
    # Glitch (lompatan > 110 km/jam) & titik akurasi 900 m dibuang: jarak ≈ jarak lurus jalur (± pembulatan)
    straight = sum(_hav(a, b) for a, b in zip(path, path[1:]))
    assert straight * 0.95 < r["actual_km"] < straight * 1.05
    assert r["co2e_wtw_kg"] > 0 and r["co2e_kg_per_ton_husk"] > 0

    async def n_points(s):
        return (await s.execute(select(func.count()).select_from(RouteTrackPoint))).scalar()
    assert env.q(n_points) == len(pts)


def _hav(a, b):
    from app.engines.emission import haversine_km
    return haversine_km(a, b)


# ---------------------------------------------------------------- stop gagal & pembatalan
def test_failed_stop_unblocks_route_and_harvest_can_be_rescheduled(env):
    h1, h2 = verified(env, "M01"), verified(env, "M02")
    route = dispatched(env, [h1, h2])
    pickup(env, route, 0, h1)
    blocked = env.call("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    assert blocked.status_code == 409                    # stop 2 belum ditangani
    f = env.ok("supir", "POST", "/driver/stop-failed",
               {"route_stop_id": route["stops"][1]["route_stop_id"], "reason": "stok_tidak_ada",
                "note": "Sekam sudah dijual ke pihak lain"})
    assert f["stop_status"] == "failed"
    # truk sudah datang tapi stok tidak ada → ongkos jarak kosong jadi potongan nyata atas pengepul pemilik lot
    assert f["charge"] and f["charge"]["kind"] == "stop_gagal" and f["charge"]["amount_rp"] > 0
    assert any(c["id"] == f["charge"]["id"] for c in env.ok("pengepul", "GET", "/collector/charges"))
    assert env.ok("supir", "POST", "/driver/stop-failed",
                  {"route_stop_id": route["stops"][1]["route_stop_id"], "reason": "stok_tidak_ada"})["already_recorded"]
    # Stop gagal tidak boleh dimuat belakangan dari antrean offline
    late = env.call("supir", "POST", "/driver/confirm-pickup",
                    {"route_stop_id": route["stops"][1]["route_stop_id"], "qr_code": h2["qr_code"]})
    assert late.status_code == 409
    done = env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    assert done["emissions"]["distance_source"] == "rencana"     # tanpa GPS → estimasi dari stop yang didatangi
    # Panen stop gagal kembali bebas → bisa dijadwalkan ulang ke supir lain
    again = dispatched(env, [h2], driver="supir2")
    assert again["stops"][0]["harvest_id"] == h2["id"]


def test_collector_cancels_while_truck_on_the_road_pays_deadhead(env):
    h1, h2 = verified(env, "M01"), verified(env, "M04")
    route = dispatched(env, [h1, h2])
    pickup(env, route, 0, h1)
    # Sudah di truk → tidak bisa dibatalkan
    assert env.call("pengepul", "POST", f"/collector/harvests/{h1['id']}/cancel-purchase",
                    {"reason": "salah kirim"}).status_code == 409
    # Pengepul lain tidak bisa membatalkan
    assert env.call("pengepul2", "POST", f"/collector/harvests/{h2['id']}/cancel-purchase",
                    {"reason": "iseng"}).status_code == 404
    c = env.ok("pengepul", "POST", f"/collector/harvests/{h2['id']}/cancel-purchase",
               {"reason": "Dijual ke pembeli lain"})
    assert c["outcome"] == "stop_dibatalkan" and c["cancel_fee_rp"] > 0 and c["deadhead_km"] > 0
    assert c["charge"]["amount_rp"] == c["cancel_fee_rp"] and c["charge"]["status"] == "terbuka"
    assert any(x["id"] == c["charge"]["id"] for x in env.ok("pabrik", "GET", "/factory/charges"))
    stops = env.ok("supir", "GET", "/driver/active-route")["stops"]
    assert [s["stop_status"] for s in stops] == ["picked_up", "cancelled"]
    env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    # Potongan dipotong otomatis saat tagihan pabrik → pengepul berikutnya ditandai lunas
    rec = env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h1["id"], "received_kg": 990, "price_per_kg": 450})
    paid = env.ok("pabrik", "POST", f"/factory/settlements/{rec['settlement']['id']}/pay", {"payment_reference": "TRF-9"})
    assert paid["deducted_rp"] == c["cancel_fee_rp"] and paid["net_transfer_rp"] == paid["amount_rp"] - c["cancel_fee_rp"]
    mine = env.ok("pengepul", "GET", "/collector/charges")
    assert next(x for x in mine if x["id"] == c["charge"]["id"])["status"] == "dipotong"


def test_cancel_before_departure_is_free(env):
    h = verified(env)
    dispatched(env, [h], start=False)
    c = env.ok("pengepul", "POST", f"/collector/harvests/{h['id']}/cancel-purchase", {"reason": "batal"})
    assert c["cancel_fee_rp"] == 0


def test_factory_cancels_route_midway_picked_load_still_delivered(env):
    h1, h2 = verified(env, "M01"), verified(env, "M02")
    route = dispatched(env, [h1, h2])
    pickup(env, route, 0, h1)
    c = env.ok("pabrik", "POST", f"/factory/routes/{route['route_id']}/cancel", {"reason": "Hujan deras, jalan banjir"})
    assert c["cancelled_stops"] == 1 and c["picked_up_stops"] == 1 and c["route_status"] == "in_progress"
    env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": h1["id"], "received_kg": 990})
    # Rute yang belum berangkat dibatalkan penuh
    h3 = verified(env, "M03")
    r2 = dispatched(env, [h3], start=False)
    assert env.ok("pabrik", "POST", f"/factory/routes/{r2['route_id']}/cancel",
                  {"reason": "truk rusak"})["route_status"] == "cancelled"
    assert env.call("supir", "POST", f"/driver/cancel?route_id={r2['route_id']}").status_code in (403, 404, 405)


def test_auction_purchase_cancel_restores_farmer_listing(env):
    l = env.ok("petani", "POST", "/farmer/listings",
               {"quantity_kg": 1000, "moisture_pct": 12, "allow_jemput": True, "ask_price_jemput": 400,
                "mill_id": env.mill["M01"]}, status=201)
    b = env.ok("pengepul", "POST", "/collector/bids",
               {"listing_id": l["id"], "scheme": "jemput", "price_per_kg": 450, "quantity_kg": 1000}, status=201)
    a = env.ok("petani", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 1000})
    assert a["listing_status"] == "closed"
    c = env.ok("pengepul", "POST", f"/collector/harvests/{a['harvest_id']}/cancel-purchase",
               {"reason": "Truk tidak tersedia minggu ini"})
    assert c["outcome"] == "lelang_dibatalkan" and c["listing_restored_kg"] == 1000
    mine = env.ok("petani", "GET", "/farmer/listings")
    row = next(x for x in mine if x["id"] == l["id"])
    assert row["status"] == "open" and row["remaining_kg"] == 1000
    # Pengepul lain bisa menawar lagi
    env.ok("pengepul2", "POST", "/collector/bids",
           {"listing_id": l["id"], "scheme": "jemput", "price_per_kg": 430, "quantity_kg": 1000}, status=201)


# ---------------------------------------------------------------- retur sekam basah / berjamur
def test_factory_gate_rejection_opens_return_case_and_resolution_is_final(env):
    h = verified(env)
    route = dispatched(env, [h])
    pickup(env, route, 0, h)
    rj = env.ok("pabrik", "POST", "/factory/reject",
                {"harvest_id": h["id"], "reason": "Karung basah kena hujan di jalan", "reason_code": "basah",
                 "moisture": 31, "weighed_kg": 1020})
    rc = env.ok("pabrik", "GET", "/factory/returns?status=terbuka")
    assert rc[0]["id"] == rj["return_case_id"] and rc[0]["reason_code"] == "basah" and rc[0]["quantity_kg"] == 1020
    assert env.ok("pengepul", "GET", "/collector/returns")[0]["id"] == rj["return_case_id"]
    assert env.ok("auditor", "GET", "/factory/returns")[0]["status"] == "terbuka"
    done = env.ok("pabrik", "POST", f"/factory/returns/{rj['return_case_id']}/resolve",
                  {"disposition": "keringkan_ulang", "cost_bearer": "pengepul", "handling_cost_rp": 150000,
                   "note": "Dijemur 2 hari di lantai jemur pabrik"})
    assert done["status"] == "selesai" and done["disposition"] == "keringkan_ulang"
    assert env.call("pabrik", "POST", f"/factory/returns/{rj['return_case_id']}/resolve",
                    {"disposition": "musnahkan"}).status_code == 409
    assert env.call("auditor", "POST", f"/factory/returns/{rj['return_case_id']}/resolve",
                    {"disposition": "musnahkan"}).status_code == 403


def _agreed_request(env, kg=5000, moisture=11):
    r = env.ok("pengepul", "POST", "/collector/delivery-requests",
               {"quantity_kg": kg, "moisture_est": moisture, "ash_est": 18, "proposed_date": "2026-10-20",
                "proposed_price_per_kg": 480}, status=201)
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{r['id']}/respond", {"action": "accept"})
    return r


def test_qc_partial_sorting_pays_only_accepted_sacks_and_quarantines_moldy(env):
    r = _agreed_request(env)
    qc = env.ok("pabrik", "POST", "/factory/qc",
                {"request_id": r["id"], "gross_kg": 7500, "tare_kg": 2500, "moisture": 11, "contamination": 0,
                 "rejected_kg": 400, "rejected_reason": "berjamur", **LAB}, status=201)
    assert qc["net_kg"] == 4600 and qc["rejected_kg"] == 400 and qc["remaining_kg"] == 4600
    assert qc["total_payment_rp"] == round(4600 * qc["final_price_per_kg"])
    rc = env.ok("pabrik", "GET", "/factory/returns")
    assert rc[0]["reason_code"] == "berjamur" and rc[0]["quantity_kg"] == 400 and rc[0]["qc_id"] == qc["id"]


def test_qc_whole_lot_rejection_opens_return_with_moisture_reason(env):
    r = _agreed_request(env)
    qc = env.ok("pabrik", "POST", "/factory/qc",
                {"request_id": r["id"], "gross_kg": 5000, "tare_kg": 0, "moisture": 32, **LAB}, status=201)
    assert qc["decision"] == "tolak" and qc["total_payment_rp"] == 0
    rc = env.ok("pabrik", "GET", "/factory/returns")[0]
    assert rc["reason_code"] == "basah" and rc["quantity_kg"] == 5000 and rc["moisture"] == 32


def test_sorting_everything_is_refused(env):
    r = _agreed_request(env)
    bad = env.call("pabrik", "POST", "/factory/qc",
                   {"request_id": r["id"], "gross_kg": 1000, "tare_kg": 0, "moisture": 11, "rejected_kg": 1000, **LAB})
    assert bad.status_code == 422


# ---------------------------------------------------------------- BOM multi-output & stok produk jadi
def test_batch_writes_bom_yields_and_finished_goods_ledger(env):
    r = _agreed_request(env)
    lot = env.ok("pabrik", "POST", "/factory/qc", {"request_id": r["id"], "gross_kg": 5000, "tare_kg": 0,
                                                   "moisture": 11, **LAB}, status=201)
    ys = process_yields(11, 18)
    kg = 4000
    env.ok("pabrik", "POST", "/factory/batches",
           {"batch_code": "B-FIELD-1", "inputs": [{"qc_id": lot["id"], "kg": kg}],
            "outputs": {p: round(v * kg, 1) for p, v in ys.outputs.items()},
            "losses": {k: round(v * kg, 1) for k, v in ys.losses.items()}}, status=201)
    inv = env.ok("auditor", "GET", "/factory/inventory")["balance_kg"]
    assert inv["bio_silika"] == pytest.approx(round(ys.outputs["bio_silika"] * kg, 1))
    assert inv["biochar"] <= round(ys.outputs["biochar"] * kg, 1)          # minus porsi petani (bila tertelusur)

    async def outputs(s):
        from app.models.factory_ops import BatchOutput
        return (await s.execute(select(BatchOutput))).scalars().all()
    rows = env.q(outputs)
    assert {o.product for o in rows} == {"bio_pellet", "biochar", "bio_silika"}
    for o in rows:
        if o.quantity_kg > 0:
            assert o.expected_kg == pytest.approx(o.quantity_kg, rel=0.01) and abs(o.yield_variance_pct) < 1
            assert o.yield_pct == pytest.approx(100 * o.quantity_kg / kg, rel=1e-3)

    sale = env.ok("pabrik", "POST", "/factory/inventory/movements",
                  {"product": "bio_silika", "movement": "penjualan", "quantity_kg": 10, "unit_price_rp": 12000,
                   "reference": "DO-001"}, status=201)
    assert sale["quantity_kg"] == -10
    over = env.call("pabrik", "POST", "/factory/inventory/movements",
                    {"product": "bio_silika", "movement": "penjualan", "quantity_kg": 1e6})
    assert over.status_code == 409

    async def n(s):
        return (await s.execute(select(func.count()).select_from(FinishedGoodsMovement))).scalar()
    assert env.q(n) >= 4


# ---------------------------------------------------------------- harga beli terikat kadar air
def test_price_quote_and_verify_follow_dry_matter_and_wet_load_is_not_bought(env):
    dry = env.ok("pengepul", "POST", "/collector/price-quote", {"weighed_kg": 1000, "moisture": 12})
    wet = env.ok("pengepul", "POST", "/collector/price-quote", {"weighed_kg": 1000, "moisture": 18})
    assert dry["pricing"]["price_per_kg"] > wet["pricing"]["price_per_kg"]
    assert wet["pricing"]["mold_risk"] is True and dry["pricing"]["mold_risk"] is False
    assert "ash" in dry["estimated_fields"]                          # lapangan: hanya moisture meter
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500, "mill_id": env.mill["M01"]}, status=201)
    reject = env.call("pengepul", "POST", "/collector/verify",
                      {"harvest_id": h["id"], "weighed_kg": 500, **{**PROX, "moisture": 35}})
    assert reject.status_code == 422 and "Tolak" in reject.json()["detail"]


def test_dry_basis_price_is_continuous_no_grade_cliff():
    params.reset_cache()
    prices = [farmgate_price(400, 1000, m, 0, "B", 1.05, method="basis_kering")["price_per_kg"]
              for m in (10, 11, 12, 13, 14, 15)]
    steps = [a - b for a, b in zip(prices, prices[1:])]
    assert all(s > 0 for s in steps) and max(steps) - min(steps) < 0.5      # turun merata ±4.5 Rp per 1% air
    assert farmgate_price(400, 1000, 30, 0, "TOLAK", 0)["total_price"] == 0


# ---------------------------------------------------------------- engine emisi & OR-Tools
def test_b40_blend_factor_matches_glec_derivation():
    params.reset_cache()
    ff = fuel_factors()
    assert ff["wtw_kg_per_l"] == pytest.approx(0.6 * (2.68 + 0.81) + 0.4 * 1.16, abs=1e-6)
    assert ff["ttw_kg_per_l"] == pytest.approx(0.6 * 2.68, abs=1e-6)


def test_empty_running_is_counted_in_emissions():
    params.reset_cache()
    laden_only = emissions_from_plan([(10, 3000)], 3000)
    with_empty = emissions_from_plan([(10, 0), (10, 3000)], 3000)
    assert with_empty["co2e_wtw_kg"] > laden_only["co2e_wtw_kg"]
    assert with_empty["empty_km"] == 10 and with_empty["intensity_g_per_tkm"] > laden_only["intensity_g_per_tkm"]


def test_gps_cleaning_drops_glitch_blur_and_jitter():
    params.reset_cache()
    t = datetime(2026, 10, 9, tzinfo=timezone.utc)
    pts = [TrackPoint(t, -7.745, 110.362, 5),
           TrackPoint(t + timedelta(seconds=30), -7.74501, 110.36201, 5),     # jitter < 15 m
           TrackPoint(t + timedelta(seconds=60), -7.30, 110.36, 5),           # lompat 50 km dalam 1 menit
           TrackPoint(t + timedelta(seconds=90), -7.75, 110.37, 500),         # akurasi buruk
           TrackPoint(t + timedelta(seconds=120), -7.75, 110.37, 5)]
    kept, stats = clean_track(pts)
    assert len(kept) == 2 and stats["dropped"] == {"accuracy": 1, "speed": 1, "jitter": 1}


def test_fleet_dispatch_optimize_preview_then_commit(env):
    hs = [verified(env, m, kg=1200) for m in ("M01", "M02", "M03", "M04")]
    body = {"harvest_ids": [h["id"] for h in hs], "time_limit_ms": 300,
            "vehicles": [{"driver_id": env.uid["supir"], "vehicle_m3": 30},
                         {"driver_id": env.uid["supir2"], "vehicle_m3": 30}]}
    plan = env.ok("pabrik", "POST", "/factory/dispatch/optimize", body)
    assert plan["committed"] is False and not plan["unassigned"]
    assert sorted(i for r in plan["routes"] for i in r["stops"]) == sorted(h["id"] for h in hs)
    assert all(r["load_m3"] <= 30 for r in plan["routes"]) and plan["summary"]["total_co2e_wtw_kg"] > 0
    assert env.call("admin", "POST", "/factory/dispatch/optimize", {**body, "commit": True}).status_code == 403
    done = env.ok("pabrik", "POST", "/factory/dispatch/optimize", {**body, "commit": True})
    assert all("route_id" in r for r in done["routes"])
    again = env.call("pabrik", "POST", "/factory/dispatch/optimize", {**body, "commit": True})
    assert again.status_code == 409                              # tidak bisa dijadwalkan dua kali
    routes = env.ok("pabrik", "GET", "/factory/routes")
    assert {r["optimizer"] for r in routes} == {"ortools"} and all(r["planned_km"] > 0 for r in routes)


def test_routes_optimize_supports_ortools_mode(env):
    r = env.ok("pabrik", "POST", "/labs/routes/optimize", {"mode": "ortools", "time_budget_ms": 400})
    assert r["computation_details"]["mode_used"] == "ortools"
    assert r["summary"]["total_km"] <= r["summary"]["baseline_km"]


# ---------------------------------------------------------------- green scorecard & kesiapan lapangan
def test_green_scorecard_uses_real_batches_routes_and_returns(env):
    r = _agreed_request(env)
    lot = env.ok("pabrik", "POST", "/factory/qc", {"request_id": r["id"], "gross_kg": 5000, "tare_kg": 0,
                                                   "moisture": 11, "rejected_kg": 200, "rejected_reason": "berjamur",
                                                   **LAB}, status=201)
    ys = process_yields(11, 18)
    kg = 4000
    env.ok("pabrik", "POST", "/factory/batches",
           {"batch_code": "B-GREEN-1", "inputs": [{"qc_id": lot["id"], "kg": kg}], "pyrolysis_temp_c": 520,
            "outputs": {p: round(v * kg, 1) for p, v in ys.outputs.items()},
            "losses": {k: round(v * kg, 1) for k, v in ys.losses.items()},
            "costs": [{"item": "listrik", "amount_rp": 800000, "driver_qty": 600, "driver_unit": "kWh"}]}, status=201)
    h = verified(env)
    route = dispatched(env, [h])
    pickup(env, route, 0, h)
    env.ok("supir", "POST", f"/driver/complete-route?route_id={route['route_id']}")
    sc = env.ok("auditor", "GET", "/factory/green-scorecard")
    c = sc["carbon_tco2e"]
    biochar_t = round(ys.outputs["biochar"] * kg, 1) / 1000
    assert c["biochar_sequestration"] == pytest.approx(biochar_t * 0.49 * 0.80 * 44 / 12, rel=1e-3)
    assert c["avoided_open_burning"] > 0 and c["transport_emissions"] < 0 and c["process_electricity"] < 0
    assert c["net"] == pytest.approx(c["avoided_open_burning"] + c["biochar_sequestration"]
                                     + c["transport_emissions"] + c["process_electricity"], abs=1e-3)
    assert "bukan kredit karbon" in c["status"]
    circ = sc["circularity"]
    assert 0 < circ["mass_valorization_pct"] <= 100 and circ["return_rate_pct"] > 0
    assert sc["green_chemistry"]["silica_extraction_efficiency_pct"] is not None
    assert sc["recommendations"] and sc["data_quality"]["routes_completed"] == 1
    assert env.call("petani", "GET", "/factory/green-scorecard").status_code == 403


def test_collector_may_buy_wet_husk_for_drying_explicitly(env):
    h = env.ok("petani", "POST", "/farmer/harvest", {"quantity_kg": 500, "mill_id": env.mill["M01"]}, status=201)
    v = env.ok("pengepul", "POST", "/collector/verify",
               {"harvest_id": h["id"], "weighed_kg": 500, **{**PROX, "moisture": 30}, "beli_untuk_dikeringkan": True})
    # Harga basis kering: 400 × 0,70/0,88 per kg — bukan Rp 0 dan bukan harga penuh
    assert v["grade"] == "TOLAK" and 0 < v["total_price"] < 500 * 400
    assert v["pricing"]["mold_risk"] is True


def test_pickup_far_from_mill_is_flagged_not_blocked(env):
    h = verified(env, "M01")
    route = dispatched(env, [h])
    far = pickup(env, route, 0, h, lat=-7.60, lon=110.70)          # ±40 km dari penggilingan M01
    assert far["geofence_flag"] is True and far["distance_to_mill_m"] > 30_000


def test_wrong_phone_clock_does_not_shift_report_month(env):
    h = env.ok("petani", "POST", "/farmer/harvest",
               {"quantity_kg": 300, "mill_id": env.mill["M01"], "client_recorded_at": "2019-01-01T08:00:00+00:00"},
               status=201)
    rows = env.ok("petani", "GET", "/farmer/harvests")
    row = next(x for x in (rows if isinstance(rows, list) else rows.get("harvests", rows)) if x["id"] == h["id"])
    assert not row["reported_at"].startswith("2019")


def test_demo_endpoints_hidden_when_demo_mode_off(env, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/api/v1/auth/demo-accounts").status_code == 404
    assert env.call("admin", "POST", "/auth/reset-demo").status_code == 404


def test_rate_limit_bucket_is_per_user_not_shared_ip():
    from app.middleware.rate_limiter import _user_bucket
    a = "Bearer " + create_access_token(11, "petani")
    b = "Bearer " + create_access_token(12, "petani")
    assert _user_bucket(a) == "u:11" and _user_bucket(b) == "u:12"
    assert _user_bucket("Bearer palsu.token.x") is None and _user_bucket(None) is None
