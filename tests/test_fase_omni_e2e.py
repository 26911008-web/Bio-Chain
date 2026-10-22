"""Test Suite: Omni-Audit & Circular Reverse Logistics E2E (Fase 1 - Fase 5)
Menguji end-to-end:
1. Multi-Mode Listing (Direct vs Bidding) & Market Grouping
2. Bidding Lifecycle, Schedule Confirmation & Atomic Acceptance
3. Circular Biochar Backhaul Requests & Dual-Capacity Consolidated Routing (30 m³ / 5.000 kg)
4. Field QC Refraction & Deviation Transparency
5. Driver QR Checkpoint Scan & Backhaul Drop Delivery
6. Factory Biochar Dispatch, Weighbridge Slip & Receivables Tracking
7. Collector Reputation Scorecard
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import models  # noqa: F401
from app.database import Base, get_db
from app.dependencies import create_access_token
from app.main import app
from tests.conftest import isolated_engine
from app.models.user import User, UserRole
from app.routers.auth import hash_password

PEOPLE = {
    "petani_1": (UserRole.PETANI, -7.768, 110.293),
    "petani_2": (UserRole.PETANI, -7.722, 110.300),
    "pengepul_1": (UserRole.PENGEPUL, -7.700, 110.350),
    "supir_1": (UserRole.DRIVER, -7.735, 110.335),
    "pabrik_1": (UserRole.PABRIK, -7.745, 110.362),
    "auditor_1": (UserRole.AUDITOR, None, None),
}
HASH = hash_password("secret123")


@pytest.fixture
def env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "omni_e2e.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            for i, (name, (role, lat, lon)) in enumerate(PEOPLE.items()):
                s.add(User(
                    username=name,
                    phone=f"0812{i:07d}",
                    password_hash=HASH,
                    full_name=name.replace("_", " ").title(),
                    role=role,
                    is_active=True,
                    lat=lat,
                    lon=lon,
                    kecamatan="Sleman",
                ))
            await s.commit()
            return {u.username: u for u in (await s.execute(select(User))).scalars()}

    users = asyncio.run(setup())

    async def override():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    headers = {n: {"Authorization": f"Bearer {create_access_token(u.id, u.role.value)}"} for n, u in users.items()}

    class E:
        ids = {n: u.id for n, u in users.items()}
        h = headers
        session = Session

        def call(self, who, method, path, json=None):
            return client.request(method, f"/api/v1{path}", json=json, headers=headers[who])

        def ok(self, who, method, path, json=None, status=200):
            r = self.call(who, method, path, json)
            assert r.status_code == status, f"{who} {method} {path} → {r.status_code}: {r.text}"
            return r.json()

    yield E()
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


def test_omni_multi_mode_listing_and_market_grouping(env):
    """Fase 2 & 3: Petani membuat listing Direct & Bidding, Pengepul melihat market terkelompok."""
    # 1. Listing Mode DIRECT
    l_direct = env.ok("petani_1", "POST", "/farmer/listings", {
        "quantity_kg": 2000,
        "commodity": "sekam_padi",
        "allow_jemput": True,
        "ask_price_jemput": 420,
        "transaction_mode": "DIRECT",
    }, status=201)
    assert l_direct["transaction_mode"] == "DIRECT"
    assert l_direct["remaining_kg"] == 2000

    # 2. Listing Mode BIDDING (Bursa Lelang)
    l_bidding = env.ok("petani_2", "POST", "/farmer/listings", {
        "quantity_kg": 3000,
        "commodity": "sekam_padi",
        "allow_jemput": True,
        "ask_price_jemput": 400,
        "floor_price": 400,
        "transaction_mode": "BIDDING",
    }, status=201)
    assert l_bidding["transaction_mode"] == "BIDDING"
    assert l_bidding["floor_price"] == 400

    # 3. Pengepul cek bursa terkelompok (/api/v1/collector/market-grouped)
    grouped = env.ok("pengepul_1", "GET", "/collector/market-grouped")
    assert isinstance(grouped, list)
    sekam_group = next((g for g in grouped if g["commodity"] == "sekam_padi"), None)
    assert sekam_group is not None
    assert sekam_group["direct_count"] >= 1
    assert sekam_group["bidding_count"] >= 1
    assert sekam_group["total_stock_kg"] >= 5000


def test_omni_bidding_lifecycle_and_schedule_confirmation(env):
    """Fase 2: Alur tawar-menawar lelang, penjadwalan & konfirmasi jadwal petani."""
    l = env.ok("petani_1", "POST", "/farmer/listings", {
        "quantity_kg": 2500,
        "commodity": "sekam_padi",
        "allow_jemput": True,
        "ask_price_jemput": 400,
        "transaction_mode": "BIDDING",
    }, status=201)

    # Pengepul mengajukan tawaran beserta rencana tanggal jemput & term COD
    bid_res = env.ok("pengepul_1", "POST", "/collector/bids", {
        "listing_id": l["id"],
        "scheme": "jemput",
        "price_per_kg": 430,
        "quantity_kg": 2500,
        "pickup_date": "2026-10-20",
        "logistics_mode": "PICKUP",
        "payment_term": "COD",
    }, status=201)
    bid_id = bid_res["bid_id"]

    # Petani cek tawaran
    bids_data = env.ok("petani_1", "GET", f"/farmer/listings/{l['id']}/bids")
    assert len(bids_data["bids"]) >= 1
    target_bid = next(b for b in bids_data["bids"] if b["bid_id"] == bid_id)
    assert target_bid["price_per_kg"] == 430

    # Petani menyetujui jadwal jemput
    sched_res = env.ok("petani_1", "POST", f"/farmer/bids/{bid_id}/schedule-respond", {
        "action": "APPROVED",
        "reschedule_note": "Siap dijemput pagi jam 08:00 WIB",
    })
    assert sched_res["farmer_schedule_status"] == "APPROVED"

    # Petani menerima tawaran (Accept Bid)
    award = env.ok("petani_1", "POST", f"/farmer/listings/{l['id']}/accept", {
        "bid_id": bid_id,
        "quantity_kg": 2500,
    })
    assert award["contract_value_rp"] == 2500 * 430
    assert award["remaining_kg"] == 0
    assert "qr_verification_token" in award
    harvest_id = award["harvest_id"]
    assert harvest_id > 0


def test_omni_reverse_logistics_biochar_and_consolidated_routing(env):
    """Fase 2, 3, 4: Permintaan muatan balik biochar & rute konsolidasi dual-kapasitas (Volume ≤ 30 m³, Massa ≤ 5.000 kg)."""
    # Buat harvest 1 untuk petani 1 (1.500 kg -> 12.5 m³)
    h1 = env.ok("petani_1", "POST", "/farmer/harvest", {
        "quantity_kg": 1500,
        "commodity": "sekam_padi",
    }, status=201)

    # Buat harvest 2 untuk petani 2 (1.500 kg -> 12.5 m³)
    h2 = env.ok("petani_2", "POST", "/farmer/harvest", {
        "quantity_kg": 1500,
        "commodity": "sekam_padi",
    }, status=201)

    # Petani 1 mengajukan muatan balik biochar untuk sawahnya (400 kg -> 1.33 m³)
    b_req = env.ok("petani_1", "POST", "/farmer/biochar-requests", {
        "requested_kg": 400,
        "collector_id": env.ids["pengepul_1"],
        "harvest_id": h1["id"],
        "delivery_point": "Sawah Blok A",
        "notes": "Muatan balik biochar untuk pembenah tanah",
    }, status=201)
    assert b_req["requested_kg"] == 400
    assert b_req["status"] == "REQUESTED"

    # Petani cek daftar permintaan biochar
    reqs = env.ok("petani_1", "GET", "/farmer/biochar-requests")
    assert any(r["id"] == b_req["id"] for r in reqs)

    # Pengepul menyusun rute konsolidasi dengan muatan balik biochar (Kapasitas 30 m³ -> Cukup: 26.33 m³)
    plan = env.ok("pengepul_1", "POST", "/collector/consolidated-pickup-plan", {
        "harvest_ids": [h1["id"], h2["id"]],
        "vehicle_plate": "AB 1234 CD",
        "truck_max_kg": 5000.0,
        "truck_max_m3": 30.0,
        "biochar_backhaul_requests": [b_req["id"]],
    })
    assert plan["is_feasible"] is True
    assert plan["total_biochar_backhaul_kg"] == 400
    assert plan["total_biomass_kg"] == 3000
    assert len(plan["simulation_timeline"]) >= 3

    # Uji deteksi overload bila batas volume diperkecil ke 20 m³
    plan_overload = env.ok("pengepul_1", "POST", "/collector/consolidated-pickup-plan", {
        "harvest_ids": [h1["id"], h2["id"]],
        "vehicle_plate": "AB 1234 CD",
        "truck_max_kg": 5000.0,
        "truck_max_m3": 20.0,
        "biochar_backhaul_requests": [b_req["id"]],
    })
    assert plan_overload["is_feasible"] is False
    assert "Kapasitas terlampaui" in plan_overload["warning"]


def test_omni_field_qc_refraction_and_deviations(env):
    """Fase 2 & 3: Timbangan lapangan dengan pencatatan deviasi & umpan balik transparan."""
    # Lapor panen dengan klaim 2.500 kg
    h = env.ok("petani_1", "POST", "/farmer/harvest", {
        "quantity_kg": 2500,
        "commodity": "sekam_padi",
        "moisture_est": 12.0,
    }, status=201)
    h_id = h["id"]

    # Pengepul menimbang lapangan: hasil riil 2.450 kg (ada deviasi -50 kg / -2.0%)
    verify_res = env.ok("pengepul_1", "POST", "/collector/verify", {
        "harvest_id": h_id,
        "weighed_kg": 2450.0,
        "actual_weighed_qty": 2450.0,
        "moisture": 12.5,
        "ash": 16.0,
        "volatile_matter": 65.0,
        "fixed_carbon": 17.0,
        "contamination": 1.0,
    })
    assert verify_res["actual_weighed_qty"] == 2450.0
    assert verify_res["farmer_claimed_qty"] == 2500.0
    assert verify_res["deviation_kg"] == -50.0
    assert verify_res["deviation_pct"] == -2.0
    assert verify_res["qc_status"] == "PASS"
    assert "qr_verification_token" in verify_res
    qr_token = verify_res["qr_verification_token"]

    # Petani mengecek riwayat transparansi deviasi (/api/v1/farmer/qc-deviations)
    devs = env.ok("petani_1", "GET", "/farmer/qc-deviations")
    assert len(devs) >= 1
    d_row = next(d for d in devs if d["harvest_id"] == h_id)
    assert d_row["farmer_claimed_qty"] == 2500.0
    assert d_row["actual_weighed_qty"] == 2450.0
    assert d_row["deviation_kg"] == -50.0
    assert d_row["qc_status"] == "PASS"

    # Driver melakukan scan QR checkpoint di titik jemput
    scan_res = env.ok("supir_1", "POST", "/driver/checkpoint-scan", {
        "qr_token": qr_token,
        "checkpoint_type": "PICKUP",
        "lat": -7.768,
        "lon": 110.293,
        "notes": "Biomassa dijemput sesuai timbangan lapangan",
    })
    assert scan_res["success"] is True
    assert scan_res["type"] == "HARVEST"
    assert scan_res["actual_weighed_qty"] == 2450.0


def test_omni_factory_biochar_dispatch_and_driver_delivery(env):
    """Fase 4: Pabrik menerbitkan surat jalan biochar muatan balik, supir scan QR & konfirmasi serah terima."""
    # Pabrik menerbitkan muatan balik biochar 500 kg
    disp = env.ok("pabrik_1", "POST", "/factory/dispatch-biochar", {
        "collector_id": env.ids["pengepul_1"],
        "driver_id": env.ids["supir_1"],
        "total_weight_kg": 500.0,
        "total_bags": 20,
        "vehicle_plate": "AB 8888 XY",
    }, status=201)
    assert disp["total_weight_kg"] == 500.0
    assert disp["status"] == "DISPATCHED"
    qr_dsp = disp["qr_dispatch_token"]
    disp_id = disp["id"]

    # Driver mengecek tugas muatan balik (/api/v1/driver/backhaul-tasks)
    tasks = env.ok("supir_1", "GET", "/driver/backhaul-tasks")
    assert any(t["id"] == disp_id for t in tasks)

    # Driver scan QR checkpoint muatan balik
    scan_dsp = env.ok("supir_1", "POST", "/driver/checkpoint-scan", {
        "qr_token": qr_dsp,
        "checkpoint_type": "FACTORY_OUTBOUND",
    })
    assert scan_dsp["success"] is True
    assert scan_dsp["type"] == "BIOCHAR_BACKHAUL"

    # Driver menyerahkan biochar ke sawah petani
    drop_res = env.ok("supir_1", "POST", "/driver/confirm-backhaul-drop", {
        "distribution_id": disp_id,
        "farmer_id": env.ids["petani_1"],
        "delivered_kg": 500.0,
        "notes": "Ditumpuk di saung sawah petani",
    })
    assert drop_res["success"] is True
    assert drop_res["status"] == "DELIVERED_TO_FARMER"


def test_omni_collector_reputation_and_receivables(env):
    """Fase 2 & 3: Scorecard reputasi pengepul dan tracking piutang pabrik."""
    # 1. Petani cek scorecard reputasi pengepul
    reps = env.ok("petani_1", "GET", "/farmer/collector-reputations")
    assert len(reps) >= 1
    top_col = reps[0]
    assert "on_time_settlement_rate" in top_col
    assert "punctuality_rating" in top_col
    assert "trust_badge" in top_col

    # 2. Pengepul cek tracking piutang pabrik
    recs = env.ok("pengepul_1", "GET", "/collector/factory-receivables")
    assert "total_unpaid_rp" in recs
    assert "pending_invoices_count" in recs
    assert isinstance(recs["items"], list)
