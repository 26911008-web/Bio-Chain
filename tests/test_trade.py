"""Fase 2 — Mesin transaksi B2B: listing petani, tawaran pengepul (jemput/antar, sebagian),
petani memilih, generator resi atomik TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[SEQ], penasihat harga."""

import asyncio
import re
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.main import app
from tests.conftest import isolated_engine
from app.models.user import User, UserRole
from app.routers.auth import hash_password
from app.services.trx_code import WIB, new_verification_code, yymm

PROXIMATE = {"moisture": 11.0, "ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0, "contamination": 1.0}
PEOPLE = {   # (peran, lat, lon) — sekitar Sleman
    "petani_a": (UserRole.PETANI, -7.768, 110.293), "petani_b": (UserRole.PETANI, -7.722, 110.300),
    "pengepul_1": (UserRole.PENGEPUL, -7.700, 110.350), "pengepul_2": (UserRole.PENGEPUL, -7.760, 110.400),
    "supir": (UserRole.DRIVER, -7.735, 110.335), "pabrik": (UserRole.PABRIK, -7.745, 110.362),
    "auditor": (UserRole.AUDITOR, None, None),
}
HASH = hash_password("x")


@pytest.fixture
def env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "trade.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (name, (role, lat, lon)) in enumerate(PEOPLE.items()):
                s.add(User(username=name, phone=f"0811{i:07d}", password_hash=HASH, full_name=name, role=role,
                           is_active=True, lat=lat, lon=lon))
            await s.commit()
            return {u.username: u for u in (await s.execute(select(User))).scalars()}

    users = asyncio.run(setup())

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
    headers = {n: {"Authorization": f"Bearer {create_access_token(u.id, u.role.value)}"} for n, u in users.items()}

    class E:
        ids = {n: u.id for n, u in users.items()}
        h = headers
        session = Session

        def call(self, who, method, path, json=None):
            return client.request(method, f"/api/v1{path}", json=json, headers=headers[who])

        def ok(self, who, method, path, json=None, status=200):
            r = self.call(who, method, path, json)
            assert r.status_code == status, f"{who} {method} {path} → {r.status_code}: {r.text}"
            return r.json()

    yield E()
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


def listing(env, who="petani_a", qty=1000, **kw):
    body = {"quantity_kg": qty, "moisture_pct": 12, "allow_jemput": True, "ask_price_jemput": 400,
            "allow_antar": True, "ask_price_antar": 480, **kw}
    return env.ok(who, "POST", "/farmer/listings", body, status=201)


def bid(env, who, listing_id, scheme="jemput", price=420, qty=1000):
    return env.ok(who, "POST", "/collector/bids",
                  {"listing_id": listing_id, "scheme": scheme, "price_per_kg": price, "quantity_kg": qty}, status=201)


# ---------------------------------------------------------------- listing & tawaran
def test_two_schemes_with_separate_reserve_prices(env):
    l = listing(env)
    assert l["schemes"] == {"jemput": 400, "antar": 480} and l["status"] == "open"
    r = env.call("pengepul_1", "POST", "/collector/bids",
                 {"listing_id": l["id"], "scheme": "antar", "price_per_kg": 450, "quantity_kg": 500})
    assert r.status_code == 422 and "di bawah harga minimum" in r.json()["detail"]
    assert bid(env, "pengepul_1", l["id"], "antar", 490, 500)["status"] == "active"


def test_scheme_not_offered_is_rejected(env):
    l = listing(env, allow_antar=False, ask_price_antar=None)
    r = env.call("pengepul_1", "POST", "/collector/bids",
                 {"listing_id": l["id"], "scheme": "antar", "price_per_kg": 900, "quantity_kg": 100})
    assert r.status_code == 422 and "tidak membuka skema antar" in r.json()["detail"]


def test_new_bid_replaces_previous_active_bid_same_scheme(env):
    l = listing(env)
    first = bid(env, "pengepul_1", l["id"], price=410)
    bid(env, "pengepul_1", l["id"], price=430)
    statuses = {b["bid_id"]: b["status"] for b in env.ok("pengepul_1", "GET", "/collector/bids")}
    assert statuses[first["bid_id"]] == "withdrawn" and list(statuses.values()).count("active") == 1


def test_bid_cannot_exceed_remaining_stock(env):
    l = listing(env, qty=300)
    r = env.call("pengepul_1", "POST", "/collector/bids",
                 {"listing_id": l["id"], "scheme": "jemput", "price_per_kg": 420, "quantity_kg": 301})
    assert r.status_code == 422


# ---------------------------------------------------------------- petani memilih, sebagian, atomik
def test_farmer_compares_net_value_and_chooses_partially(env):
    l = listing(env, qty=1000)
    b_jemput = bid(env, "pengepul_1", l["id"], "jemput", 430, 600)
    b_antar = bid(env, "pengepul_2", l["id"], "antar", 520, 1000)
    view = env.ok("petani_a", "GET", f"/farmer/listings/{l['id']}/bids")
    antar = next(b for b in view["bids"] if b["scheme"] == "antar")
    assert antar["farmer_transport_cost_per_kg"] > 0
    assert antar["net_to_farmer_per_kg"] == pytest.approx(520 - antar["farmer_transport_cost_per_kg"], abs=0.2)
    assert sum(b["highest_net"] for b in view["bids"]) == 1

    # Petani memilih sendiri: 600 kg jemput ke pengepul_1, sisanya 400 kg antar ke pengepul_2
    a1 = env.ok("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b_jemput["bid_id"], "quantity_kg": 600})
    assert a1["listing_status"] == "partially_awarded" and a1["remaining_kg"] == 400
    a2 = env.ok("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b_antar["bid_id"], "quantity_kg": 400})
    assert a2["listing_status"] == "closed" and a2["remaining_kg"] == 0 and a2["contract_value_rp"] == 400 * 520


def test_accept_more_than_bid_is_rejected(env):
    l = listing(env, qty=1000)
    b = bid(env, "pengepul_1", l["id"], qty=300)
    r = env.call("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 301})
    assert r.status_code == 422


def test_concurrent_accepts_never_oversell(env):
    l = listing(env, qty=1000)
    b1 = bid(env, "pengepul_1", l["id"], qty=700)
    b2 = bid(env, "pengepul_2", l["id"], qty=700)

    async def race():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await asyncio.gather(*[
                c.post(f"/api/v1/farmer/listings/{l['id']}/accept", headers=env.h["petani_a"],
                       json={"bid_id": b["bid_id"], "quantity_kg": 700}) for b in (b1, b2)])

    codes = sorted(r.status_code for r in asyncio.run(race()))
    assert codes == [200, 409], codes
    mine = env.ok("petani_a", "GET", "/farmer/listings")[0]
    assert mine["remaining_kg"] == 300 and mine["status"] == "partially_awarded"


def test_closing_listing_rejects_remaining_bids(env):
    l = listing(env, qty=500)
    b1 = bid(env, "pengepul_1", l["id"], qty=500)
    b2 = bid(env, "pengepul_2", l["id"], qty=500, price=405)
    env.ok("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b1["bid_id"], "quantity_kg": 500})
    assert {b["bid_id"]: b["status"] for b in env.ok("pengepul_2", "GET", "/collector/bids")}[b2["bid_id"]] == "rejected"
    r = env.call("pengepul_2", "POST", "/collector/bids",
                 {"listing_id": l["id"], "scheme": "jemput", "price_per_kg": 500, "quantity_kg": 100})
    assert r.status_code == 409


def test_farmer_cannot_touch_other_farmers_listing(env):
    l = listing(env, who="petani_a")
    b = bid(env, "pengepul_1", l["id"])
    assert env.call("petani_b", "POST", f"/farmer/listings/{l['id']}/accept",
                    {"bid_id": b["bid_id"], "quantity_kg": 10}).status_code == 404
    assert env.call("petani_b", "GET", f"/farmer/listings/{l['id']}/bids").status_code == 404


@pytest.mark.parametrize("who,method,path", [
    ("petani_a", "POST", "/collector/bids"), ("pengepul_1", "POST", "/farmer/listings"),
    ("supir", "GET", "/collector/market"), ("auditor", "POST", "/farmer/listings/1/accept"),
])
def test_trade_rbac(env, who, method, path):
    assert env.call(who, method, path, {}).status_code == 403


# ---------------------------------------------------------------- kontrak → custody → resi
def test_awarded_harvest_is_exclusive_and_priced_at_agreed_price(env):
    l = listing(env, qty=1000)
    b = bid(env, "pengepul_1", l["id"], price=455, qty=1000)
    h = env.ok("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 1000})
    queue_other = env.ok("pengepul_2", "GET", "/collector/available-harvests")
    assert all(x["id"] != h["harvest_id"] for x in queue_other)
    assert env.call("pengepul_2", "POST", "/collector/verify",
                    {"harvest_id": h["harvest_id"], "weighed_kg": 990, **PROXIMATE}).status_code == 403
    v = env.ok("pengepul_1", "POST", "/collector/verify",
               {"harvest_id": h["harvest_id"], "weighed_kg": 990, "evidence_photo_url": "https://cdn.example/f1.jpg", **PROXIMATE})
    assert v["total_price"] == 990 * 455 and v["price_basis"] == "harga lelang"
    code = v["verification_code"]
    assert re.fullmatch(rf"TRX-PTN{env.ids['petani_a']:04d}-PGP{env.ids['pengepul_1']:04d}-{yymm()}-00001", code), code


def test_full_chain_gets_one_code_per_handover(env):
    l = listing(env, qty=800)
    b = bid(env, "pengepul_1", l["id"], qty=800)
    h = env.ok("petani_a", "POST", f"/farmer/listings/{l['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 800})
    hid = h["harvest_id"]
    env.ok("pengepul_1", "POST", "/collector/verify", {"harvest_id": hid, "weighed_kg": 800, **PROXIMATE})
    route = env.ok("pabrik", "POST", "/factory/dispatch", {"driver_id": env.ids["supir"], "harvest_ids": [hid]}, status=201)
    env.ok("supir", "POST", f"/driver/start-route?route_id={route['route_id']}")
    env.ok("supir", "POST", "/driver/confirm-pickup", {"route_stop_id": route["stops"][0]["route_stop_id"],
                                                       "qr_code": h["qr_code"], "photo_url": "https://cdn.example/p.jpg"})
    env.ok("pabrik", "POST", "/factory/receive", {"harvest_id": hid, "received_kg": 780})
    trail = env.ok("auditor", "GET", f"/auditor/mass-balance/{hid}")["custody_trail"]
    codes = [e["verification_code"] for e in trail if e["verification_code"]]
    assert [c.split("-")[1] + ">" + c.split("-")[2] for c in codes] == [
        f"PTN{env.ids['petani_a']:04d}>PGP{env.ids['pengepul_1']:04d}",
        f"PGP{env.ids['pengepul_1']:04d}>DRV{env.ids['supir']:04d}",
        f"DRV{env.ids['supir']:04d}>PBK{env.ids['pabrik']:04d}"]
    assert next(e for e in trail if e["stage"] == "driver_pickup")["evidence_photo_url"] == "https://cdn.example/p.jpg"


def test_sequence_increments_per_pair_and_resets_per_month(env):
    async def run():
        async with env.session() as s:
            a = await s.get(User, env.ids["petani_a"])
            p = await s.get(User, env.ids["pengepul_1"])
            oct_ = datetime(2026, 10, 15, tzinfo=timezone.utc)
            codes = [await new_verification_code(s, a, p, oct_) for _ in range(3)]
            codes.append(await new_verification_code(s, a, p, datetime(2026, 11, 1, tzinfo=timezone.utc)))
            # Batas bulan dihitung WIB: 31 Okt 18:00 UTC = 1 Nov 01:00 WIB → periode 2611
            codes.append(await new_verification_code(s, a, p, datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)))
            await s.commit()
            return codes
    codes = asyncio.run(run())
    assert [c[-10:] for c in codes] == ["2610-00001", "2610-00002", "2610-00003", "2611-00001", "2611-00002"]
    assert datetime(2026, 10, 31, 18, tzinfo=timezone.utc).astimezone(WIB).month == 11


def test_sequence_is_atomic_under_concurrency(env):
    """50 transaksi serentak dari sesi terpisah → 50 nomor unik tanpa celah."""
    async def one():
        for attempt in range(50):
            try:
                async with env.session() as s:
                    a = await s.get(User, env.ids["petani_b"])
                    p = await s.get(User, env.ids["pengepul_2"])
                    code = await new_verification_code(s, a, p)
                    await s.commit()
                    return code
            except Exception:              # SQLite: penulis tunggal → coba ulang bila terkunci
                await asyncio.sleep(0.01 * (attempt + 1))
        raise AssertionError("gagal mendapat nomor")

    async def run():
        return await asyncio.gather(*[one() for _ in range(50)])
    seqs = sorted(int(c[-5:]) for c in asyncio.run(run()))
    assert seqs == list(range(1, 51))


# ---------------------------------------------------------------- penasihat harga (logistik marginal)
def test_bid_advisor_uses_marginal_route_cost_for_jemput_only(env):
    l = listing(env, qty=1000)
    jemput = env.ok("pengepul_1", "POST", "/collector/bid-advisor",
                    {"listing_id": l["id"], "scheme": "jemput", "resale_price_per_kg": 520, "margin_per_kg": 30})
    antar = env.ok("pengepul_1", "POST", "/collector/bid-advisor",
                   {"listing_id": l["id"], "scheme": "antar", "resale_price_per_kg": 520, "margin_per_kg": 30})
    assert jemput["logistic_cost_per_kg"] > 0 and antar["logistic_cost_per_kg"] == 0
    assert jemput["max_bid_per_kg"] == pytest.approx(520 - jemput["logistic_cost_per_kg"] - 30, abs=0.2)
    assert antar["max_bid_per_kg"] == 490 and antar["feasible"] is True        # reserve antar 480
    assert 480 <= antar["suggested_bid_per_kg"] <= 490
    assert jemput["computation_details"]["km_marginal"] > 0


def test_bid_advisor_marginal_cost_shrinks_when_route_already_passes_nearby(env):
    near = listing(env, who="petani_a", qty=1000)
    first = env.ok("pengepul_2", "POST", "/collector/bid-advisor",
                   {"listing_id": near["id"], "scheme": "jemput", "resale_price_per_kg": 520})
    # Pengepul_2 sudah memenangkan stok petani_b (searah) → menjemput petani_a hanya menambah sedikit km
    other = listing(env, who="petani_b", qty=1000)
    b = bid(env, "pengepul_2", other["id"], qty=1000)
    env.ok("petani_b", "POST", f"/farmer/listings/{other['id']}/accept", {"bid_id": b["bid_id"], "quantity_kg": 1000})
    second = env.ok("pengepul_2", "POST", "/collector/bid-advisor",
                    {"listing_id": near["id"], "scheme": "jemput", "resale_price_per_kg": 520})
    assert second["computation_details"]["titik_komitmen"] == 1
    assert second["logistic_cost_per_kg"] < first["logistic_cost_per_kg"]
