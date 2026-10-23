"""Demo publik (PUBLIC_DEMO): pengunjung tidak bisa menjadi admin atau merusak akun demo bersama."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.conftest import demo_headers


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def public_demo(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_DEMO", True)


def test_admin_hidden_from_login_page(client, public_demo):
    accounts = client.get("/api/v1/auth/demo-accounts").json()
    assert accounts and all(a["role"] != "admin" for a in accounts)
    assert "admin2026" not in str(accounts)


def test_admin_listed_on_laptop_demo(client):
    assert any(a["role"] == "admin" for a in client.get("/api/v1/auth/demo-accounts").json())


def test_reset_and_reseed_disabled(client, public_demo):
    admin = demo_headers(client, "admin")
    assert client.post("/api/v1/auth/reset-demo", headers=admin).status_code == 403
    assert client.post("/api/v1/admin/seed-demo-data", headers=admin).status_code == 403


def test_shared_demo_account_cannot_change_password_or_delete(client, public_demo):
    petani = demo_headers(client, "petani")
    r = client.post("/api/v1/auth/change-password", headers=petani,
                    json={"old_password": "x" * 8, "new_password": "y" * 10})
    assert r.status_code == 403 and "akun demo bersama" in r.json()["detail"]
    r = client.post("/api/v1/me/delete", headers=petani, json={"password": "x" * 8, "reason": "uji"})
    assert r.status_code == 403


def test_demo_admin_password_from_env(monkeypatch):
    from app.security.demo_guard import demo_password
    from app.seed import DEMO_ACCOUNTS
    admin = next(a for a in DEMO_ACCOUNTS if a["role"] == "admin")
    petani = next(a for a in DEMO_ACCOUNTS if a["role"] == "petani")
    monkeypatch.setattr(settings, "DEMO_ADMIN_PASSWORD", "rahasia-panjang-123")
    assert demo_password(admin) == "rahasia-panjang-123"
    assert demo_password(petani) == petani["password"]


def test_public_demo_refuses_to_start_without_strong_admin_password():
    from pydantic import ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError, match="DEMO_ADMIN_PASSWORD"):
        Settings(PUBLIC_DEMO=True, DEMO_ADMIN_PASSWORD="")
    with pytest.raises(ValidationError, match="DEMO_ADMIN_PASSWORD"):
        Settings(PUBLIC_DEMO=True, DEMO_ADMIN_PASSWORD="admin2026")
    assert Settings(PUBLIC_DEMO=True, DEMO_ADMIN_PASSWORD="x" * 20).PUBLIC_DEMO
