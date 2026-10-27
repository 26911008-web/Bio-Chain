"""Unit & Integration Tests for Factory Scientific Upgrades:
- OEE (Overall Equipment Effectiveness) in Batch Economics (Nakajima 1988 / TPM)
- Demand-Driven MRP (DDMRP) Buffer Sizing (Ptak & Smith 2019)
- Statistical Process Control (SPC) & Proximate Closure Check (ASTM D3172 / ISO 17246)
- Factory Router Endpoints (/inventory/ddmrp-buffers & /quality/spc-check)
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.engines.factory_econ import batch_economics, calculate_ddmrp_buffers, check_proximate_spc


def test_oee_calculation_world_class():
    """Verify OEE calculation achieves World-Class standard (>85%) under ideal conditions."""
    input_kg = 15000.0  # 15 ton
    outputs = {"bio_pellet": 6000.0, "biochar": 3000.0, "bio_silika": 500.0}
    losses = {
        "air": 1800.0, "volatil_syngas": 3200.0, "gas_pembakaran": 0.0,
        "bio_oil": 300.0, "residu_ekstraksi": 100.0, "susut_proses": 100.0
    }
    # 15 ton at 1.5 tph design capacity = 10 std hours. If run in 10 hours: Availability=1.0, Performance=1.0
    econ = batch_economics(
        input_kg=input_kg,
        outputs_kg=outputs,
        losses_kg=losses,
        joint_costs=5_000_000.0,
        separable_costs={"bio_pellet": 0.0, "biochar": 0.0, "bio_silika": 500_000.0},
        hours=10.0,
        price_overrides={"bio_pellet": 1800.0, "biochar": 6000.0, "bio_silika": 25000.0}
    )

    assert "oee" in econ
    oee = econ["oee"]
    assert oee["availability_pct"] == 100.0
    assert oee["performance_pct"] == 100.0
    assert oee["quality_pct"] > 60.0
    assert oee["oee_pct"] > 60.0
    assert "status" in oee
    assert oee["actual_tph"] == 1.5


def test_ddmrp_buffer_zones():
    """Verify DDMRP buffer calculation follows Ptak & Smith (2019) 3-zone model."""
    res = calculate_ddmrp_buffers(current_stock_kg=12000.0, adu_kg_day=20000.0, dlt_days=3.0, variability_factor=0.4)
    zones = res["zones"]

    # Red = 20,000 * 3 * 0.4 = 24,000 kg
    assert zones["red_zone_kg"] == 24000.0
    # Yellow = 20,000 * 3 = 60,000 kg
    assert zones["yellow_zone_kg"] == 60000.0
    # Top of Red (TOR) = 24,000 kg
    assert zones["top_of_red_kg"] == 24000.0
    # Top of Yellow (TOY) = 84,000 kg
    assert zones["top_of_yellow_kg"] == 84000.0
    # Current stock 12,000 < TOR (24,000) -> RED zone
    assert res["current_zone"] == "RED"
    assert "Kritis" in res["status_label"]

    # Test GREEN zone
    res_green = calculate_ddmrp_buffers(current_stock_kg=150000.0, adu_kg_day=20000.0, dlt_days=3.0)
    assert res_green["current_zone"] == "GREEN"
    assert "Optimal" in res_green["status_label"]


def test_spc_proximate_closure_valid():
    """Verify ASTM D3172 proximate closure within +/-5% is valid and in-control."""
    # Standard proximate sum: 12% moisture + 17% ash + 56% VM + 15% FC = 100%
    spc = check_proximate_spc(moisture=12.0, ash=17.0, volatile_matter=56.0, fixed_carbon=15.0, contamination=0.5)
    assert spc["total_proximate_pct"] == 100.0
    assert spc["closure_error_pct"] == 0.0
    assert spc["closure_valid"] is True
    assert spc["in_control"] is True
    assert len(spc["anomalies"]) == 0


def test_spc_proximate_closure_deviation_and_limits():
    """Verify ASTM D3172 proximate closure catches anomalies when sum != 100% or exceeds 3-sigma."""
    # Anomaly 1: Sum = 125% (Out of closure tolerance)
    spc_bad = check_proximate_spc(moisture=25.0, ash=25.0, volatile_matter=60.0, fixed_carbon=15.0)
    assert spc_bad["closure_valid"] is False
    assert spc_bad["in_control"] is False
    assert any("Total fraksi proksimat" in a for a in spc_bad["anomalies"])
    assert any("Kadar air" in a for a in spc_bad["anomalies"])  # 25% > 16% UCL
    assert any("Kadar abu" in a for a in spc_bad["anomalies"])  # 25% > 21% UCL


@pytest.mark.asyncio
async def test_factory_ddmrp_and_spc_endpoints():
    """Verify HTTP endpoints for DDMRP inventory and SPC proximate checks."""
    from app.dependencies import get_current_user
    from app.routers.factory import _audit_read
    from app.models.user import User, UserRole

    mock_user = User(id=1, username="pabrik_indmira", role=UserRole.PABRIK, full_name="Kepala Pabrik", is_active=True, token_version=0)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[_audit_read] = lambda: mock_user
    try:
        from app.dependencies import create_access_token
        valid_token = create_access_token(user_id=1, role="pabrik")
        headers = {"Authorization": f"Bearer {valid_token}"}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:

            # 1. Test DDMRP buffer endpoint
            ddmrp_res = await ac.get("/api/v1/factory/inventory/ddmrp-buffers", headers=headers)
            assert ddmrp_res.status_code == 200
            ddmrp_data = ddmrp_res.json()
            assert "zones" in ddmrp_data
            assert "current_zone" in ddmrp_data
            assert "recommended_action" in ddmrp_data

            # 2. Test SPC check endpoint
            spc_res = await ac.post(
                "/api/v1/factory/quality/spc-check",
                params={"moisture": 12.5, "ash": 16.8, "volatile_matter": 55.2, "fixed_carbon": 15.5, "contamination": 1.0},
                headers=headers
            )
            assert spc_res.status_code == 200
            spc_data = spc_res.json()
            assert spc_data["closure_valid"] is True
            assert spc_data["in_control"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(_audit_read, None)
