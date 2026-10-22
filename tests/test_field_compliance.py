"""Kepatuhan lapangan: F7 petani tanpa HP, F8 bukti bayar petani (NUMERIC), F12 UU PDP, F6 wajib ganti password,
F10 (lihat test_uploads), F17 Request-ID."""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app import params
from app.main import app
from tests.conftest import demo_headers

VERIFY = dict(moisture=11.0, ash=18.0, volatile_matter=65.0, fixed_carbon=16.0, contamination=1.0)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _phone():
    return "0857" + str(uuid.uuid4().int)[:8]


def _login(client, ident, pw):
    r = client.post("/api/v1/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _second_collector(client):
    phone = _phone()
    r = client.post("/api/v1/admin/users", headers=demo_headers(client, "admin"),
                    json={"phone": phone, "password": "kud-lain-123", "full_name": "KUD Lain", "role": "pengepul"})
    assert r.status_code == 201, r.text
    return _login(client, phone, "kud-lain-123")[0]


def _proxy_farmer(client, hdr, **kw):
    body = {"full_name": "Mbah Karto", "desa": "Sidoarum", "kecamatan": "Godean", "consent_given": True, **kw}
    return client.post("/api/v1/collector/proxy-farmers", headers=hdr, json=body)


# ------------------------------------------------------------------ F7 petani tanpa HP
def test_proxy_farmer_requires_consent_and_cannot_login(client):
    hp = demo_headers(client, "pengepul")
    assert _proxy_farmer(client, hp, consent_given=False).status_code == 422
    r = _proxy_farmer(client, hp)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["phone"] is None and "Sidoarum" in f["full_name"]
    assert any(x["id"] == f["id"] for x in client.get("/api/v1/collector/proxy-farmers", headers=hp).json())
    # akun proxy tidak bisa login (tanpa nomor HP sah & password acak)
    assert client.post("/api/v1/auth/login", json={"identifier": f["full_name"], "password": "x"}).status_code == 401


def test_proxy_harvest_only_for_own_farmers_and_idempotent(client):
    hp = demo_headers(client, "pengepul")
    fid = _proxy_farmer(client, hp).json()["id"]
    ev = str(uuid.uuid4())
    body = {"farmer_id": fid, "quantity_kg": 1250, "client_event_id": ev}
    r1 = client.post("/api/v1/collector/proxy-harvest", headers=hp, json=body)
    assert r1.status_code == 201 and r1.json()["qr_code"].startswith("BIO-") and r1.json()["replayed"] is False
    r2 = client.post("/api/v1/collector/proxy-harvest", headers=hp, json=body)
    assert r2.json()["replayed"] is True and r2.json()["id"] == r1.json()["id"], "kirim ulang offline tidak menggandakan"
    other = _second_collector(client)
    assert client.post("/api/v1/collector/proxy-harvest", headers=other,
                       json={"farmer_id": fid, "quantity_kg": 100}).status_code == 403
    # akun petani mandiri (bukan binaan) juga ditolak
    petani_id = client.get("/api/v1/auth/me", headers=demo_headers(client, "petani")).json()["user_id"]
    assert client.post("/api/v1/collector/proxy-harvest", headers=hp,
                       json={"farmer_id": petani_id, "quantity_kg": 100}).status_code == 403


# ------------------------------------------------------------------ F12 minimisasi nomor HP
def test_available_harvests_mask_phone_and_contact_reveals(client):
    hp = demo_headers(client, "pengepul")
    rows = client.get("/api/v1/collector/available-harvests", headers=hp).json()
    rows = rows if isinstance(rows, list) else rows.get("items", [])
    with_phone = [r for r in rows if r.get("farmer_phone")]
    assert with_phone, "seed punya laporan petani ber-HP"
    assert all("*" in r["farmer_phone"] for r in with_phone), "nomor disamarkan di daftar lintas-pengguna"
    c = client.get(f"/api/v1/collector/harvests/{with_phone[0]['id']}/contact", headers=hp)
    assert c.status_code == 200 and re.fullmatch(r"08\d{8,11}", c.json()["phone"])


# ------------------------------------------------------------------ F8 bukti bayar petani
def _verified_lot(client, hp, qty=2000, weighed=1980):
    fid = _proxy_farmer(client, hp).json()["id"]
    hid = client.post("/api/v1/collector/proxy-harvest", headers=hp,
                      json={"farmer_id": fid, "quantity_kg": qty}).json()["id"]
    v = client.post("/api/v1/collector/verify", headers=hp, json={"harvest_id": hid, "weighed_kg": weighed, **VERIFY})
    assert v.status_code == 200, v.text
    return hid, v.json()["total_price"], fid


def test_pay_farmer_receipt_numeric_and_rules(client, monkeypatch):
    hp = demo_headers(client, "pengepul")
    hid, total, _ = _verified_lot(client, hp)
    unpaid = client.get("/api/v1/collector/unpaid-harvests", headers=hp).json()
    row = next(u for u in unpaid if u["harvest_id"] == hid)
    assert row["amount_rp"] == int(round(total))
    # non-tunai wajib referensi
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hp,
                       json={"method": "transfer"}).status_code == 422
    # pengepul lain tidak boleh mencatat: 403 (cek aplikasi, SQLite) atau 404 (PostgreSQL RLS menyembunyikan lot)
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=_second_collector(client),
                       json={"method": "tunai"}).status_code in (403, 404)
    monkeypatch.setitem(params._values, "pajak.pph22_farmer_pct", 0.25)
    ev = str(uuid.uuid4())
    r = client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hp,
                    json={"method": "qris", "reference": "QR-778899", "client_event_id": ev})
    assert r.status_code == 201, r.text
    p = r.json()
    assert re.fullmatch(r"BYR-PGP\d{4}-PTN\d{4}-\d{4}-\d{5}", p["receipt_code"])
    assert isinstance(p["gross_rp"], int) and p["gross_rp"] == int(round(total))
    assert p["tax_rp"] == round(p["gross_rp"] * 0.0025) and p["net_rp"] == p["gross_rp"] - p["tax_rp"]
    # kirim ulang (antrean offline) → kuitansi sama; bayar dobel → 409
    again = client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hp,
                        json={"method": "qris", "reference": "QR-778899", "client_event_id": ev})
    assert again.json()["replayed"] is True and again.json()["receipt_code"] == p["receipt_code"]
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hp,
                       json={"method": "tunai"}).status_code == 409
    assert hid not in {u["harvest_id"] for u in client.get("/api/v1/collector/unpaid-harvests", headers=hp).json()}


def test_farmer_sees_own_payments(client):
    hp = demo_headers(client, "pengepul")
    petani_hdr = demo_headers(client, "petani")
    rows = client.get("/api/v1/farmer/payments", headers=petani_hdr)
    assert rows.status_code == 200 and isinstance(rows.json(), list)
    assert client.get("/api/v1/farmer/payments", headers=hp).status_code == 403


def test_cannot_pay_unverified_lot(client):
    hp = demo_headers(client, "pengepul")
    fid = _proxy_farmer(client, hp).json()["id"]
    hid = client.post("/api/v1/collector/proxy-harvest", headers=hp, json={"farmer_id": fid, "quantity_kg": 500}).json()["id"]
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hp,
                       json={"method": "tunai"}).status_code == 409          # belum ditimbang → belum ada nilai


# ------------------------------------------------------------------ F12 hak subjek data
def test_consents_export_and_delete(client):
    phone = _phone()
    r = client.post("/api/v1/auth/register", json={"phone": phone, "password": "pdp-uji-123", "full_name": "Petani PDP",
                                                   "role": "petani", "consents": {"layanan_inti": True, "lokasi_gps": False}})
    assert r.status_code == 201, r.text
    hdr, _ = _login(client, phone, "pdp-uji-123")
    c = client.get("/api/v1/me/consents", headers=hdr).json()
    by = {p["purpose"]: p for p in c["purposes"]}
    assert c["needs_consent"] is False and by["layanan_inti"]["granted"] and by["lokasi_gps"]["granted"] is False
    assert client.post("/api/v1/me/consents", headers=hdr, json={"choices": {"layanan_inti": False}}).status_code == 422
    assert client.post("/api/v1/me/consents", headers=hdr,
                       json={"choices": {"foto_bukti": True}}).json()["purposes"][2]["granted"] is True
    client.post("/api/v1/farmer/harvest", headers=hdr, json={"quantity_kg": 800})
    ex = client.get("/api/v1/me/data-export", headers=hdr)
    assert ex.status_code == 200 and "attachment" in ex.headers["content-disposition"]
    data = ex.json()
    assert data["profile"]["phone"] == phone and len(data["harvests"]) == 1 and data["receipt_code"].startswith("PDP-EKS")
    assert client.post("/api/v1/me/delete", headers=hdr, json={"password": "salah"}).status_code == 401
    d = client.post("/api/v1/me/delete", headers=hdr, json={"password": "pdp-uji-123", "reason": "uji"})
    assert d.status_code == 200 and d.json()["receipt_code"].startswith("PDP-HAP")
    assert client.post("/api/v1/auth/login", json={"identifier": phone, "password": "pdp-uji-123"}).status_code == 401
    # Regresi: lot milik akun terhapus tetap ada, tetapi penanda nomor (DEL-…) tidak bocor sebagai "nomor HP"
    hid = data["harvests"][0]["id"]
    contact = client.get(f"/api/v1/collector/harvests/{hid}/contact", headers=demo_headers(client, "pengepul")).json()
    assert contact["phone"] is None and contact["without_phone"] is True
    assert contact["farmer_name"].startswith("Pengguna terhapus")
    # nomor HP bebas dipakai lagi (identitas lama benar-benar terhapus)
    assert client.post("/api/v1/auth/register", json={"phone": phone, "password": "baru-12345", "full_name": "Baru",
                                                      "role": "petani"}).status_code == 201


def test_register_rejects_missing_core_consent(client):
    r = client.post("/api/v1/auth/register", json={"phone": _phone(), "password": "rahasia123", "full_name": "Tolak",
                                                   "role": "petani", "consents": {"layanan_inti": False}})
    assert r.status_code == 422


# ------------------------------------------------------------------ F6 wajib ganti password
def test_reset_forces_password_change(client):
    phone = _phone()
    uid = client.post("/api/v1/auth/register", json={"phone": phone, "password": "awal-12345", "full_name": "Lupa",
                                                     "role": "petani"}).json()["user_id"]
    temp = client.post(f"/api/v1/admin/users/{uid}/reset-password", headers=demo_headers(client, "admin")).json()["temporary_password"]
    hdr, body = _login(client, phone, temp)
    assert body["must_change_password"] is True
    assert client.get("/api/v1/auth/me", headers=hdr).json()["must_change_password"] is True
    assert client.post("/api/v1/auth/change-password", headers=hdr,
                       json={"old_password": "keliru", "new_password": "baru-12345"}).status_code == 401
    assert client.post("/api/v1/auth/change-password", headers=hdr,
                       json={"old_password": temp, "new_password": "baru-12345"}).status_code == 200
    _, body2 = _login(client, phone, "baru-12345")
    assert body2["must_change_password"] is False


# ------------------------------------------------------------------ F17 Request-ID
def test_request_id_header(client):
    r = client.get("/api/v1/system/status", headers={"X-Request-ID": "lapangan-abc12345"})
    assert r.headers["x-request-id"] == "lapangan-abc12345"
    assert len(client.get("/api/v1/system/status").headers["x-request-id"]) == 16
    bad = client.get("/api/v1/system/status", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"


# ------------------------------------------------------------------ F9 uji lapangan cukup kadar air
def test_verify_with_moisture_only_marks_unmeasured(client):
    hp = demo_headers(client, "pengepul")
    fid = _proxy_farmer(client, hp).json()["id"]
    hid = client.post("/api/v1/collector/proxy-harvest", headers=hp, json={"farmer_id": fid, "quantity_kg": 900}).json()["id"]
    r = client.post("/api/v1/collector/verify", headers=hp, json={"harvest_id": hid, "weighed_kg": 880, "moisture": 11.0})
    assert r.status_code == 200, r.text
    q = r.json()["quality_detail"]
    assert q["proximate_measured"] is False and any("tidak diukur" in w for w in q["warnings"])
    assert set(q["components"]) == {"kadar_air", "kontaminasi"} and r.json()["grade"] in ("A", "B", "C")
    assert r.json()["total_price"] > 0
    # dengan uji lab lengkap → terukur, tanpa peringatan proksimat
    hid2 = client.post("/api/v1/collector/proxy-harvest", headers=hp, json={"farmer_id": fid, "quantity_kg": 900}).json()["id"]
    r2 = client.post("/api/v1/collector/verify", headers=hp, json={"harvest_id": hid2, "weighed_kg": 880, **VERIFY})
    assert r2.json()["quality_detail"]["proximate_measured"] is True
