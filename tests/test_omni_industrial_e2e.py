"""E2E Industrial Test Suite:
1. Isolasi Penugasan Driver Pabrik (FACTORY_FLEET vs COLLECTOR_SELF).
2. Gerbang Masuk & QC Timbangan Jembatan (ACCEPTED, PARTIALLY_ACCEPTED, REJECTED) dengan Refraksi Mutu & Auto-Invoice.
3. Skema Finansial Multi-Opsi (CASH, DP, TOP) & Overdue Control Freeze.
4. Alokasi Loading Ramp Dinamis dengan Pembaruan Mutu Rekursif & Limit Overflow.
5. Mesin Rekomendasi Blending Multi-Ramp (4 Produk) & Eksekusi Batch Sirkular (By-Product Ledger).
6. Grouped Monitoring Dashboard & Collector Quality Feedback.
"""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import Base, get_db
from app.dependencies import create_access_token
from app.main import app
from tests.conftest import isolated_engine
from app.models.user import User, UserRole
from app.models.route import Route, RouteStatus
from app.models.industrial import LoadingRamp, GateReception, FactoryInvoice, ProductionBlend, ByProductLedger
from app.routers.auth import hash_password

HASH = hash_password("testpass123")


@pytest.fixture
def industrial_env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "ind.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            users_data = [
                ("pabrik", "08110000001", UserRole.PABRIK),
                ("pengepul", "08120000002", UserRole.PENGEPUL),
                ("pengepul2", "08120000003", UserRole.PENGEPUL),
                ("supir_pabrik", "08130000004", UserRole.DRIVER),
                ("auditor", "08140000005", UserRole.AUDITOR),
            ]
            for uname, phone, role in users_data:
                s.add(User(username=uname, phone=phone, password_hash=HASH, full_name=f"User {uname.title()}", role=role, is_active=True))
            await s.commit()

            # Inisialisasi 4 Loading Ramp Standar
            ramps = [
                LoadingRamp(ramp_code="RAMP-01", name="Ramp Utama Sekam Padi", biomass_type="sekam_padi", max_capacity_kg=50000.0, current_stock_kg=15000.0, aggregate_mc=13.0, aggregate_ash=17.0, aggregate_lhv_kcal=3400.0),
                LoadingRamp(ramp_code="RAMP-02", name="Ramp Tongkol Jagung Cacah", biomass_type="tongkol_jagung", max_capacity_kg=40000.0, current_stock_kg=10000.0, aggregate_mc=14.0, aggregate_ash=2.5, aggregate_lhv_kcal=4100.0),
                LoadingRamp(ramp_code="RAMP-03", name="Ramp Serbuk Kayu Sengon", biomass_type="serbuk_sengon", max_capacity_kg=35000.0, current_stock_kg=8000.0, aggregate_mc=25.0, aggregate_ash=1.5, aggregate_lhv_kcal=3800.0),
                LoadingRamp(ramp_code="RAMP-04", name="Ramp Cangkang Tempurung Kelapa", biomass_type="tempurung_kelapa", max_capacity_kg=45000.0, current_stock_kg=12000.0, aggregate_mc=10.0, aggregate_ash=2.0, aggregate_lhv_kcal=4600.0),
            ]
            for r in ramps:
                s.add(r)
            await s.commit()

            ids = {u.username: (u.id, u.role.value) for u in (await s.execute(select(User))).scalars()}
            ramp_ids = {r.ramp_code: r.id for r in (await s.execute(select(LoadingRamp))).scalars()}
            return ids, ramp_ids

    ids, ramp_ids = asyncio.run(setup())

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
    headers = {n: {"Authorization": f"Bearer {create_access_token(uid, role)}"} for n, (uid, role) in ids.items()}

    class Env:
        h = headers
        uids = {n: uid for n, (uid, _) in ids.items()}
        ramps = ramp_ids
        session_factory = Session

        def call(self, who, method, path, json=None, params=None):
            return client.request(method, f"/api/v1{path}", json=json, params=params, headers=headers[who])

        def ok(self, who, method, path, json=None, status=200, params=None):
            r = self.call(who, method, path, json=json, params=params)
            assert r.status_code == status, f"{who} {method} {path} -> {r.status_code}: {r.text}"
            return r.json()

    yield Env()
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())
    if drop_schema:
        drop_schema()


# =============================================================================
# 1. TEST ISOLASI PENUGASAN DRIVER PABRIK (FACTORY_FLEET vs COLLECTOR_SELF)
# =============================================================================
def test_driver_job_isolation_carrier_check(industrial_env):
    env = industrial_env

    # 1. Buat rute dengan carrier COLLECTOR_SELF (pengepul kirim mandiri)
    async def seed_routes():
        async with env.session_factory() as s:
            now = datetime.now(timezone.utc)
            r_self = Route(
                driver_id=env.uids["supir_pabrik"],
                vehicle_plate="AB 1111 CS",
                status=RouteStatus.PLANNED,
                logistics_carrier="COLLECTOR_SELF",
                planned_at=now,
                created_at=now
            )
            r_fleet = Route(
                driver_id=env.uids["supir_pabrik"],
                vehicle_plate="AB 2222 FF",
                status=RouteStatus.PLANNED,
                logistics_carrier="FACTORY_FLEET",
                planned_at=now,
                created_at=now
            )
            s.add(r_self)
            s.add(r_fleet)
            await s.commit()

    asyncio.run(seed_routes())

    # Driver meminta rute aktif
    res = env.call("supir_pabrik", "GET", "/driver/active-route")
    assert res.status_code == 200
    data = res.json()
    assert data["active"] is True
    # Wajib rute FACTORY_FLEET, rute COLLECTOR_SELF harus terisolasi dan diabaikan
    assert data["vehicle_plate"] == "AB 2222 FF"


# =============================================================================
# 2. TEST GERBANG PABRIK, 3-STATE QC & PEMBARUAN MUTU REKURSIF RAMP
# =============================================================================
def test_gate_reception_qc_accepted_and_recursive_ramp_update(industrial_env):
    env = industrial_env

    # Gross: 12000 kg, Tare: 4000 kg -> Netto: 8000 kg
    # RAMP-01 saat ini: stok 15000 kg, MC 13.0%, Ash 17.0%, LHV 3400.0 kcal
    # Muatan masuk: 8000 kg, MC 15.0%, Ash 19.0%, LHV 3200.0 kcal
    # Stok baru = 15000 + 8000 = 23000 kg
    # MC baru = (15000*13.0 + 8000*15.0) / 23000 = (195000 + 120000)/23000 = 13.70%
    # Ash baru = (15000*17.0 + 8000*19.0) / 23000 = (255000 + 152000)/23000 = 17.70%
    payload = {
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 8888 BB",
        "driver_name": "Budi Santoso",
        "logistics_carrier": "FACTORY_FLEET",
        "biomass_type": "sekam_padi",
        "gross_weight": 12000.0,
        "tare_weight": 4000.0,
        "tested_mc_pct": 15.0,
        "tested_ash_pct": 19.0,
        "tested_lhv_kcal": 3200.0,
        "contamination_pct": 1.5,
        "qc_decision": "ACCEPTED",
        "allocated_ramp_id": env.ramps["RAMP-01"],
        "payment_scheme": "CASH",
        "unit_price_rp": 450.0,
    }

    res = env.ok("pabrik", "POST", "/factory/gate-receptions", json=payload, status=201)
    assert res["success"] is True
    assert res["gate_ticket"]["net_weight"] == 8000.0
    assert res["gate_ticket"]["accepted_qty_kg"] == 8000.0
    assert res["gate_ticket"]["rejected_qty_kg"] == 0.0

    # Cek pembaruan mutu rekursif pada ramp
    ramp_status = res["ramp_status"]
    assert ramp_status["new_stock_kg"] == 23000.0
    assert ramp_status["aggregate_mc"] == pytest.approx(13.70, abs=0.05)
    assert ramp_status["aggregate_ash"] == pytest.approx(17.70, abs=0.05)

    # Cek invoice terbit otomatis (CASH = Lunas instan)
    invoice = res["invoice"]
    assert invoice["total_amount_rp"] == 8000.0 * 450.0  # Rp 3.600.000
    assert invoice["payment_scheme"] == "CASH"
    assert invoice["status"] == "PAID"
    assert invoice["remaining"] == 0.0


def test_gate_reception_qc_partially_accepted_and_rejection_validation(industrial_env):
    env = industrial_env

    # 1. Tolak sebagian TANPA alasan penolakan -> Wajib 422
    payload_no_reason = {
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 7777 CC",
        "driver_name": "Slamet",
        "logistics_carrier": "COLLECTOR_SELF",
        "biomass_type": "tongkol_jagung",
        "gross_weight": 10000.0,
        "tare_weight": 3000.0,  # Netto: 7000 kg
        "tested_mc_pct": 28.0,
        "tested_ash_pct": 5.0,
        "tested_lhv_kcal": 3800.0,
        "qc_decision": "PARTIALLY_ACCEPTED",
        "accepted_qty_kg": 4000.0,
        "rejected_qty_kg": 3000.0,
        "rejection_reason": None,  # Kosong!
        "allocated_ramp_id": env.ramps["RAMP-02"],
        "payment_scheme": "DP",
        "dp_paid_amount": 500000.0,
        "unit_price_rp": 500.0,
    }
    r_err = env.call("pabrik", "POST", "/factory/gate-receptions", json=payload_no_reason)
    assert r_err.status_code == 422

    # 2. Tolak sebagian DENGAN alasan penolakan tertulis
    payload_valid = dict(payload_no_reason)
    payload_valid["rejection_reason"] = "3000 kg bagian bawah truk basah dan berjamur (MC 38%)."
    res = env.ok("pabrik", "POST", "/factory/gate-receptions", json=payload_valid, status=201)
    assert res["success"] is True
    assert res["gate_ticket"]["accepted_qty_kg"] == 4000.0
    assert res["gate_ticket"]["rejected_qty_kg"] == 3000.0
    assert res["gate_ticket"]["rejection_reason"] == payload_valid["rejection_reason"]

    # Ramp-02 hanya bertambah 4000 kg (stok awal 10000 -> 14000 kg)
    assert res["ramp_status"]["new_stock_kg"] == 14000.0

    # Invoice hanya menagihkan kuantitas yang diterima (4000 kg * 500 = Rp 2.000.000)
    inv = res["invoice"]
    assert inv["total_amount_rp"] == 2000000.0
    assert inv["dp_paid"] == 500000.0
    assert inv["remaining"] == 1500000.0
    assert inv["status"] == "PARTIALLY_PAID"


def test_gate_reception_qc_rejected_total(industrial_env):
    env = industrial_env

    # Penolakan total tanpa alasan -> Wajib 422
    payload = {
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 5555 DD",
        "driver_name": "Agus",
        "logistics_carrier": "COLLECTOR_SELF",
        "biomass_type": "serbuk_sengon",
        "gross_weight": 8000.0,
        "tare_weight": 3000.0,  # Netto: 5000 kg
        "tested_mc_pct": 45.0,
        "tested_ash_pct": 10.0,
        "tested_lhv_kcal": 2800.0,
        "qc_decision": "REJECTED",
        "rejection_reason": None,
    }
    assert env.call("pabrik", "POST", "/factory/gate-receptions", json=payload).status_code == 422

    # Dengan alasan penolakan
    payload["rejection_reason"] = "Kadar air 45% melebihi batas toleransi maksimal 25%."
    res = env.ok("pabrik", "POST", "/factory/gate-receptions", json=payload, status=201)
    assert res["gate_ticket"]["accepted_qty_kg"] == 0.0
    assert res["gate_ticket"]["rejected_qty_kg"] == 5000.0
    assert res["ramp_status"] is None  # Tidak masuk ramp
    assert res["invoice"] is None      # Tidak diterbitkan invoice pembayaran


def test_ramp_capacity_overflow_protection(industrial_env):
    env = industrial_env

    # RAMP-03 kapasitas maks: 35000 kg, stok saat ini: 8000 kg. Ruang sisa: 27000 kg.
    # Coba masukkan muatan 30000 kg -> Melebihi kapasitas -> Wajib 409 Conflict
    payload = {
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 9999 BIG",
        "driver_name": "Joko Tronton",
        "logistics_carrier": "FACTORY_FLEET",
        "biomass_type": "serbuk_sengon",
        "gross_weight": 40000.0,
        "tare_weight": 10000.0,  # Netto 30000 kg
        "tested_mc_pct": 18.0,
        "tested_ash_pct": 1.5,
        "tested_lhv_kcal": 3900.0,
        "qc_decision": "ACCEPTED",
        "allocated_ramp_id": env.ramps["RAMP-03"],
        "payment_scheme": "CASH",
    }
    r = env.call("pabrik", "POST", "/factory/gate-receptions", json=payload)
    assert r.status_code == 409
    assert "Kapasitas fisik RAMP-03 terlampaui" in r.json()["detail"]


# =============================================================================
# 3. TEST KONTROL TAGIHAN OVERDUE (TOP FREEZE RULE)
# =============================================================================
def test_overdue_top_control_blocks_new_orders(industrial_env):
    env = industrial_env

    # Buat invoice yang telah overdue untuk pabrik
    async def create_overdue_invoice():
        async with env.session_factory() as s:
            inv = FactoryInvoice(
                invoice_number="INV-OVERDUE-001",
                mill_id=env.uids["pabrik"],
                collector_id=env.uids["pengepul"],
                biomass_type="sekam_padi",
                billable_qty_kg=5000.0,
                unit_price_rp=450.0,
                total_amount_rp=2250000.0,
                payment_scheme="TOP",
                dp_paid_amount=0.0,
                remaining_amount=2250000.0,
                due_date=datetime.now(timezone.utc) - timedelta(days=5),  # 5 hari lewat jatuh tempo!
                is_overdue=True,
                status="OVERDUE",
                created_at=datetime.now(timezone.utc) - timedelta(days=20)
            )
            s.add(inv)
            await s.commit()

    asyncio.run(create_overdue_invoice())

    # Coba buat transaksi baru dengan skema TOP -> Wajib DIBLOKIR 403 Forbidden!
    payload_top = {
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 3333 TT",
        "driver_name": "Anto",
        "logistics_carrier": "FACTORY_FLEET",
        "biomass_type": "tempurung_kelapa",
        "gross_weight": 8000.0,
        "tare_weight": 3000.0,  # Netto 5000 kg
        "tested_mc_pct": 11.0,
        "tested_ash_pct": 2.0,
        "tested_lhv_kcal": 4500.0,
        "qc_decision": "ACCEPTED",
        "allocated_ramp_id": env.ramps["RAMP-04"],
        "payment_scheme": "TOP",  # Skema TOP
        "due_days": 14,
    }
    r = env.call("pabrik", "POST", "/factory/gate-receptions", json=payload_top)
    assert r.status_code == 403
    assert "Pabrik memiliki tagihan TOP yang telah jatuh tempo" in r.json()["detail"]


# =============================================================================
# 4. TEST MULTI-RAMP BLENDING OPTIMIZER & COMMIT DENGAN BY-PRODUCT
# =============================================================================
def test_multi_ramp_blending_optimizer_and_commit(industrial_env):
    env = industrial_env

    # 1. Hitung rekomendasi blending untuk batch 10.000 kg
    res_opt = env.ok("pabrik", "POST", "/factory/blends/optimize", json={"batch_size_kg": 10000.0})
    assert res_opt["batch_size_kg"] == 10000.0
    recs = res_opt["recommendations"]
    assert len(recs) == 4

    products = {r["target_product"] for r in recs}
    assert products == {"BIOPELLET", "BIOCHAR", "BIO_SILICA", "BRIQUETTE"}

    # Wajib ada tepat satu yang most profitable dan lowest carbon
    most_prof = [r for r in recs if r["is_most_profitable"]]
    lowest_carb = [r for r in recs if r["is_lowest_carbon"]]
    assert len(most_prof) == 1
    assert len(lowest_carb) == 1

    # Ambil rekomendasi BIOCHAR
    biochar_rec = next(r for r in recs if r["target_product"] == "BIOCHAR")
    assert biochar_rec["total_input_kg"] == 10000.0
    assert biochar_rec["yield_pct"] == 28.0
    assert biochar_rec["estimated_output_kg"] == 2800.0
    assert biochar_rec["net_tco2e"] > 0

    # 2. Commit batch BIOCHAR
    commit_payload = {
        "target_product": "BIOCHAR",
        "total_input_kg": biochar_rec["total_input_kg"],
        "ramp_allocations": biochar_rec["ramp_allocations"],
        "cost_per_kg": biochar_rec["hpp_per_kg"],
        "target_selling_price_per_kg": biochar_rec["target_selling_price_per_kg"],
        "estimated_margin_rp": biochar_rec["total_profit_rp"],
        "net_tco2e": biochar_rec["net_tco2e"],
        "final_mc_pct": biochar_rec["final_mc_pct"],
        "final_ash_pct": biochar_rec["final_ash_pct"],
        "final_lhv_kcal": biochar_rec["final_lhv_kcal"],
    }
    res_commit = env.ok("pabrik", "POST", "/factory/blends/commit", json=commit_payload, status=201)
    assert res_commit["success"] is True
    assert res_commit["target_product"] == "BIOCHAR"
    assert len(res_commit["by_products_recorded"]) == 1
    assert res_commit["by_products_recorded"][0]["type"] == "WOOD_VINEGAR"
    assert res_commit["by_products_recorded"][0]["qty_kg"] == 1500.0  # 15% dari 10.000 kg

    # 3. Verifikasi riwayat blending tercatat
    blends = env.ok("pabrik", "GET", "/factory/blends")
    assert len(blends) >= 1
    assert blends[0]["blend_code"] == res_commit["blend_code"]
    assert blends[0]["target_product"] == "BIOCHAR"

    # 4. Verifikasi riwayat by-product tercatat
    bps = env.ok("pabrik", "GET", "/factory/by-products")
    assert len(bps) >= 1
    assert bps[0]["by_product_type"] == "WOOD_VINEGAR"
    assert bps[0]["circular_status"] == "STORED"


# =============================================================================
# 5. TEST DASHBOARD MONITORING TERKELOMPOK & TRANSPARANSI UMPAN BALIK PENGEPUL
# =============================================================================
def test_grouped_biomass_dashboard_and_collector_feedback(industrial_env):
    env = industrial_env

    # Jalankan transaksi gerbang untuk sekam padi (diterima) dan serbuk sengon (ditolak sebagian)
    env.ok("pabrik", "POST", "/factory/gate-receptions", json={
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 1010 SE",
        "driver_name": "Pak Tani Supir",
        "logistics_carrier": "FACTORY_FLEET",
        "biomass_type": "sekam_padi",
        "gross_weight": 9000.0,
        "tare_weight": 3000.0,  # 6000 kg
        "tested_mc_pct": 12.5,
        "tested_ash_pct": 16.5,
        "tested_lhv_kcal": 3450.0,
        "qc_decision": "ACCEPTED",
        "allocated_ramp_id": env.ramps["RAMP-01"],
        "payment_scheme": "CASH",
    }, status=201)

    env.ok("pabrik", "POST", "/factory/gate-receptions", json={
        "collector_id": env.uids["pengepul"],
        "vehicle_plate": "AB 2020 SG",
        "driver_name": "Supir Dua",
        "logistics_carrier": "COLLECTOR_SELF",
        "biomass_type": "serbuk_sengon",
        "gross_weight": 7000.0,
        "tare_weight": 2000.0,  # 5000 kg
        "tested_mc_pct": 32.0,
        "tested_ash_pct": 2.0,
        "tested_lhv_kcal": 3600.0,
        "qc_decision": "PARTIALLY_ACCEPTED",
        "accepted_qty_kg": 3000.0,
        "rejected_qty_kg": 2000.0,
        "rejection_reason": "Kadar air 32% terlalu basah untuk reaktor pirolisis langsung.",
        "allocated_ramp_id": env.ramps["RAMP-03"],
        "payment_scheme": "DP",
        "dp_paid_amount": 300000.0,
    }, status=201)

    # 1. Cek Dashboard Monitoring Terkelompok (Pabrik)
    dash = env.ok("pabrik", "GET", "/factory/dashboard/biomass-grouped")
    summary = dash["summary"]
    assert len(summary) >= 2

    sekam_sum = next(s for s in summary if s["biomass_type"] == "sekam_padi")
    assert sekam_sum["total_incoming_kg"] == 6000.0
    assert sekam_sum["total_accepted_kg"] == 6000.0
    assert sekam_sum["rejection_rate_pct"] == 0.0

    sengon_sum = next(s for s in summary if s["biomass_type"] == "serbuk_sengon")
    assert sengon_sum["total_incoming_kg"] == 5000.0
    assert sengon_sum["total_accepted_kg"] == 3000.0
    assert sengon_sum["total_rejected_kg"] == 2000.0
    assert sengon_sum["rejection_rate_pct"] == 40.0

    # 2. Cek Log Evaluasi Mutu & Umpan Balik Pengepul di sisi Pabrik
    pabrik_fb = env.ok("pabrik", "GET", "/factory/collector-feedback-logs")
    assert len(pabrik_fb) >= 2
    sengon_fb = next(f for f in pabrik_fb if f["biomass_type"] == "serbuk_sengon")
    assert sengon_fb["rejected_qty_kg"] == 2000.0
    assert "Jemur ulang" in sengon_fb["actionable_feedback"] or "kering" in sengon_fb["actionable_feedback"]

    # 3. Cek Transparansi Umpan Balik Gerbang di sisi Pengepul
    col_fb = env.ok("pengepul", "GET", "/collector/gate-feedback")
    assert col_fb["total_deliveries"] >= 2
    assert col_fb["total_rejected_kg"] >= 2000.0
    assert len(col_fb["items"]) >= 2
    rejection_item = next(i for i in col_fb["items"] if i["rejected_qty_kg"] > 0)
    assert rejection_item["rejection_reason"] == "Kadar air 32% terlalu basah untuk reaktor pirolisis langsung."
    assert "penjemuran" in rejection_item["actionable_feedback"].lower() or "lembab" in rejection_item["actionable_feedback"].lower()
