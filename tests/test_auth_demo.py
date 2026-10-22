from fastapi.testclient import TestClient
from app.main import app


def test_system_status():
    with TestClient(app) as c:
        r = c.get("/api/v1/system/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["demo_ready"] is True


def test_demo_accounts_list():
    with TestClient(app) as c:
        r = c.get("/api/v1/auth/demo-accounts")
        assert r.status_code == 200
        accounts = r.json()
        assert len(accounts) >= 5
        roles = {a["role"] for a in accounts}
        assert "admin" in roles
        assert "pabrik" in roles
        assert "pengepul" in roles
        assert "driver" in roles
        assert "petani" in roles


def test_login_demo_admin():
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"identifier": "admin", "password": "admin2026"})
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "admin"
        assert "access_token" in data
        assert data["user_id"] > 0


def test_login_demo_petani_by_phone():
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"identifier": "081544556677", "password": "sekam123"})
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "petani"
        assert data["incentive_tier"] in ["mitra_emas", "pemula", "pemasok_aktif"]
        token = data["access_token"]

        # Call farmer profile / harvests
        h_resp = c.get("/api/v1/farmer/harvests", headers={"Authorization": f"Bearer {token}"})
        assert h_resp.status_code == 200
        harvests = h_resp.json()
        assert isinstance(harvests, list)


def test_login_invalid_password():
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"identifier": "admin", "password": "wrongpassword"})
        assert r.status_code == 401
