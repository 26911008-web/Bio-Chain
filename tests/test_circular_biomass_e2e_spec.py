"""Automated E2E Test Suite: Spesifikasi Sistem Sirkular Biomassa & Biochar
Modul Petani, Pengepul, Driver & Pabrik (End-to-End 4 Persona)

Skenario 1: 4 Petani (Sekam Padi, Tongkol Jagung, Ampas Tebu, Serbuk Sengon)
            Jalur Langsung & Lelang + Request Biochar + Evaluasi Mutu + Rating Pengepul.
Skenario 2: 4 Pengepul Spesialis (Isolasi Komoditas Tunggal, Finalisasi Transaksi,
            Jadwal Penjemputan + Backhaul Biochar, Ekspos Stok ke Pabrik).
Skenario 3: 2 Akun Pabrik (Marketplace Stok Lintas Pengepul, Stock Locking Anti-Double Booking,
            Filter Armada Pabrik ke Driver, Anti-Cross Contamination Single-Biomass per Trip).
Skenario 4: Factory Gate QC Timbangan Jembatan (3-State Decisions: Accepted, Partially Accepted, Rejected),
            Payment Gate Wajib (CASH, DP, TOP), Overdue Protection, Feedback Rekap ke Pengepul, Return Manifest.
Skenario 5: Factory Loading Ramp Blending Optimizer (4 Produk: Biopellet, Biochar, Biosilika, Briket),
            Feedstock Compatibility Matrix, Analisa Finansial & Jejak Karbon, Hasil Samping (By-Products),
            Traceability Sirkular Closed-Loop & Grouped Monitoring Dashboard.
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
from app.models.harvest import Harvest, HarvestStatus, Mill
from app.models.trade import StockListing, Bid, BidStatus
from app.models.industrial import LoadingRamp, GateReception, FactoryInvoice, ProductionBlend, ByProductLedger
from app.models.circular import BiocharRequest, BiocharQualityEvaluation
from app.models.biomass import BiomassParameter
from app.models.ledger import BiocharLedgerEntry
from app.routers.auth import hash_password

HASH = hash_password("testpass123")


@pytest.fixture
def circular_env(tmp_path):
    engine, drop_schema = isolated_engine(tmp_path, "circular_spec.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            # 1. Seed 4 Petani
            farmers = [
                ("petani_sekam", "08111000001", "Pak Joko Sekam", "Godean"),
                ("petani_jagung", "08111000002", "Pak Tono Jagung", "Moyudan"),
                ("petani_tebu", "08111000003", "Bu Rini Tebu", "Minggir"),
                ("petani_kayu", "08111000004", "Pak Bambang Kayu", "Seyegan"),
            ]
            for uname, phone, name, kec in farmers:
                s.add(User(username=uname, phone=phone, password_hash=HASH, full_name=name,
                           role=UserRole.PETANI, kecamatan=kec, is_active=True))

            # 2. Seed 4 Pengepul Spesialis Tunggal (1 pengepul = 1 komoditas spesifik)
            collectors = [
                ("pengepul_sekam", "08122000001", "UD Sekam Berkah", "Godean", "sekam_padi"),
                ("pengepul_jagung", "08122000002", "UD Jagung Makmur", "Moyudan", "tongkol_jagung"),
                ("pengepul_tebu", "08122000003", "UD Tebu Barokah", "Minggir", "ampas_tebu"),
                ("pengepul_kayu", "08122000004", "UD Kayu Lestari", "Seyegan", "serbuk_sengon"),
            ]
            for uname, phone, name, kec, spec in collectors:
                s.add(User(username=uname, phone=phone, password_hash=HASH, full_name=name,
                           role=UserRole.PENGEPUL, kecamatan=kec, specialization_commodity=spec, is_active=True))

            # 3. Seed 1 Driver Armada Pabrik
            s.add(User(username="supir_pabrik", phone="08133000001", password_hash=HASH,
                       full_name="Budi Santoso Driver", role=UserRole.DRIVER, is_active=True))

            # 4. Seed 2 Pabrik Offtaker Multi-Biomassa
            mills_user = [
                ("pabrik_utama", "08144000001", "PT Bio Synergy Nusantara", "Sleman"),
                ("pabrik_kedua", "08144000002", "PT Hijau Sirkular Energi", "Depok"),
            ]
            for uname, phone, name, kec in mills_user:
                s.add(User(username=uname, phone=phone, password_hash=HASH, full_name=name,
                           role=UserRole.PABRIK, kecamatan=kec, is_active=True))

            # 5. Seed Auditor
            s.add(User(username="auditor", phone="08155000001", password_hash=HASH,
                       full_name="Auditor ESG & ISO", role=UserRole.AUDITOR, is_active=True))

            # 6. Seed Titik Penggilingan / Pemasok (Mills table)
            mill_loc = Mill(name="Pusat Pengolahan Biomassa Sleman", code="MILL-SLM", kecamatan="Godean",
                            lat=-7.74, lon=110.36, is_active=True)
            s.add(mill_loc)

            # 7. Seed 4 Loading Ramp Standar untuk 4 Biomassa (Kapasitas & Stok Tinggi untuk Blending)
            ramps = [
                LoadingRamp(ramp_code="RAMP-01", name="Ramp Sekam Padi", biomass_type="sekam_padi",
                            max_capacity_kg=100000.0, current_stock_kg=35000.0, aggregate_mc=13.0, aggregate_ash=17.0, aggregate_lhv_kcal=3400.0),
                LoadingRamp(ramp_code="RAMP-02", name="Ramp Tongkol Jagung", biomass_type="tongkol_jagung",
                            max_capacity_kg=100000.0, current_stock_kg=35000.0, aggregate_mc=14.0, aggregate_ash=2.5, aggregate_lhv_kcal=4100.0),
                LoadingRamp(ramp_code="RAMP-03", name="Ramp Serbuk Sengon", biomass_type="serbuk_sengon",
                            max_capacity_kg=100000.0, current_stock_kg=35000.0, aggregate_mc=25.0, aggregate_ash=1.5, aggregate_lhv_kcal=3800.0),
                LoadingRamp(ramp_code="RAMP-04", name="Ramp Ampas Tebu", biomass_type="ampas_tebu",
                            max_capacity_kg=100000.0, current_stock_kg=35000.0, aggregate_mc=18.0, aggregate_ash=3.0, aggregate_lhv_kcal=3900.0),
            ]
            for r in ramps:
                s.add(r)

            # 8. Set Base Prices pada BiomassParameter agar verifikasi non-lelang valid
            overrides = {
                "sekam_padi": 500.0,
                "tongkol_jagung": 450.0,
                "ampas_tebu": 300.0,
                "serbuk_sengon": 400.0,
            }
            for c_code, b_price in overrides.items():
                bp = (await s.execute(select(BiomassParameter).where(BiomassParameter.code == c_code))).scalar_one_or_none()
                if bp:
                    bp.base_price_per_kg = b_price

            await s.flush()

            # 9. Seed Saldo Awal Dompet Biochar Petani (500 kg) agar Petani Sekam bisa Redeem
            petani_sekam_user = (await s.execute(select(User).where(User.username == "petani_sekam"))).scalar_one()
            pabrik_user = (await s.execute(select(User).where(User.username == "pabrik_utama"))).scalar_one()
            s.add(BiocharLedgerEntry(
                farmer_id=petani_sekam_user.id,
                entry_type="allocation",
                amount_kg=500.0,
                note="Alokasi awal biochar hasil pirolisis untuk pembenah tanah sawah",
                created_by_id=pabrik_user.id,
            ))

            await s.commit()

            ids = {u.username: (u.id, u.role.value) for u in (await s.execute(select(User))).scalars()}
            ramp_ids = {r.ramp_code: r.id for r in (await s.execute(select(LoadingRamp))).scalars()}
            mill_id = mill_loc.id
            return ids, ramp_ids, mill_id

    ids, ramp_ids, mill_id = asyncio.run(setup())

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
        mid = mill_id
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
# SKENARIO 1: PETANI (MULTI-BIOMASSA, DIRECT VS AUCTION, BIOCHAR & RATINGS)
# =============================================================================
def test_scenario_1_farmer_multibiomass_direct_auction_biochar(circular_env):
    """Skenario 1: 4 Petani menginput 4 biomassa berbeda (Harga Langsung & Lelang) + Biochar Request & Review."""
    env = circular_env

    # 0. Test Discovery List Pengepul untuk Petani
    cols = env.ok("petani_sekam", "GET", "/farmer/collectors", params={"commodity": "sekam_padi"})
    assert len(cols) >= 4
    # Pengepul sekam harus berada di paling atas karena spesialisasi cocok
    assert cols[0]["specialization_commodity"] == "sekam_padi"
    assert "Sekam" in cols[0]["name"]
    selected_collector_id = cols[0]["id"]

    # 1. Petani 1 (Sekam Padi) -> Jalur Harga Langsung, Opsi Dijemput Pengepul Spesifik
    h1 = env.ok("petani_sekam", "POST", "/farmer/harvest", json={
        "quantity_kg": 5000.0,
        "commodity": "sekam_padi",
        "mill_id": env.mid,
        "collector_id": selected_collector_id,
        "moisture_est": 13.5,
        "grade_est": "A",
        "delivery_scheme": "jemput",
    }, status=201)
    assert h1["id"] > 0
    assert h1["quantity_kg"] == 5000.0
    assert h1["status"] == "reported"

    # 2. Petani 2 (Tongkol Jagung) -> Jalur Lelang (Open Bidding), Opsi Dijemput Pengepul
    l2 = env.ok("petani_jagung", "POST", "/farmer/listings", json={
        "quantity_kg": 4000.0,
        "commodity": "tongkol_jagung",
        "mill_id": env.mid,
        "moisture_pct": 14.0,
        "grade_estimate": "A",
        "allow_jemput": True,
        "ask_price_jemput": 550.0,
        "allow_antar": False,
    }, status=201)
    assert l2["id"] > 0
    assert l2["commodity"] == "tongkol_jagung"
    assert l2["remaining_kg"] == 4000.0

    # 3. Petani 3 (Ampas Tebu) -> Jalur Harga Langsung, Opsi Antar Mandiri ke Gudang
    h3 = env.ok("petani_tebu", "POST", "/farmer/harvest", json={
        "quantity_kg": 6000.0,
        "commodity": "ampas_tebu",
        "mill_id": env.mid,
        "moisture_est": 18.0,
        "grade_est": "B",
        "delivery_scheme": "antar",
    }, status=201)
    assert h3["id"] > 0
    assert h3["quantity_kg"] == 6000.0

    # 4. Petani 4 (Serbuk Sengon) -> Jalur Lelang (Open Bidding), Opsi Bebas
    l4 = env.ok("petani_kayu", "POST", "/farmer/listings", json={
        "quantity_kg": 3500.0,
        "commodity": "serbuk_sengon",
        "mill_id": env.mid,
        "moisture_pct": 24.0,
        "grade_estimate": "B",
        "allow_jemput": True,
        "ask_price_jemput": 420.0,
        "allow_antar": True,
        "ask_price_antar": 480.0,
    }, status=201)
    assert l4["id"] > 0
    assert l4["commodity"] == "serbuk_sengon"

    # 5. Petani Mengajukan Permintaan Biochar Pembenah Tanah
    redemp = env.ok("petani_sekam", "POST", "/farmer/biochar/redemptions", json={
        "kg": 200.0,
        "land_area_ha": 0.8,
        "pickup_point": "pengepul",
        "note": "Aplikasi biochar untuk pembenah tanah sawah musim tanam 1",
    }, status=201)
    assert redemp["id"] > 0
    assert redemp["kg"] == 200.0
    assert redemp["status"] == "diajukan"

    # 6. Petani Mengisi Evaluasi Mutu Biochar (Mesh, Pirolisis, Kelembapan, Dampak Tanah)
    eval_res = env.ok("petani_sekam", "POST", "/farmer/biochar-evaluations", json={
        "batch_code": "BIOCHAR-SAWAH-01",
        "grain_size_mesh_rating": 5,
        "pyrolysis_maturity_rating": 4,
        "moisture_rating": 5,
        "soil_impact_rating": 5,
        "review_notes": "Struktur tanah menjadi sangat remah dan kelembapan bertahan lebih lama.",
    }, status=201)
    assert eval_res["success"] is True
    assert eval_res["evaluation"]["overall_score"] == 4.75

    # 7. Petani Memberikan Rating Pengepul (Ketepatan Waktu Penjemputan & Pembayaran)
    rating_res = env.ok("petani_sekam", "POST", "/farmer/collector-ratings", json={
        "collector_id": env.uids["pengepul_sekam"],
        "harvest_id": h1["id"],
        "punctuality_rating": 5,
        "payment_rating": 5,
        "review_text": "Pengepul datang tepat waktu dan pelunasan tunai langsung di tempat.",
    }, status=201)
    assert rating_res["success"] is True
    assert rating_res["rating"]["overall_rating"] == 5.0


# =============================================================================
# SKENARIO 2: PENGEPUL SPESIALIS (ISOLASI KOMODITAS & BACKHAUL BIOCHAR)
# =============================================================================
def test_scenario_2_specialist_collectors_isolation_and_backhaul(circular_env):
    """Skenario 2: 4 Pengepul Spesialis (1 pengepul = 1 komoditas), validasi isolasi & penjemputan."""
    env = circular_env

    # 1. Daftarkan laporan panen petani
    h_sekam = env.ok("petani_sekam", "POST", "/farmer/harvest", json={
        "quantity_kg": 4000.0, "commodity": "sekam_padi", "mill_id": env.mid, "delivery_scheme": "jemput"
    }, status=201)
    h_jagung = env.ok("petani_jagung", "POST", "/farmer/harvest", json={
        "quantity_kg": 3000.0, "commodity": "tongkol_jagung", "mill_id": env.mid, "delivery_scheme": "jemput"
    }, status=201)

    # 2. ISOLASI SPESIALISASI KOMODITAS:
    # Pengepul Sekam DILARANG memverifikasi komoditas selain sekam_padi (misal tongkol jagung)
    r_forbidden = env.call("pengepul_sekam", "POST", "/collector/verify", json={
        "harvest_id": h_jagung["id"],
        "weighed_kg": 3000.0,
        "moisture": 14.0,
    })
    assert r_forbidden.status_code in (403, 422), f"Harus ditolak karena bukan spesialisasinya: {r_forbidden.text}"

    # Pengepul Sekam SUKSES memverifikasi komoditas spesialisasinya (sekam_padi)
    v_sekam = env.ok("pengepul_sekam", "POST", "/collector/verify", json={
        "harvest_id": h_sekam["id"],
        "weighed_kg": 4000.0,
        "moisture": 13.0,
        "ash": 16.5,
    })
    assert v_sekam["status"] == "verified"
    assert v_sekam["verified_kg"] == 4000.0

    # 3. Pengepul Spesialis Jagung SUKSES memverifikasi tongkol jagung
    v_jagung = env.ok("pengepul_jagung", "POST", "/collector/verify", json={
        "harvest_id": h_jagung["id"],
        "weighed_kg": 3000.0,
        "moisture": 14.5,
        "ash": 2.5,
    })
    assert v_jagung["status"] == "verified"

    # 4. Pengepul Memeriksa Dashboard Penawaran Ber-Tab (Langsung Diambil vs Lelang)
    dash_sekam = env.ok("pengepul_sekam", "GET", "/collector/offers-dashboard")
    assert dash_sekam["specialization_commodity"] == "sekam_padi"
    for row in dash_sekam["langsung_diambil"]:
        assert row["commodity_code"] == "sekam_padi"

    # 5. Rencana Penjemputan Konsolidasi & Reverse Logistics Muatan Balik Biochar
    plan_res = env.ok("pengepul_sekam", "POST", "/collector/consolidated-pickup-plan", json={
        "harvest_ids": [h_sekam["id"]],
        "truck_max_kg": 5000.0,
        "truck_max_m3": 40.0,
    })
    assert plan_res["success"] is True
    assert plan_res["is_feasible"] is True
    assert plan_res["stops_count"] >= 1

    # 6. Pengepul Mengekspos Stok Siap Jual ke Pabrik
    stocks = env.ok("pabrik_utama", "GET", "/factory/collector-stocks")
    assert "sekam_padi" in stocks["grouped"]
    assert stocks["grouped"]["sekam_padi"]["total_stock_kg"] >= 4000.0


# =============================================================================
# SKENARIO 3: PABRIK DISPATCH, DRIVER FILTER & ANTI-CROSS CONTAMINATION
# =============================================================================
def test_scenario_3_factory_dispatch_driver_filter_anti_contamination(circular_env):
    """Skenario 3: 2 Akun Pabrik, Filter Armada Pabrik ke Driver, Anti-Cross Contamination Single-Biomass."""
    env = circular_env

    # 1. Siapkan 2 lot panen terverifikasi: Sekam Padi dan Tongkol Jagung
    h_sekam = env.ok("petani_sekam", "POST", "/farmer/harvest", json={
        "quantity_kg": 4000.0, "commodity": "sekam_padi", "mill_id": env.mid, "delivery_scheme": "jemput"
    }, status=201)
    env.ok("pengepul_sekam", "POST", "/collector/verify", json={
        "harvest_id": h_sekam["id"], "weighed_kg": 4000.0, "moisture": 13.0
    })

    h_jagung = env.ok("petani_jagung", "POST", "/farmer/harvest", json={
        "quantity_kg": 3500.0, "commodity": "tongkol_jagung", "mill_id": env.mid, "delivery_scheme": "jemput"
    }, status=201)
    env.ok("pengepul_jagung", "POST", "/collector/verify", json={
        "harvest_id": h_jagung["id"], "weighed_kg": 3500.0, "moisture": 14.0
    })

    # 2. VALIDASI ANTI-KONTAMINASI (Single-Biomass per Trip Constraint):
    # Pabrik mencoba menjadwalkan 1 trip truk yang menggabungkan Sekam Padi DAN Tongkol Jagung -> WAJIB 422!
    bad_mix = env.call("pabrik_utama", "POST", "/factory/dispatch", json={
        "driver_id": env.uids["supir_pabrik"],
        "harvest_ids": [h_sekam["id"], h_jagung["id"]],
        "vehicle_plate": "AB 9000 MIX",
        "vehicle_m3": 35.0,
        "logistics_carrier": "FACTORY_FLEET",
    })
    assert bad_mix.status_code == 422
    assert "Anti-Cross Contamination" in bad_mix.text

    # 3. STOCK LOCKING (Anti-Double Booking):
    # Pabrik Utama mengunci stok sekam padi
    lock_res = env.ok("pabrik_utama", "POST", "/factory/reserve-stock", json={
        "harvest_ids": [h_sekam["id"]],
    })
    assert lock_res["success"] is True

    # Pabrik Kedua mencoba mengunci stok yang sama -> Wajib 409 Conflict!
    double_lock = env.call("pabrik_kedua", "POST", "/factory/reserve-stock", json={
        "harvest_ids": [h_sekam["id"]],
    })
    assert double_lock.status_code == 409
    assert "dikunci oleh pabrik lain" in double_lock.text

    # Pabrik Utama melepas kunci stok
    env.ok("pabrik_utama", "POST", "/factory/release-stock", json={"harvest_ids": [h_sekam["id"]]})

    # 4. FILTER PENUGASAN DRIVER (FACTORY_FLEET vs COLLECTOR_SELF):
    # Buat rute dengan Armada Pabrik (FACTORY_FLEET)
    r_fleet = env.ok("pabrik_utama", "POST", "/factory/dispatch", json={
        "driver_id": env.uids["supir_pabrik"],
        "harvest_ids": [h_sekam["id"]],
        "vehicle_plate": "AB 1234 PA",
        "vehicle_m3": 45.0,
        "logistics_carrier": "FACTORY_FLEET",
    }, status=201)
    route_id = r_fleet["route_id"]

    # Supir pabrik memeriksa job-inbox -> Rute armada pabrik HARUS muncul
    inbox = env.ok("supir_pabrik", "GET", "/driver/job-inbox")
    assert any(j["route_id"] == route_id and j["carrier"] == "FACTORY_FLEET" for j in inbox)

    # Supir pabrik memeriksa rute aktif
    active_route = env.ok("supir_pabrik", "GET", "/driver/active-route")
    assert active_route["active"] is True
    assert active_route["route_id"] == route_id


# =============================================================================
# SKENARIO 4: FACTORY GATE QC, PAYMENT GATE (CASH, DP, TOP) & RETURN MANIFEST
# =============================================================================
def test_scenario_4_factory_gate_qc_payment_gate_and_return_manifest(circular_env):
    """Skenario 4: Factory Gate QC 3-State Decisions, Instant Payment Gate, Overdue Freeze, Return Manifest."""
    env = circular_env

    # 1. KEPUTUSAN 1: Diterima Semua (ACCEPTED) + CASH Lunas Instan
    payload_accepted = {
        "collector_id": env.uids["pengepul_sekam"],
        "vehicle_plate": "AB 1111 OK",
        "driver_name": "Supir Satu",
        "logistics_carrier": "FACTORY_FLEET",
        "biomass_type": "sekam_padi",
        "gross_weight": 10000.0,
        "tare_weight": 3000.0,  # Netto: 7000 kg
        "tested_mc_pct": 13.0,
        "tested_ash_pct": 16.5,
        "tested_lhv_kcal": 3450.0,
        "qc_decision": "ACCEPTED",
        "allocated_ramp_id": env.ramps["RAMP-01"],
        "payment_scheme": "CASH",
        "unit_price_rp": 450.0,
    }
    res_acc = env.ok("pabrik_utama", "POST", "/factory/gate-receptions", json=payload_accepted, status=201)
    assert res_acc["gate_ticket"]["accepted_qty_kg"] == 7000.0
    assert res_acc["gate_ticket"]["rejected_qty_kg"] == 0.0
    assert res_acc["invoice"]["status"] == "PAID"
    assert res_acc["invoice"]["remaining"] == 0.0
    assert res_acc["return_manifest"] is None

    # 2. KEPUTUSAN 2: Ditolak Sebagian (PARTIALLY_ACCEPTED) + DP Payment + Return Manifest
    payload_partial = {
        "collector_id": env.uids["pengepul_jagung"],
        "vehicle_plate": "AB 2222 PR",
        "driver_name": "Supir Dua",
        "logistics_carrier": "COLLECTOR_SELF",
        "biomass_type": "tongkol_jagung",
        "gross_weight": 9000.0,
        "tare_weight": 3000.0,  # Netto: 6000 kg
        "tested_mc_pct": 26.0,
        "tested_ash_pct": 4.0,
        "tested_lhv_kcal": 3900.0,
        "qc_decision": "PARTIALLY_ACCEPTED",
        "accepted_qty_kg": 4000.0,
        "rejected_qty_kg": 2000.0,
        "rejection_reason": "2000 kg bagian bawah truk basah dan berjamur (MC 35%).",
        "allocated_ramp_id": env.ramps["RAMP-02"],
        "payment_scheme": "DP",
        "dp_paid_amount": 500000.0,
        "unit_price_rp": 500.0,
    }
    res_part = env.ok("pabrik_utama", "POST", "/factory/gate-receptions", json=payload_partial, status=201)
    assert res_part["gate_ticket"]["accepted_qty_kg"] == 4000.0
    assert res_part["gate_ticket"]["rejected_qty_kg"] == 2000.0
    assert res_part["invoice"]["total_amount_rp"] == 2000000.0
    assert res_part["invoice"]["dp_paid"] == 500000.0
    assert res_part["invoice"]["remaining"] == 1500000.0
    assert res_part["invoice"]["status"] == "PARTIALLY_PAID"
    assert res_part["return_manifest"] is not None
    assert res_part["return_manifest"]["quantity_kg"] == 2000.0
    assert res_part["return_manifest"]["disposition"] == "kembalikan_ke_pengirim"

    # 3. KEPUTUSAN 3: Ditolak Semua (REJECTED) -> Wajib Alasan Tertulis
    payload_rejected = {
        "collector_id": env.uids["pengepul_kayu"],
        "vehicle_plate": "AB 3333 RJ",
        "driver_name": "Supir Tiga",
        "logistics_carrier": "COLLECTOR_SELF",
        "biomass_type": "serbuk_sengon",
        "gross_weight": 8000.0,
        "tare_weight": 3000.0,  # Netto: 5000 kg
        "tested_mc_pct": 48.0,
        "tested_ash_pct": 12.0,
        "tested_lhv_kcal": 2600.0,
        "qc_decision": "REJECTED",
        "rejection_reason": "Kadar air 48% melebihi batas toleransi pirolisis (maks 25%).",
    }
    res_rej = env.ok("pabrik_utama", "POST", "/factory/gate-receptions", json=payload_rejected, status=201)
    assert res_rej["gate_ticket"]["accepted_qty_kg"] == 0.0
    assert res_rej["gate_ticket"]["rejected_qty_kg"] == 5000.0
    assert res_rej["ramp_status"] is None
    assert res_rej["invoice"] is None
    assert res_rej["return_manifest"]["quantity_kg"] == 5000.0

    # 4. FEEDBACK LOOP OTOMATIS KE PENGEPUL:
    feedback = env.ok("pabrik_utama", "GET", f"/factory/collector-feedback-logs?collector_id={env.uids['pengepul_jagung']}")
    assert len(feedback) >= 1
    assert any("basah" in fb["rejection_reason"].lower() for fb in feedback)


# =============================================================================
# SKENARIO 5: BLENDING OPTIMIZER, BY-PRODUCTS, CLOSED-LOOP & GROUPED DASHBOARD
# =============================================================================
def test_scenario_5_blending_optimizer_byproducts_closed_loop_grouped(circular_env):
    """Skenario 5: Blending Multi-Ramp, Feedstock Matrix, By-Products, Closed-Loop & Grouped Monitoring."""
    env = circular_env

    # 1. SIMULASI BLENDING MULTI-RAMP UNTUK 4 PRODUK AKHIR:
    opt = env.ok("pabrik_utama", "POST", "/factory/blends/optimize", json={"batch_size_kg": 10000.0})
    assert opt["batch_size_kg"] == 10000.0
    recs = opt["recommendations"]
    assert len(recs) == 4
    prods = {r["target_product"] for r in recs}
    assert prods == {"BIOPELLET", "BIOCHAR", "BIO_SILICA", "BRIQUETTE"}

    # Verifikasi Feedstock Compatibility Matrix:
    silica_rec = next(r for r in recs if r["target_product"] == "BIO_SILICA")
    assert silica_rec["feedstock_compatibility"]["is_compatible"] is True
    assert "sekam_padi" in silica_rec["feedstock_compatibility"]["preferred_feedstocks"]

    pellet_rec = next(r for r in recs if r["target_product"] == "BIOPELLET")
    assert "serbuk_sengon" in pellet_rec["feedstock_compatibility"]["preferred_feedstocks"]

    # 2. EKSEKUSI PRODUKSI BIOCHAR & PENCATATAN BY-PRODUCTS:
    biochar_rec = next(r for r in recs if r["target_product"] == "BIOCHAR")
    commit_char = env.ok("pabrik_utama", "POST", "/factory/blends/commit", json={
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
    }, status=201)
    assert commit_char["success"] is True
    assert any(bp["type"] == "WOOD_VINEGAR" for bp in commit_char["by_products_recorded"])

    # 3. EKSEKUSI PRODUKSI BIO-SILIKA & PENCATATAN BOTTOM ASH:
    commit_silica = env.ok("pabrik_utama", "POST", "/factory/blends/commit", json={
        "target_product": "BIO_SILICA",
        "total_input_kg": silica_rec["total_input_kg"],
        "ramp_allocations": silica_rec["ramp_allocations"],
        "cost_per_kg": silica_rec["hpp_per_kg"],
        "target_selling_price_per_kg": silica_rec["target_selling_price_per_kg"],
        "estimated_margin_rp": silica_rec["total_profit_rp"],
        "net_tco2e": silica_rec["net_tco2e"],
        "final_mc_pct": silica_rec["final_mc_pct"],
        "final_ash_pct": silica_rec["final_ash_pct"],
        "final_lhv_kcal": silica_rec["final_lhv_kcal"],
    }, status=201)
    assert commit_silica["success"] is True
    assert any(bp["type"] == "BOTTOM_ASH" for bp in commit_silica["by_products_recorded"])

    # 4. CEK BUKU BESAR BY-PRODUCTS (CIRCULAR LEDGER):
    by_products = env.ok("pabrik_utama", "GET", "/factory/by-products")
    assert len(by_products) >= 2
    bp_types = {b["by_product_type"] for b in by_products}
    assert "WOOD_VINEGAR" in bp_types
    assert "BOTTOM_ASH" in bp_types

    # 5. TRACEABILITY BIOCHAR SIRKULAR (CLOSED-LOOP TRACKING):
    trace = env.ok("pabrik_utama", "GET", "/factory/closed-loop-biochar")
    assert "summary" in trace
    assert trace["summary"]["total_biochar_produced_kg"] > 0
    assert len(trace["kiln_batches"]) >= 1

    # 6. DASHBOARD MONITORING TERKELOMPOK BERDASARKAN JENIS BIOMASSA:
    dash = env.ok("pabrik_utama", "GET", "/factory/dashboard/biomass-grouped")
    assert "summary" in dash
    assert len(dash["summary"]) >= 1
    commodities_in_dash = {item["biomass_type"] for item in dash["summary"]}
    assert "sekam_padi" in commodities_in_dash
    assert "tongkol_jagung" in commodities_in_dash
    for item in dash["summary"]:
        assert "biomass_type" in item
        assert "display_name" in item
        assert "ramp_stock_kg" in item
        assert "total_invoiced_rp" in item
