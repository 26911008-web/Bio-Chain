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


def test_register_and_admin_user_management():
    import uuid
    suffix = str(uuid.uuid4().int)[:6]                  # digit saja: nomor HP kini divalidasi (F6)
    petani_phone = f"0899{suffix}"
    pengepul_phone = f"0888{suffix}"

    with TestClient(app) as c:
        # 1. Register Petani (langsung aktif)
        r = c.post("/api/v1/auth/register", json={
            "phone": petani_phone,
            "username": f"petani_{suffix}",
            "full_name": "Pak Tani Baru",
            "password": "password123",
            "role": "petani",
            "kecamatan": "Godean",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["role"] == "petani"
        assert "access_token" in data

        # Login sebagai Petani baru
        login_res = c.post("/api/v1/auth/login", json={
            "identifier": petani_phone,
            "password": "password123",
        })
        assert login_res.status_code == 200

        # 2. Register Pengepul (menunggu aktivasi admin)
        r2 = c.post("/api/v1/auth/register", json={
            "phone": pengepul_phone,
            "username": f"pengepul_{suffix}",
            "full_name": "KUD Baru",
            "password": "password123",
            "role": "pengepul",
            "kecamatan": "Sleman",
        })
        assert r2.status_code == 201
        pengepul_id = r2.json()["user_id"]

        # Sebelum diaktifkan, login ditolak
        unapproved_login = c.post("/api/v1/auth/login", json={
            "identifier": pengepul_phone,
            "password": "password123",
        })
        assert unapproved_login.status_code == 403

        # 3. Admin login & listing users
        admin_login = c.post("/api/v1/auth/login", json={"identifier": "admin", "password": "admin2026"})
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # List users (termasuk filter role)
        users_resp = c.get("/api/v1/admin/users?role=pengepul", headers=admin_headers)
        assert users_resp.status_code == 200
        pengepul_users = users_resp.json()
        assert any(u["id"] == pengepul_id for u in pengepul_users)

        # 4. Admin aktifkan user pengepul
        act_res = c.post(f"/api/v1/admin/users/{pengepul_id}/activate", headers=admin_headers)
        assert act_res.status_code == 200

        # Sekarang pengepul bisa login
        approved_login = c.post("/api/v1/auth/login", json={
            "identifier": pengepul_phone,
            "password": "password123",
        })
        assert approved_login.status_code == 200

        # 5. Admin toggle-active (nonaktifkan dan aktifkan kembali)
        toggle_res = c.post(f"/api/v1/admin/users/{pengepul_id}/toggle-active", headers=admin_headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_active"] is False

        toggle_res2 = c.post(f"/api/v1/admin/users/{pengepul_id}/toggle-active", headers=admin_headers)
        assert toggle_res2.status_code == 200
        assert toggle_res2.json()["is_active"] is True

        # 6. Admin membuat user langsung (contoh: Auditor atau Driver baru)
        driver_phone = f"0877{suffix}"
        create_res = c.post("/api/v1/admin/users", headers=admin_headers, json={
            "phone": driver_phone,
            "username": f"driver_{suffix}",
            "full_name": "Driver Cepat",
            "password": "password123",
            "role": "driver",
            "kecamatan": "Depok",
            "is_active": True,
        })
        assert create_res.status_code == 201
        created_data = create_res.json()
        assert created_data["role"] == "driver"
        assert created_data["is_active"] is True
