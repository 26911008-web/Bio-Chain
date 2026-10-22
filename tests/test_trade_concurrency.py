"""Test Concurrency & Exclusive Award: Petani O, Pengepul A, dan Pengepul B.

Kasus:
1. Petani O membuka lelang stok sekam 1000 kg.
2. Pengepul A dan Pengepul B melihat barang lelang di /market.
3. Pengepul A dan Pengepul B sama-sama menawar.
4. Petani O menyepakati dan menerima tawaran Pengepul A (1000 kg habis terjual).
5. Pada Pengepul B:
   - Barang lelang hilang dari daftar /market (karena sudah sold out / closed).
   - Bila Pengepul B mencoba menawar atau menghitung saran pada listing tersebut,
     sistem menolaknya dengan pesan jelas bahwa barang sudah terjual ke pengepul lain.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_petani_o_sold_to_pengepul_a_hidden_from_pengepul_b():
    import uuid
    suffix = str(uuid.uuid4().int)[:6]                  # digit saja: nomor HP kini divalidasi (F6)
    phone_o = f"0811{suffix}"
    phone_a = f"0822{suffix}"
    phone_b = f"0833{suffix}"

    with TestClient(app) as c:
        # Register Petani O
        c.post("/api/v1/auth/register", json={
            "phone": phone_o, "username": f"petani_o_{suffix}", "full_name": "Petani O",
            "password": "password123", "role": "petani", "kecamatan": "Godean"
        })
        tok_o = c.post("/api/v1/auth/login", json={"identifier": phone_o, "password": "password123"}).json()["access_token"]
        h_o = {"Authorization": f"Bearer {tok_o}"}

        # Admin create Pengepul A & B (langsung aktif)
        tok_admin = c.post("/api/v1/auth/login", json={"identifier": "admin", "password": "admin2026"}).json()["access_token"]
        h_admin = {"Authorization": f"Bearer {tok_admin}"}

        c.post("/api/v1/admin/users", headers=h_admin, json={
            "phone": phone_a, "username": f"pengepul_a_{suffix}", "full_name": "Pengepul A",
            "password": "password123", "role": "pengepul", "kecamatan": "Sleman", "is_active": True
        })
        c.post("/api/v1/admin/users", headers=h_admin, json={
            "phone": phone_b, "username": f"pengepul_b_{suffix}", "full_name": "Pengepul B",
            "password": "password123", "role": "pengepul", "kecamatan": "Sleman", "is_active": True
        })

        tok_a = c.post("/api/v1/auth/login", json={"identifier": phone_a, "password": "password123"}).json()["access_token"]
        tok_b = c.post("/api/v1/auth/login", json={"identifier": phone_b, "password": "password123"}).json()["access_token"]
        h_a = {"Authorization": f"Bearer {tok_a}"}
        h_b = {"Authorization": f"Bearer {tok_b}"}

        # 1. Petani O buka listing stok 1000 kg
        res_list = c.post("/api/v1/farmer/listings", headers=h_o, json={
            "quantity_kg": 1000.0, "allow_jemput": True, "allow_antar": False,
            "ask_price_jemput": 400.0, "moisture_pct": 14.0, "grade_estimate": "A"
        })
        assert res_list.status_code == 201
        listing_id = res_list.json()["id"]

        # 2. Pengepul A dan Pengepul B sama-sama melihat listing di market
        market_a = c.get("/api/v1/collector/market", headers=h_a).json()
        market_b = c.get("/api/v1/collector/market", headers=h_b).json()
        assert any(l["id"] == listing_id for l in market_a)
        assert any(l["id"] == listing_id for l in market_b)

        # 3. Pengepul A dan Pengepul B sama-sama mengajukan tawaran (bidding)
        bid_a = c.post("/api/v1/collector/bids", headers=h_a, json={
            "listing_id": listing_id, "scheme": "jemput", "price_per_kg": 420.0, "quantity_kg": 1000.0
        })
        assert bid_a.status_code == 201
        bid_a_id = bid_a.json()["bid_id"]

        bid_b = c.post("/api/v1/collector/bids", headers=h_b, json={
            "listing_id": listing_id, "scheme": "jemput", "price_per_kg": 415.0, "quantity_kg": 1000.0
        })
        assert bid_b.status_code == 201
        bid_b_id = bid_b.json()["bid_id"]

        # 4. Petani O menerima tawaran Pengepul A (1000 kg habis terjual)
        accept_res = c.post(f"/api/v1/farmer/listings/{listing_id}/accept", headers=h_o, json={
            "bid_id": bid_a_id, "quantity_kg": 1000.0
        })
        assert accept_res.status_code == 200
        assert accept_res.json()["remaining_kg"] == 0.0
        assert accept_res.json()["listing_status"] == "closed"

        # 5. Verifikasi: Pada Pengepul B, barang lelang sekarang TIDAK ADA di /market
        market_b_after = c.get("/api/v1/collector/market", headers=h_b).json()
        assert not any(l["id"] == listing_id for l in market_b_after), "Listing yang sudah dibeli Pengepul A masih muncul di Pengepul B!"

        # 6. Verifikasi: Tawaran Pengepul B otomatis ditolak (rejected) karena barang sudah habis
        my_bids_b = c.get("/api/v1/collector/bids", headers=h_b).json()
        bid_b_status = next(b for b in my_bids_b if b["bid_id"] == bid_b_id)
        assert bid_b_status["status"] == "rejected"

        # 7. Verifikasi: Jika Pengepul B mencoba menawar lagi pada listing yang sudah terjual
        late_bid = c.post("/api/v1/collector/bids", headers=h_b, json={
            "listing_id": listing_id, "scheme": "jemput", "price_per_kg": 430.0, "quantity_kg": 1000.0
        })
        assert late_bid.status_code == 409
        assert "sudah" in late_bid.json()["detail"].lower() or "closed" in late_bid.json()["detail"].lower()
