"""Penguatan hasil audit 5 fase (Okt 2026): pencabutan token saat ganti/reset password, must_change_password di
server, kapasitas truk m³ & kg, uang muka (DP) petani, dedup foto bukti, aliran bio-oil di neraca massa."""

import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import demo_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, ident, pw):
    r = client.post("/api/v1/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _new_user(client, role="petani", pw="awal-123"):
    phone = "0858" + str(uuid.uuid4().int)[:8]
    r = client.post("/api/v1/admin/users", headers=demo_headers(client, "admin"),
                    json={"phone": phone, "password": pw, "full_name": f"Uji {role}", "role": role})
    assert r.status_code == 201, r.text
    return phone, r.json()


# ------------------------------------------------------------------ token & password
def test_change_password_revokes_old_tokens_and_returns_new_one(client):
    phone, _ = _new_user(client)
    old_hdr, _ = _login(client, phone, "awal-123")
    other_device, _ = _login(client, phone, "awal-123")
    r = client.post("/api/v1/auth/change-password", headers=old_hdr,
                    json={"old_password": "awal-123", "new_password": "baru-456"})
    assert r.status_code == 200, r.text
    new_hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=other_device).status_code == 401      # HP lain otomatis keluar
    assert client.get("/api/v1/auth/me", headers=old_hdr).status_code == 401
    assert client.get("/api/v1/auth/me", headers=new_hdr).status_code == 200


def test_admin_reset_revokes_and_must_change_is_enforced_server_side(client):
    phone, u = _new_user(client)
    hdr, _ = _login(client, phone, "awal-123")
    rr = client.post(f"/api/v1/admin/users/{u['id']}/reset-password", headers=demo_headers(client, "admin"))
    assert rr.status_code == 200, rr.text
    assert client.get("/api/v1/farmer/wallet", headers=hdr).status_code == 401           # token sebelum reset mati
    tmp_hdr, body = _login(client, phone, rr.json()["temporary_password"])
    assert body["must_change_password"] is True
    assert client.get("/api/v1/farmer/wallet", headers=tmp_hdr).status_code == 403       # wajib ganti dulu (server)
    assert client.get("/api/v1/auth/me", headers=tmp_hdr).status_code == 200
    r = client.post("/api/v1/auth/change-password", headers=tmp_hdr,
                    json={"old_password": rr.json()["temporary_password"], "new_password": "aman-789"})
    ok_hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/farmer/wallet", headers=ok_hdr).status_code == 200


def test_admin_user_validation_rejects_blank_and_bad_role(client):
    ha = demo_headers(client, "admin")
    base = {"phone": "0858" + str(uuid.uuid4().int)[:8], "password": "rahasia-1", "full_name": "Uji", "role": "petani"}
    assert client.post("/api/v1/admin/users", headers=ha, json={**base, "full_name": "   "}).status_code == 422
    assert client.post("/api/v1/admin/users", headers=ha, json={**base, "role": "superadmin"}).status_code == 422
    assert client.post("/api/v1/admin/users", headers=ha, json={**base, "password": "1234"}).status_code == 422


# ------------------------------------------------------------------ kapasitas truk
def _verified_harvest(client, kg):
    hp, hc = demo_headers(client, "petani"), demo_headers(client, "pengepul")
    mills = client.get("/api/v1/farmer/mills", headers=hp).json()
    hid = client.post("/api/v1/farmer/harvest", headers=hp,
                      json={"quantity_kg": kg, "mill_id": mills[0]["id"]}).json()["id"]
    v = client.post("/api/v1/collector/verify", headers=hc, json={"harvest_id": hid, "weighed_kg": kg, "moisture": 11.0})
    assert v.status_code == 200, v.text
    return hid


def test_dispatch_rejects_volume_or_weight_over_capacity(client):
    hf = demo_headers(client, "pabrik")
    driver_id = _login(client, "sopir_budi", "truk2026")[1]["user_id"]
    hid = _verified_harvest(client, 1200)                               # 1.200 kg ÷ 110 kg/m³ ≈ 10,9 m³
    r = client.post("/api/v1/factory/dispatch", headers=hf, json={"driver_id": driver_id, "harvest_ids": [hid],
                                                                  "vehicle_m3": 6})
    assert r.status_code == 422 and "volume" in r.json()["detail"]
    r = client.post("/api/v1/factory/dispatch", headers=hf, json={"driver_id": driver_id, "harvest_ids": [hid],
                                                                  "vehicle_m3": 30, "vehicle_payload_kg": 800})
    assert r.status_code == 422 and "berat" in r.json()["detail"]
    ok = client.post("/api/v1/factory/dispatch", headers=hf, json={"driver_id": driver_id, "harvest_ids": [hid],
                                                                   "vehicle_m3": 30})
    assert ok.status_code == 201, ok.text


# ------------------------------------------------------------------ uang muka (DP)
def test_down_payment_capped_once_and_netted_at_payment(client):
    hc, hp = demo_headers(client, "pengepul"), demo_headers(client, "petani")
    hid = _verified_harvest(client, 1000)
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc,
                       json={"amount_rp": 10_000_000, "method": "tunai"}).status_code == 422      # > batas %
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc,
                       json={"amount_rp": 50_000, "method": "transfer"}).status_code == 422        # tanpa referensi
    dp = client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc, json={"amount_rp": 50_000, "method": "tunai"})
    assert dp.status_code == 201, dp.text
    assert dp.json()["receipt_code"].startswith("DP-") and dp.json()["status"] == "aktif"
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc,
                       json={"amount_rp": 10_000, "method": "tunai"}).status_code == 409           # satu DP per lot
    o = client.get("/api/v1/farmer/payments/overview", headers=hp).json()
    w = next(x for x in o["waiting"]["items"] if x["harvest_id"] == hid)
    assert w["dp_rp"] == 50_000 and w["net_rp"] == w["gross_rp"] - 50_000
    pay = client.post(f"/api/v1/collector/harvests/{hid}/pay-farmer", headers=hc, json={"method": "tunai"}).json()
    assert pay["dp_rp"] == 50_000 and pay["net_rp"] == pay["gross_rp"] - pay["tax_rp"] - 50_000
    o2 = client.get("/api/v1/farmer/payments/overview", headers=hp).json()
    assert any(d["harvest_id"] == hid and d["status"] == "dipotong" for d in o2["down_payments"])
    # pengepul lain / petani tidak bisa mencatat DP lot ini
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hp,
                       json={"amount_rp": 1000, "method": "tunai"}).status_code == 403


# ------------------------------------------------------------------ foto bukti & BOM
def _jpeg(seed: int) -> bytes:
    """Gambar unik per seed: folder upload bertahan antar-run, jadi 250 warna polos cepat bertabrakan (tes flaky)."""
    from PIL import Image
    img = Image.new("RGB", (64, 48), (seed % 255, 120, 30))
    px = img.load()
    for i, byte in enumerate(seed.to_bytes(16, "big")):           # pola piksel dari 128-bit seed
        px[i % 64, i // 64] = (byte, 255 - byte, (byte * 7) % 256)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def test_upload_same_photo_is_flagged_duplicate(client):
    hp = demo_headers(client, "petani")
    data = _jpeg(uuid.uuid4().int)
    a = client.post("/api/v1/uploads", headers=hp, files={"file": ("a.jpg", data, "image/jpeg")})
    b = client.post("/api/v1/uploads", headers=hp, files={"file": ("b.jpg", data, "image/jpeg")})
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["duplicate"] is False and b.json()["duplicate"] is True
    assert a.json()["url"] == b.json()["url"] and len(a.json()["sha256"]) == 64


def test_bio_oil_is_a_mass_balance_stream():
    from app.engines.factory_econ import LOSS_KINDS
    assert "bio_oil" in LOSS_KINDS


# ------------------------------------------------------------------ DP langsung setelah lelang diterima
def test_auction_dp_shown_in_queue_and_forfeited_to_farmer_on_unilateral_cancel(client):
    hp, hc = demo_headers(client, "petani"), demo_headers(client, "pengepul")
    lst = client.post("/api/v1/farmer/listings", headers=hp,
                      json={"quantity_kg": 800, "allow_jemput": False, "allow_antar": True, "ask_price_antar": 400}).json()
    lid = lst.get("id") or lst.get("listing_id")
    bid = client.post("/api/v1/collector/bids", headers=hc, json={"listing_id": lid, "scheme": "antar",
                                                                  "price_per_kg": 450, "quantity_kg": 800})
    assert bid.status_code in (200, 201), bid.text
    bid_id = bid.json().get("id") or bid.json().get("bid_id")
    acc = client.post(f"/api/v1/farmer/listings/{lid}/accept", headers=hp, json={"bid_id": bid_id, "quantity_kg": 800})
    assert acc.status_code == 200, acc.text
    hid = acc.json()["harvest_id"]
    q = next(x for x in client.get("/api/v1/collector/available-harvests", headers=hc).json() if x["id"] == hid)
    assert q["is_auction"] is True and q["agreed_price_per_kg"] == 450 and q["dp"] is None
    # DP maks 30% × 450 × 800 = 108.000
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc,
                       json={"amount_rp": 120_000, "method": "tunai"}).status_code == 422
    assert client.post(f"/api/v1/collector/harvests/{hid}/pay-dp", headers=hc,
                       json={"amount_rp": 100_000, "method": "tunai"}).status_code == 201
    q2 = next(x for x in client.get("/api/v1/collector/available-harvests", headers=hc).json() if x["id"] == hid)
    assert q2["dp"]["amount_rp"] == 100_000 and q2["dp"]["status"] == "aktif"
    c = client.post(f"/api/v1/collector/harvests/{hid}/cancel-purchase", headers=hc, json={"reason": "harga pabrik turun"})
    assert c.status_code == 200, c.text
    assert c.json()["down_payment"]["status"] == "hangus_untuk_petani" and "hak petani" in c.json()["message"]
    o = client.get("/api/v1/farmer/payments/overview", headers=hp).json()
    assert any(d["harvest_id"] == hid and d["status"] == "hangus_untuk_petani" for d in o["down_payments"])


# ------------------------------------------------------------------ CSP ketat
def test_csp_blocks_inline_scripts_and_page_has_no_inline_handlers(client):
    import re
    from pathlib import Path
    r = client.get("/")
    csp = r.headers.get("content-security-policy", "")
    script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src and "'sha256-" in script_src
    assert "object-src 'none'" in csp and "frame-ancestors 'self'" in csp
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert not re.search(r"\son(click|change|input|submit|load|error|key\w+|mouse\w+|focus|blur)=", html, re.I)
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    assert inline == ['<script type="importmap">']                   # satu-satunya, di-hash di CSP
    for js in ("app.js", "field-ops.js", "factory-ops.js", "ui-enhance.js"):
        src = Path(f"app/static/{js}").read_text(encoding="utf-8")
        assert not re.search(r"""\son(click|change|input|submit)=["']""", src), js     # template pun bebas handler inline
    assert "content-security-policy" not in {k.lower() for k in client.get("/docs").headers}  # Swagger dikecualikan
