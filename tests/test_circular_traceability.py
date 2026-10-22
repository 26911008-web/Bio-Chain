"""Test ketelusuran sirkular QR Code end-to-end (petani -> pengepul -> driver -> pabrik -> abu/biochar -> sawah)."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_circular_traceability_e2e():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test recent circular lots
        res_recent = await client.get("/api/v1/traceability/recent?limit=5")
        assert res_recent.status_code == 200
        recent_data = res_recent.json()
        assert isinstance(recent_data, list)
        assert len(recent_data) > 0
        sample_lot = recent_data[0]
        assert "id" in sample_lot
        assert "origin_qr_code" in sample_lot

        # 2. Test circular trace by Harvest ID
        h_id = sample_lot["id"]
        res_trace = await client.get(f"/api/v1/traceability/circular/{h_id}")
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
        res_by_qr = await client.get(f"/api/v1/traceability/circular/{qr_origin}")
        assert res_by_qr.status_code == 200
        data_by_qr = res_by_qr.json()
        assert data_by_qr["found"] is True
        assert data_by_qr["harvest_id"] == h_id
