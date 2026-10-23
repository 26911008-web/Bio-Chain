"""Test ketelusuran sirkular QR Code end-to-end (petani -> pengepul -> driver -> pabrik -> abu/biochar -> sawah)."""

from fastapi.testclient import TestClient

from app.main import app


def test_circular_traceability_e2e():
    with TestClient(app) as anon:
        # Publik tanpa login: daftar lot & lookup ID angka ditolak (cegah enumerasi lot)
        assert (anon.get("/api/v1/traceability/recent?limit=5")).status_code == 401
        assert (anon.get("/api/v1/traceability/circular/1")).status_code == 401
        assert (anon.get("/api/v1/traceability/circular/BIO-00000000-AAAAAA")).status_code == 401

    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"identifier": "pabrik_indmira", "password": "pabrik2026"})
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        # 1. Test recent circular lots
        res_recent = client.get("/api/v1/traceability/recent?limit=50")
        assert res_recent.status_code == 200
        recent_data = res_recent.json()
        assert isinstance(recent_data, list)
        assert len(recent_data) > 0
        sample_lot = recent_data[0]
        assert "id" in sample_lot
        assert "origin_qr_code" in sample_lot

        # 2. Test circular trace by Harvest ID
        h_id = sample_lot["id"]
        res_trace = client.get(f"/api/v1/traceability/circular/{h_id}")
        assert res_trace.status_code == 200
        data = res_trace.json()
        assert data["found"] is True
        assert "loop_summary" in data
        assert "stages" in data
        assert len(data["stages"]) == 6

        # Verifikasi tahapan sirkular 1 s/d 6
        stage_ids = [s["stage_id"] for s in data["stages"]]
        assert stage_ids == [
            "STAGE_1_FARMER_REPORT",
            "STAGE_2_COLLECTOR_VERIFICATION",
            "STAGE_3_DRIVER_LOGISTICS",
            "STAGE_4_FACTORY_GATE",
            "STAGE_5_CONVERSION_PRODUCTION",
            "STAGE_6_CIRCULAR_BACKHAUL_FARMER",
        ]

        # Verifikasi keberadaan QR code pada tiap tahap
        for stage in data["stages"]:
            assert "qr_code" in stage
            assert stage["qr_code"] is not None
            assert len(stage["qr_code"]) > 0

        # Verifikasi hash integritas kriptografis
        assert "integrity_hash" in data["loop_summary"]
        assert len(data["loop_summary"]["integrity_hash"]) == 64  # SHA256 length

        # 3. Test lookup by QR origin code
        qr_origin = sample_lot["origin_qr_code"]
        res_by_qr = client.get(f"/api/v1/traceability/circular/{qr_origin}")
        assert res_by_qr.status_code == 200
        data_by_qr = res_by_qr.json()
        assert data_by_qr["found"] is True
        assert data_by_qr["harvest_id"] == h_id

        # Publik dengan QR asli bertanda tangan → silsilah terbuka, HP tersamarkan
        from app.services.qr_sign import is_signed
        signed = next((r["qr_code"] for r in recent_data if r.get("qr_code") and is_signed(r["qr_code"])), None)
        if signed:
            with TestClient(app) as anon:
                r = anon.get(f"/api/v1/traceability/circular/{signed}")
                assert r.status_code == 200 and r.json()["found"] is True
                phone = r.json()["stages"][0]["actor"]["phone"]
                assert phone == "-" or "*" in phone
