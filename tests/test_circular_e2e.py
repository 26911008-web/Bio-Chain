"""E2E siklus ekonomi sirkular + RBAC + race condition + rollback, pada DB SQLite terisolasi.

Skenario utama: Petani A lapor 100 kg → Pengepul B timbang 100 kg → Supir C angkut →
Pabrik D terima 95 kg (susut 5%) → batch menghasilkan 10 kg biochar → 10 kg masuk dompet Petani A.
"""

import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401  — daftarkan semua tabel
from app.database import Base, get_db
from app.main import app
from tests.conftest import isolated_engine
from app.models.harvest import Harvest
from app.models.ledger import BiocharLedgerEntry, CustodyEvent
from app.models.user import User, UserRole
from app.dependencies import create_access_token
from app.routers.auth import hash_password
from app.services import custody

PASSWORD = "rahasia123"
PASSWORD_HASH = hash_password(PASSWORD)     # PBKDF2 mahal: hitung sekali per sesi tes
PERSONAS = {
    "petani_a": UserRole.PETANI, "petani_b": UserRole.PETANI, "pengepul_b": UserRole.PENGEPUL,
    "supir_c": UserRole.DRIVER, "supir_lain": UserRole.DRIVER, "pabrik_d": UserRole.PABRIK,
    "auditor": UserRole.AUDITOR, "admin": UserRole.ADMIN,
}


@pytest.fixture
def env(tmp_path):
    """App dengan DB file sementara + user per persona; mengembalikan helper HTTP per persona."""
    engine, drop_schema = isolated_engine(tmp_path, "e2e.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (name, role) in enumerate(PERSONAS.items()):
                s.add(User(username=name, phone=f"0800000000{i:02d}", password_hash=PASSWORD_HASH,
                           full_name=name, role=role, is_active=True))
            await s.commit()
            return {u.username: u.id for u in (await s.execute(select(User))).scalars()}

    ids = asyncio.run(setup())

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)   # tanpa lifespan → DB demo tidak tersentuh
    tokens = {n: create_access_token(ids[n], role.value) for n, role in PERSONAS.items()}
    # Satu login nyata membuktikan user tersimpan & kredensial valid di DB terisolasi.
    assert client.post("/api/v1/auth/login", json={"identifier": "petani_a", "password": PASSWORD}).status_code == 200

    class Env:
        user_ids = ids

        def call(self, who, method, path, json=None):
            return client.request(method, f"/api/v1{path}", json=json,
                                  headers={"Authorization": f"Bearer {tokens[who]}"})

        def ok(self, who, method, path, json=None, status=200):
            r = self.call(who, method, path, json)
            assert r.status_code == status, f"{who} {method} {path} → {r.status_code}: {r.text}"
            return r.json()

        def query(self, fn):
            async def run():
                async with Session() as s:
                    return await fn(s)
            return asyncio.run(run())

        headers = {n: {"Authorization": f"Bearer {t}"} for n, t in tokens.items()}

    yield Env()
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


PROXIMATE = {"moisture": 11.0, "ash": 18.0, "volatile_matter": 66.0, "fixed_carbon": 16.0, "contamination": 1.0}


def report(env, farmer="petani_a", kg=100.0, **extra):
    return env.ok(farmer, "POST", "/farmer/harvest", {"quantity_kg": kg, **extra}, status=201)


def to_collected(env, farmer="petani_a", reported_kg=100.0, weighed_kg=100.0):
    """Lapor → timbang pengepul → dispatch → supir angkut. Mengembalikan harvest_id."""
    h = report(env, farmer, reported_kg)
    env.ok("pengepul_b", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": weighed_kg, **PROXIMATE})
    route = env.ok("pabrik_d", "POST", "/factory/dispatch",
                   {"driver_id": env.user_ids["supir_c"], "harvest_ids": [h["id"]]}, status=201)
    env.ok("supir_c", "POST", f"/driver/start-route?route_id={route['route_id']}")
    env.ok("supir_c", "POST", "/driver/confirm-pickup",
           {"route_stop_id": route["stops"][0]["route_stop_id"], "qr_code": h["qr_code"], "actual_ton": 0.1})
    return h["id"], route


# ---------------------------------------------------------------- siklus utuh
def test_full_circular_cycle_100kg_to_10kg_biochar(env):
    # 1. Petani A lapor 100 kg
    h = report(env, kg=100)
    assert h["status"] == "reported"

    # 2. Pengepul B timbang & uji mutu
    v = env.ok("pengepul_b", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 100, **PROXIMATE})
    assert v["weighed_kg"] == 100 and v["grade"] in {"A", "B", "C"}
    assert v["total_price"] == round(100 * 400 * v["quality_detail"]["price_multiplier"])

    # 3. Supir C mengangkut
    route = env.ok("pabrik_d", "POST", "/factory/dispatch",
                   {"driver_id": env.user_ids["supir_c"], "harvest_ids": [h["id"]]}, status=201)
    env.ok("supir_c", "POST", f"/driver/start-route?route_id={route['route_id']}")
    stop_id = route["stops"][0]["route_stop_id"]
    p = env.ok("supir_c", "POST", "/driver/confirm-pickup",
               {"route_stop_id": stop_id, "qr_code": h["qr_code"], "actual_ton": 0.1})
    assert p["already_confirmed"] is False
    env.ok("supir_c", "POST", f"/driver/complete-route?route_id={route['route_id']}")

    # 4. Pabrik D terima 95 kg → susut 5 kg (5%, tepat di batas toleransi → tidak ditandai)
    rcv = env.ok("pabrik_d", "POST", "/factory/receive", {"harvest_id": h["id"], "received_kg": 95})
    assert rcv["shrinkage_kg"] == 5 and rcv["shrinkage_pct"] == 5 and rcv["discrepancy_flag"] is False

    # 5. Batch pirolisis menghasilkan 10 kg biochar
    conv = env.ok("pabrik_d", "POST", "/factory/conversions",
                  {"batch_code": "E2E-001", "harvest_ids": [h["id"]], "biochar_kg": 10}, status=201)
    assert conv["allocated_kg"] == 10 and conv["allocations"][0]["biochar_kg"] == 10
    assert conv["yield_pct"] == pytest.approx(10 / 95 * 100, abs=1e-3)

    # 6. Dompet Petani A = 10 kg
    wallet = env.ok("petani_a", "GET", "/farmer/wallet")
    assert wallet["balance_kg"] == 10 and wallet["entries"][0]["harvest_id"] == h["id"]
    assert env.ok("petani_b", "GET", "/farmer/wallet")["balance_kg"] == 0

    # Jejak lengkap dapat diaudit
    mb = env.ok("auditor", "GET", f"/auditor/mass-balance/{h['id']}")
    assert mb["status"] == "converted"
    assert mb["weights_kg"] == {"farmer_estimate": 100, "collector_scale": 100, "driver_note": 100,
                                "factory_scale": 95}
    assert [e["stage"] for e in mb["custody_trail"]] == [
        "farmer_report", "collector_weigh", "driver_pickup", "factory_receive", "conversion"]
    assert mb["biochar_allocated_kg"] == 10
    summary = env.ok("auditor", "GET", "/auditor/summary")
    assert summary["total_shrinkage_kg"] == 5 and summary["biochar_allocated_to_farmers_kg"] == 10


def test_allocation_is_proportional_and_exact_to_the_gram(env):
    a, _ = to_collected(env, "petani_a", 100, 100)
    b, _ = to_collected(env, "petani_b", 50, 50)
    c, _ = to_collected(env, "petani_a", 33, 33)
    for hid, kg in ((a, 95), (b, 47.5), (c, 31.4)):
        env.ok("pabrik_d", "POST", "/factory/receive", {"harvest_id": hid, "received_kg": kg})
    conv = env.ok("pabrik_d", "POST", "/factory/conversions",
                  {"batch_code": "E2E-MIX", "harvest_ids": [a, b, c], "biochar_kg": 17.333}, status=201)
    assert round(sum(x["biochar_kg"] for x in conv["allocations"]), 3) == 17.333
    wa = env.ok("petani_a", "GET", "/farmer/wallet")["balance_kg"]
    wb = env.ok("petani_b", "GET", "/farmer/wallet")["balance_kg"]
    assert wa + wb == pytest.approx(17.333, abs=1e-9)
    assert wb == pytest.approx(17.333 * 47.5 / (95 + 47.5 + 31.4), abs=0.001)


# ---------------------------------------------------------------- diskrepansi timbangan
def test_shrinkage_beyond_tolerance_is_flagged_for_auditor(env):
    hid, _ = to_collected(env)
    rcv = env.ok("pabrik_d", "POST", "/factory/receive", {"harvest_id": hid, "received_kg": 90})
    assert rcv["discrepancy_flag"] is True and rcv["shrinkage_pct"] == 10
    disc = env.ok("auditor", "GET", "/auditor/discrepancies")["items"]
    assert [d["harvest_id"] for d in disc] == [hid]


def test_weight_gain_is_flagged(env):
    hid, _ = to_collected(env)
    rcv = env.ok("pabrik_d", "POST", "/factory/receive", {"harvest_id": hid, "received_kg": 112})
    assert rcv["discrepancy_flag"] is True and rcv["shrinkage_pct"] == -12


def test_price_uses_collector_scale_not_farmer_estimate(env):
    h = report(env, kg=500)                      # petani menaksir berlebihan
    v = env.ok("pengepul_b", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 320, **PROXIMATE})
    assert v["total_price"] == round(320 * 400 * v["quality_detail"]["price_multiplier"])
    assert v["estimate_gap_pct"] == pytest.approx(36.0)


# ---------------------------------------------------------------- RBAC
@pytest.mark.parametrize("who,method,path,body", [
    ("supir_c", "POST", "/factory/receive", {"harvest_id": 1, "received_kg": 1}),
    ("admin", "POST", "/factory/receive", {"harvest_id": 1, "received_kg": 1}),
    ("auditor", "POST", "/collector/verify", {"harvest_id": 1, "weighed_kg": 1, **PROXIMATE}),
    ("auditor", "POST", "/factory/conversions", {"batch_code": "X-1", "harvest_ids": [1], "biochar_kg": 1}),
    ("petani_a", "GET", "/auditor/summary", None),
    ("pengepul_b", "POST", "/factory/dispatch", {"driver_id": 1, "harvest_ids": [1]}),
])
def test_rbac_denies_out_of_role_actions(env, who, method, path, body):
    assert env.call(who, method, path, body).status_code == 403


def test_self_registration_cannot_create_admin_or_auditor(env):
    c = TestClient(app, raise_server_exceptions=False)
    for role in ("admin", "auditor"):
        r = c.post("/api/v1/auth/register", json={"phone": f"08999{role[:3]}01", "password": "abcdef12",
                                                    "full_name": "Penyusup", "role": role})
        assert r.status_code == 403


def test_driver_cannot_confirm_stop_on_another_drivers_route(env):
    h = report(env)
    env.ok("pengepul_b", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 100, **PROXIMATE})
    route = env.ok("pabrik_d", "POST", "/factory/dispatch",
                   {"driver_id": env.user_ids["supir_c"], "harvest_ids": [h["id"]]}, status=201)
    r = env.call("supir_lain", "POST", "/driver/confirm-pickup",
                 {"route_stop_id": route["stops"][0]["route_stop_id"], "qr_code": h["qr_code"]})
    assert r.status_code == 404


def test_route_cannot_complete_with_unscanned_stops(env):
    h = report(env)
    env.ok("pengepul_b", "POST", "/collector/verify", {"harvest_id": h["id"], "weighed_kg": 100, **PROXIMATE})
    route = env.ok("pabrik_d", "POST", "/factory/dispatch",
                   {"driver_id": env.user_ids["supir_c"], "harvest_ids": [h["id"]]}, status=201)
    env.ok("supir_c", "POST", f"/driver/start-route?route_id={route['route_id']}")
    assert env.call("supir_c", "POST", f"/driver/complete-route?route_id={route['route_id']}").status_code == 409


# ---------------------------------------------------------------- offline replay (idempotensi)
def test_offline_replay_does_not_duplicate(env):
    key = str(uuid.uuid4())
    first = report(env, kg=80, client_event_id=key, client_recorded_at="2026-10-01T06:00:00+07:00")
    again = report(env, kg=80, client_event_id=key, client_recorded_at="2026-10-01T06:00:00+07:00")
    assert again["id"] == first["id"] and again["replayed"] is True
    assert env.query(lambda s: _count(s, Harvest)) == 1

    vkey = str(uuid.uuid4())
    body = {"harvest_id": first["id"], "weighed_kg": 78, "client_event_id": vkey, **PROXIMATE}
    env.ok("pengepul_b", "POST", "/collector/verify", body)
    assert env.ok("pengepul_b", "POST", "/collector/verify", body)["replayed"] is True
    assert env.query(lambda s: _count(s, CustodyEvent)) == 2      # report + weigh, bukan 3


async def _count(s, model, *where):
    return (await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


# ---------------------------------------------------------------- race condition
def test_concurrent_receive_and_reject_exactly_one_wins(env):
    hid, _ = to_collected(env)

    async def race():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            h = env.headers["pabrik_d"]
            return await asyncio.gather(
                c.post("/api/v1/factory/receive", json={"harvest_id": hid, "received_kg": 95}, headers=h),
                c.post("/api/v1/factory/reject", json={"harvest_id": hid, "reason": "basah"}, headers=h),
            )

    codes = sorted(r.status_code for r in asyncio.run(race()))
    assert codes == [200, 409], codes
    final = env.ok("auditor", "GET", f"/auditor/mass-balance/{hid}")
    assert final["status"] in {"delivered", "rejected"}
    terminal = [e for e in final["custody_trail"] if e["stage"] in {"factory_receive", "factory_reject"}]
    assert len(terminal) == 1


def test_double_click_verify_is_rejected_not_double_paid(env):
    h = report(env)
    body = {"harvest_id": h["id"], "weighed_kg": 100, **PROXIMATE}
    env.ok("pengepul_b", "POST", "/collector/verify", body)
    assert env.call("pengepul_b", "POST", "/collector/verify", body).status_code == 409


# ---------------------------------------------------------------- ACID rollback
def test_allocation_failure_rolls_back_everything(env, monkeypatch):
    a, _ = to_collected(env, "petani_a")
    b, _ = to_collected(env, "petani_b")
    for hid in (a, b):
        env.ok("pabrik_d", "POST", "/factory/receive", {"harvest_id": hid, "received_kg": 95})

    real, calls = custody.BiocharLedgerEntry, {"n": 0}

    def flaky_ledger(**kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("ledger down")       # gagal setelah harvest pertama sudah CONVERTED
        return real(**kw)

    monkeypatch.setattr(custody, "BiocharLedgerEntry", flaky_ledger)
    r = env.call("pabrik_d", "POST", "/factory/conversions",
                 {"batch_code": "E2E-FAIL", "harvest_ids": [a, b], "biochar_kg": 10})
    assert r.status_code == 500
    monkeypatch.setattr(custody, "BiocharLedgerEntry", real)

    for hid in (a, b):
        assert env.ok("auditor", "GET", f"/auditor/mass-balance/{hid}")["status"] == "delivered"
    assert env.query(lambda s: _count(s, BiocharLedgerEntry)) == 0
    # Setelah gangguan pulih, batch yang sama bisa diulang dengan sukses
    env.ok("pabrik_d", "POST", "/factory/conversions",
           {"batch_code": "E2E-FAIL", "harvest_ids": [a, b], "biochar_kg": 10}, status=201)
    assert env.ok("petani_a", "GET", "/farmer/wallet")["balance_kg"] == 5


def test_conversion_rejects_harvest_not_yet_received(env):
    hid, _ = to_collected(env)
    r = env.call("pabrik_d", "POST", "/factory/conversions",
                 {"batch_code": "E2E-EARLY", "harvest_ids": [hid], "biochar_kg": 5})
    assert r.status_code == 409
