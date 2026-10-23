"""Regresi audit kesiapan produksi 23 Okt 2026 (docs/29): isolasi notifikasi, tabrakan login HP/username,
PDP di dashboard penawaran pengepul, /readyz tanpa detail DB, KeyError bukan 404, batas model AI."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import demo_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _phone() -> str:
    return "0858" + str(uuid.uuid4().int)[:8]


def _register_petani(client, phone: str, **kw) -> dict:
    body = {"phone": phone, "password": "rahasia-123", "full_name": "Petani Uji", "role": "petani", **kw}
    return client.post("/api/v1/auth/register", json=body)


def _login(client, ident: str, pw: str = "rahasia-123") -> dict:
    r = client.post("/api/v1/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------ notifikasi bertuan tidak bocor
def test_owned_notifications_not_visible_to_same_role(client):
    pa, pb = _phone(), _phone()
    assert _register_petani(client, pa).status_code == 201
    assert _register_petani(client, pb).status_code == 201
    ha, hb = _login(client, pa), _login(client, pb)
    r = client.post("/api/v1/farmer/harvest", headers=ha, json={"quantity_kg": 777})
    assert r.status_code == 201, r.text
    hid = r.json()["id"]

    def titles(h):
        return [it["title"] for it in client.get("/api/v1/notifications/", headers=h, params={"limit": 200}).json()["items"]]

    assert any(f"#{hid}" in t for t in titles(ha)), "pemilik melihat notifikasinya"
    assert not any(f"#{hid}" in t for t in titles(hb)), "petani lain tidak boleh melihat laporan petani A"

    own = next(it for it in client.get("/api/v1/notifications/", headers=ha, params={"limit": 200}).json()["items"]
               if f"#{hid}" in it["title"])
    # petani B tidak bisa menandai notifikasi milik A
    client.post(f"/api/v1/notifications/{own['id']}/read", headers=hb)
    still = next(it for it in client.get("/api/v1/notifications/", headers=ha, params={"limit": 200}).json()["items"]
                 if it["id"] == own["id"])
    assert still["is_read"] is False


# ------------------------------------------------------------------ login HP vs username
def test_username_cannot_be_a_phone_number(client):
    victim = _phone()
    assert _register_petani(client, victim).status_code == 201
    r = _register_petani(client, _phone(), username=victim)
    assert r.status_code == 422, r.text
    assert client.post("/api/v1/auth/login",
                       json={"identifier": victim, "password": "rahasia-123"}).status_code == 200


# ------------------------------------------------------------------ PDP dashboard penawaran
def test_offers_dashboard_masks_farmer_phone(client):
    hp = demo_headers(client, "pengepul")
    r = client.get("/api/v1/collector/offers-dashboard", headers=hp)
    assert r.status_code == 200, r.text
    rows = [it for v in r.json().values() if isinstance(v, list) for it in v if isinstance(it, dict)]
    phones = [it["farmer_phone"] for it in rows if it.get("farmer_phone") not in (None, "-")]
    assert phones, "data demo memuat petani ber-HP"
    assert all("*" in p for p in phones), phones[:3]
    for it in rows:
        if it.get("farmer_lat") is not None:
            assert round(it["farmer_lat"], 2) == it["farmer_lat"]


# ------------------------------------------------------------------ permukaan publik & error
def test_readyz_does_not_echo_db_error(client, monkeypatch):
    import app.database as db_module

    class Boom:
        def connect(self):
            raise OSError("connect to db.internal-host:5432 as biochain_app failed")

    monkeypatch.setattr(db_module, "engine", Boom())
    r = client.get("/readyz")
    assert r.status_code == 503
    assert "internal-host" not in r.text and "biochain_app" not in r.text


def test_keyerror_is_500_not_404(client):
    from app.main import _not_found

    class Req:
        method, url = "GET", type("U", (), {"path": "/x"})()

    import asyncio
    res = asyncio.run(_not_found(Req(), KeyError("secret_internal_key")))
    assert res.status_code == 500 and b"secret_internal_key" not in res.body
    res = asyncio.run(_not_found(Req(), LookupError("Panen tidak ditemukan")))
    assert res.status_code == 404


def test_non_admin_cannot_pick_arbitrary_ai_model(client):
    from app.ai import providers as P
    from app.models.user import User, UserRole
    from app.routers.assistant import _pick_model

    p = next(iter(P.PROVIDERS.values()))
    petani = User(role=UserRole.PETANI)
    admin = User(role=UserRole.ADMIN)
    assert _pick_model(p, None, petani) == P.default_model(p)
    with pytest.raises(P.AssistantError):
        _pick_model(p, "model-mahal-xl", petani)
    assert _pick_model(p, "model-mahal-xl", admin) == "model-mahal-xl"


# ------------------------------------------------------------------ usulan biomassa non-operator dibatasi
def test_farmer_biomass_proposal_is_bounded_and_lab_fields_ignored(client):
    hp = demo_headers(client, "petani")
    name = f"Kulit Uji {uuid.uuid4().hex[:6]}"
    r = client.post("/api/v1/biomass", headers=hp, json={"name": name, "base_price_per_kg": 10_000_000})
    assert r.status_code == 422, r.text
    r = client.post("/api/v1/biomass", headers=hp, json={"name": name, "moisture_reject_pct": 80})
    assert r.status_code == 422, r.text
    r = client.post("/api/v1/biomass", headers=hp, json={"name": name, "ash_pct_db": 59, "lhv_db_mj_kg": 30})
    assert r.status_code == 201, r.text
    assert r.json()["ash_pct_db"] != 59, "parameter lab dari petani diabaikan"


# ------------------------------------------------------------------ status baca siaran per pengguna
def test_broadcast_read_state_is_per_user(client):
    pa, pb = _phone(), _phone()
    assert _register_petani(client, pa).status_code == 201
    assert _register_petani(client, pb).status_code == 201
    ha, hb = _login(client, pa), _login(client, pb)

    def unread(h):
        return {it["id"] for it in client.get("/api/v1/notifications/", headers=h, params={"limit": 200}).json()["items"]
                if not it["is_read"]}

    before_b = unread(hb)
    assert before_b, "petani melihat notifikasi siaran peran petani (seed)"
    nid = next(iter(before_b & unread(ha)))
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=ha).status_code == 200
    assert nid not in unread(ha), "A sudah membaca"
    assert nid in unread(hb), "membaca siaran oleh A tidak menandai milik B"
    assert client.post("/api/v1/notifications/read-all", headers=hb).status_code == 200
    assert unread(hb) == set()
