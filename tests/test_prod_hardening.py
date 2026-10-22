"""Hardening lapangan & produksi: F6 (nomor HP + reset password admin), F19 (CORS dari env),
F16 (job backend produksi), dan provider OpenAI (format API terbaru). Provider AI dimock."""

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import providers as P
from app.config import Settings, settings
from app.main import app
from app.services.phone import normalize_phone
from tests.conftest import demo_headers

PROD = dict(DEBUG=False, DEMO_MODE=False, ALLOW_SQLITE_FALLBACK=False, JWT_SECRET="x" * 40,
            DATABASE_URL="postgresql+asyncpg://u:p@localhost/db")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("raw,expected", [
    ("+62 812-3456-7890", "081234567890"), ("6281234567890", "081234567890"), ("0062 812 3456 7890", "081234567890"),
    ("0812 3456 7890", "081234567890"), ("(0812) 3456.7890", "081234567890"), ("81234567890", "081234567890"),
    ("021-555-1234", None), ("0812", None), ("08123456789012345", None), ("abc0812345678", None), ("", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def _fresh_phone() -> str:
    return "0857" + str(uuid.uuid4().int)[:8]


def test_register_with_plus62_then_login_with_local_format(client):
    local = _fresh_phone()
    intl = "+62 " + local[1:4] + "-" + local[4:8] + "-" + local[8:]
    r = client.post("/api/v1/auth/register", json={"phone": intl, "password": "rahasia123", "full_name": "Petani Uji HP",
                                                   "role": "petani"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["phone"] == local, "disimpan dalam bentuk kanonik 08…"
    for ident in (local, intl, "62" + local[1:]):
        lr = client.post("/api/v1/auth/login", json={"identifier": ident, "password": "rahasia123"})
        assert lr.status_code == 200, (ident, lr.text)


def test_register_rejects_non_mobile_number(client):
    r = client.post("/api/v1/auth/register", json={"phone": "021-555-1234", "password": "rahasia123",
                                                   "full_name": "Telepon Rumah", "role": "petani"})
    assert r.status_code == 422 and "Nomor HP tidak valid" in r.text


def test_admin_reset_password(client):
    phone = _fresh_phone()
    r = client.post("/api/v1/auth/register", json={"phone": phone, "password": "lama12345", "full_name": "Lupa Password",
                                                   "role": "petani"})
    uid = r.json()["user_id"]
    # bukan admin → ditolak
    assert client.post(f"/api/v1/admin/users/{uid}/reset-password",
                       headers=demo_headers(client, "pengepul")).status_code == 403
    rr = client.post(f"/api/v1/admin/users/{uid}/reset-password", headers=demo_headers(client, "admin"))
    assert rr.status_code == 200, rr.text
    temp = rr.json()["temporary_password"]
    assert len(temp) == 10 and not set(temp) & set("O0l1I")
    assert client.post("/api/v1/auth/login", json={"identifier": phone, "password": "lama12345"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": phone, "password": temp}).status_code == 200


def test_admin_cannot_reset_own_password_via_endpoint(client):
    me = client.get("/api/v1/auth/me", headers=demo_headers(client, "admin")).json()
    uid = me.get("user_id") or me.get("id")
    assert client.post(f"/api/v1/admin/users/{uid}/reset-password",
                       headers=demo_headers(client, "admin")).status_code == 400


@pytest.mark.parametrize("extra,msg", [
    ({}, "JOB_BACKEND=arq"),
    ({"JOB_BACKEND": "arq"}, "CORS_ORIGINS wajib"),
    ({"JOB_BACKEND": "arq", "CORS_ORIGINS": "*"}, "CORS_ORIGINS wajib"),
    ({"JOB_BACKEND": "arq", "CORS_ORIGINS": "http://biochain.id"}, "https://"),
])
def test_production_settings_rejected(extra, msg):
    with pytest.raises(ValueError, match=msg):
        Settings(**PROD, **extra)


def test_production_settings_accepted():
    s = Settings(**PROD, JOB_BACKEND="arq", CORS_ORIGINS="https://biochain.id, https://www.biochain.id/")
    assert s.cors_origins == ["https://biochain.id", "https://www.biochain.id"]
    s1 = Settings(**PROD, ALLOW_LOCAL_JOBS_IN_PROD=True, CORS_ORIGINS="https://biochain.id")
    assert s1.JOB_BACKEND == "local"


def test_dev_cors_defaults_to_localhost():
    assert "http://localhost:8000" in Settings(DEBUG=True, CORS_ORIGINS="").cors_origins


def test_openai_provider_uses_current_api_shape(client, monkeypatch):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append({"url": str(request.url), "auth": request.headers.get("authorization"), "body": body})
        return httpx.Response(200, json={"model": body["model"], "usage": {"total_tokens": 5},
                                         "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-uji")
    monkeypatch.setattr(P, "new_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    r = client.post("/api/v1/assistant/chat", headers=demo_headers(client, "petani"),
                    json={"message": "hai", "provider": "openai"})
    assert r.status_code == 200, r.text
    b = sent[-1]["body"]
    assert sent[-1]["url"].startswith("https://api.openai.com/v1/chat/completions")
    assert sent[-1]["auth"] == "Bearer sk-uji"
    assert "max_completion_tokens" in b and "max_tokens" not in b and "temperature" not in b
    assert b["model"] == settings.OPENAI_MODEL
    prov = client.get("/api/v1/assistant/providers", headers=demo_headers(client, "petani")).json()
    assert any(p["id"] == "openai" and p["configured"] for p in prov["providers"]) and "sk-uji" not in json.dumps(prov)
