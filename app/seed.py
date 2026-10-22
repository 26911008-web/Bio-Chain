"""Bio-Chain v2 — Demo Seed Data Generator.

Menyediakan dataset demo realistis untuk hackathon & presentasi:
- 6 Demo Users (Admin, Pabrik PT Indmira, Pengepul KUD Sleman, Driver Truk 01, Petani Penggilingan Godean, Petani Moyudan)
- 36 Penggilingan Padi (Mills) di Sleman (DIY) & Klaten (Jateng)
- Laporan Stok Sekam (Harvests) dengan hasil uji proksimat nyata (air, abu, VM, FC, grade A/B/C)
- Rute Armada Penjemputan Sekam (Route & RouteStops) dengan waypoint & QR tracking
- Log Konversi Pirolisis Biochar & Kredit Karbon ESG (IPCC Tier 2)
"""

import hashlib
from datetime import datetime, timezone, timedelta
import random
import uuid
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .services.qr_sign import new_qr_code
from .data import MILLS, DEPOT
from .models.user import User, UserRole, IncentiveTier
from .models.harvest import Mill, Harvest, HarvestStatus, QualityGrade
from .models.route import Route, RouteStop, RouteStatus
from .models.conversion import Conversion, CarbonCredit, IncentiveEvent
from .models.ledger import BiocharLedgerEntry, ConversionInput, CustodyEvent
from .models.energy import EnergyMeterReading
from .models.params import ParameterChange, SystemParameter
from .models.factory_ops import (BatchCost, BatchInput, BatchLoss, BatchOutput, CollectorSettlement, DeliveryRequest,
                                 InboundQC, ManufacturingBatch, NegotiationEvent, SettlementStatus)
from .models.trade import Bid, StockListing, TrxSequence
from .routers.auth import hash_password
from .security.rls import SYSTEM_IDENTITY, apply_now, bind_identity


# Daftar Akun Demo Resmi
DEMO_ACCOUNTS = [
    {
        "username": "admin",
        "phone": "081234567890",
        "email": "admin@biochain.id",
        "password": "admin2026",
        "full_name": "Administrator Bio-Chain",
        "role": UserRole.ADMIN.value,
        "role_label": "System Admin",
        "icon": "⚙️",
        "description": "Kendali sistem, monitoring user & statistik platform",
        "kabupaten": "Sleman",
        "kecamatan": "Depok",
        "lat": -7.768,
        "lon": 110.378,
    },
    {
        "username": "pabrik_indmira",
        "phone": "081298765432",
        "email": "pabrik@indmira.com",
        "password": "pabrik2026",
        "full_name": "Pabrik Pengolahan Multi-Biomassa (PT Indmira)",
        "role": UserRole.PABRIK.value,
        "role_label": "Pabrik Multi-Biomassa",
        "icon": "🏭",
        "description": "Pengolahan multi-biomassa (bio-pellet, briket, biochar & bio-silika), LP blending, karbon IPCC & energi",
        "kabupaten": "Sleman",
        "kecamatan": "Ngaglik",
        "lat": DEPOT["lat"],
        "lon": DEPOT["lon"],
    },
    {
        "username": "pengepul_sleman",
        "phone": "081322334455",
        "email": "kud.sleman@biochain.id",
        "password": "kud2026",
        "full_name": "Pak Ahmad (KUD Tani Makmur Sleman)",
        "role": UserRole.PENGEPUL.value,
        "role_label": "Pengepul / Hub KUD",
        "icon": "📦",
        "description": "Verifikasi uji proksimat biomassa, grading A/B/C & ringkasan gudang multi-biomassa",
        "kabupaten": "Sleman",
        "kecamatan": "Sleman",
        "lat": -7.700,
        "lon": 110.350,
    },
    {
        "username": "sopir_budi",
        "phone": "081433445566",
        "email": "sopir01@biochain.id",
        "password": "truk2026",
        "full_name": "Budi Santoso (Driver Armada 01)",
        "role": UserRole.DRIVER.value,
        "role_label": "Driver Armada Truk",
        "icon": "🚛",
        "description": "Navigasi rute penjemputan multi-biomassa & konfirmasi scan QR",
        "kabupaten": "Sleman",
        "kecamatan": "Mlati",
        "lat": -7.735,
        "lon": 110.335,
    },
    {
        "username": "auditor_esg",
        "phone": "081677889900",
        "email": "auditor@biochain.id",
        "password": "audit2026",
        "full_name": "Auditor Rantai Pasok & ESG",
        "role": UserRole.AUDITOR.value,
        "role_label": "Auditor (Read-only)",
        "icon": "🔍",
        "description": "Audit jejak timbangan, susut, dan alokasi abu bottom ash ke petani — tanpa hak ubah",
        "kabupaten": "Sleman",
        "kecamatan": "Depok",
        "lat": -7.770,
        "lon": 110.380,
    },
    {
        "username": "petani_sugeng",
        "phone": "081544556677",
        "email": "sugeng@petani.id",
        "password": "sekam123",
        "full_name": "Pak Sugeng (Penggilingan Padi Godean)",
        "role": UserRole.PETANI.value,
        "role_label": "Petani / Penggilingan",
        "icon": "🌾",
        "description": "Lapor stok biomassa siap jual, lihat riwayat & klaim insentif XP",
        "kabupaten": "Sleman",
        "kecamatan": "Godean",
        "lat": -7.768,
        "lon": 110.293,
        "xp_total": 1450,
        "tier": IncentiveTier.MITRA_EMAS,
    },
    {
        "username": "petani_sari",
        "phone": "081544556678",
        "email": "sari@petani.id",
        "password": "sekam123",
        "full_name": "Bu Sari (Penggilingan Padi Moyudan)",
        "role": UserRole.PETANI.value,
        "role_label": "Petani / Penggilingan",
        "icon": "🌾",
        "description": "Pemasok biomassa bermutu tinggi",
        "kabupaten": "Sleman",
        "kecamatan": "Moyudan",
        "lat": -7.773,
        "lon": 110.244,
        "xp_total": 680,
        "tier": IncentiveTier.PEMASOK_AKTIF,
    },
]


async def seed_demo_data(db: AsyncSession, force_reset: bool = False) -> dict:
    """Isi database dengan data demo komprehensif."""
    now = datetime.now(timezone.utc)
    bind_identity(db, *SYSTEM_IDENTITY)        # RLS PostgreSQL: seed berjalan sebagai 'system'
    await apply_now(db)

    if force_reset:
        # Hapus data transaksi terlebih dahulu
        if db.bind.dialect.name == "postgresql":   # lewati trigger append-only (migrasi 002)
            await db.execute(text("SET LOCAL biochain.allow_reset = 'on'"))
        # Urutan mengikuti graf foreign key (anak → induk). PostgreSQL menegakkan FK; SQLite tidak.
        for model in (EnergyMeterReading, ParameterChange, SystemParameter,
                      BiocharLedgerEntry, ConversionInput, CustodyEvent, IncentiveEvent, CarbonCredit,
                      CollectorSettlement,
                      BatchCost, BatchLoss, BatchOutput, BatchInput, ManufacturingBatch, InboundQC, NegotiationEvent,
                      TrxSequence, RouteStop, Route,
                      Harvest,                 # → delivery_requests, stock_listings, bids, conversions, mills
                      DeliveryRequest, Bid, StockListing, Conversion, Mill, User):
            await db.execute(delete(model))
        await db.commit()
        from . import params
        params.reset_cache()

    # 1. Seed Users
    seeded_users = {}
    for acc in DEMO_ACCOUNTS:
        existing = await db.execute(
            select(User).where((User.username == acc["username"]) | (User.phone == acc["phone"]))
        )
        u = existing.scalar_one_or_none()
        if not u:
            u = User(
                username=acc["username"],
                phone=acc["phone"],
                email=acc.get("email"),
                password_hash=hash_password(acc["password"]),
                full_name=acc["full_name"],
                role=acc["role"],
                is_active=True,
                kabupaten=acc.get("kabupaten", "Sleman"),
                kecamatan=acc.get("kecamatan"),
                lat=acc.get("lat"),
                lon=acc.get("lon"),
                xp_total=acc.get("xp_total", 0),
                incentive_tier=acc.get("tier", IncentiveTier.PEMULA),
            )
            db.add(u)
            await db.flush()
        seeded_users[acc["username"]] = u

    # 2. Seed Mills (Penggilingan Padi dari data.py)
    seeded_mills = []
    farmer_sugeng = seeded_users.get("petani_sugeng")
    for m in MILLS:
        existing_m = await db.execute(select(Mill).where(Mill.code == m["id"]))
        mill = existing_m.scalar_one_or_none()
        if not mill:
            mill = Mill(
                code=m["id"],
                name=m["name"],
                kecamatan=m["kecamatan"],
                kabupaten="Klaten" if "Klaten" in m["kecamatan"] else "Sleman",
                lat=m["lat"],
                lon=m["lon"],
                capacity_ton=m["stock_ton"],
                owner_id=farmer_sugeng.id if farmer_sugeng and m["id"] == "M01" else None,
                is_active=True,
            )
            db.add(mill)
            await db.flush()
        seeded_mills.append(mill)

    # 3. Seed Harvest Batches (Stok Sekam Padi)
    farmer_user = seeded_users.get("petani_sugeng")
    collector_user = seeded_users.get("pengepul_sleman")

    harvest_count = (await db.execute(select(func.count(Harvest.id)))).scalar() or 0
    seeded_harvests = []
    if harvest_count == 0 and farmer_user and seeded_mills:
        sample_harvests = [
            {
                "mill_idx": 0,
                "qty": 2400.0,
                "status": HarvestStatus.DELIVERED,
                "grade": QualityGrade.A,
                "moisture": 10.8,
                "ash": 17.5,
                "vm": 66.2,
                "fc": 16.3,
                "contam": 1.2,
                "score": 92.5,
                "price_per_kg": 450.0,
                "qr": "BIO-HVK2601",
                "days_ago": 3,
            },
            {
                "mill_idx": 1,
                "qty": 1850.0,
                "status": HarvestStatus.VERIFIED,
                "grade": QualityGrade.A,
                "moisture": 11.2,
                "ash": 18.0,
                "vm": 65.5,
                "fc": 16.0,
                "contam": 1.5,
                "score": 88.0,
                "price_per_kg": 440.0,
                "qr": "BIO-HVK2602",
                "days_ago": 1,
            },
            {
                "mill_idx": 2,
                "qty": 3100.0,
                "status": HarvestStatus.REPORTED,
                "grade": None,
                "moisture": None,
                "ash": None,
                "vm": None,
                "fc": None,
                "contam": 0.0,
                "score": None,
                "price_per_kg": 400.0,
                "qr": "BIO-HVK2603",
                "days_ago": 0,
            },
            {
                "mill_idx": 3,
                "qty": 1200.0,
                "status": HarvestStatus.REPORTED,
                "grade": None,
                "moisture": None,
                "ash": None,
                "vm": None,
                "fc": None,
                "contam": 0.0,
                "score": None,
                "price_per_kg": 400.0,
                "qr": "BIO-HVK2604",
                "days_ago": 0,
            },
            {
                "mill_idx": 4,
                "qty": 2750.0,
                "status": HarvestStatus.COLLECTED,
                "grade": QualityGrade.B,
                "moisture": 13.8,
                "ash": 19.1,
                "vm": 63.8,
                "fc": 15.1,
                "contam": 2.2,
                "score": 76.4,
                "price_per_kg": 380.0,
                "qr": "BIO-HVK2605",
                "days_ago": 2,
            },
        ]

        for sh in sample_harvests:
            mill_target = seeded_mills[sh["mill_idx"]] if sh["mill_idx"] < len(seeded_mills) else None
            h_date = now - timedelta(days=sh["days_ago"], hours=2)
            h = Harvest(
                uuid=str(uuid.uuid4()),
                farmer_id=farmer_user.id,
                mill_id=mill_target.id if mill_target else None,
                collector_id=collector_user.id if collector_user else None,
                quantity_kg=sh["qty"],
                status=sh["status"],
                grade=sh["grade"],
                moisture=sh["moisture"],
                ash=sh["ash"],
                volatile_matter=sh["vm"],
                fixed_carbon=sh["fc"],
                contamination=sh["contam"],
                quality_score=sh["score"],
                base_price_per_kg=sh["price_per_kg"],
                incentive_multiplier=1.1 if sh["grade"] == QualityGrade.A else 1.0,
                total_price=round(sh["qty"] * sh["price_per_kg"], 0),
                qr_code=new_qr_code(hashlib.sha256(sh["qr"].encode()).hexdigest()),   # F14: QR demo bertanda tangan
                reported_at=h_date,
                verified_at=h_date + timedelta(hours=3) if sh["grade"] else None,
                collected_at=h_date + timedelta(hours=6) if sh["status"] in [HarvestStatus.COLLECTED, HarvestStatus.DELIVERED] else None,
                delivered_at=h_date + timedelta(hours=10) if sh["status"] == HarvestStatus.DELIVERED else None,
                # Timbangan bertingkat agar mass balance demo konsisten (susut tipikal ~3% saat angkut)
                verified_kg=sh["qty"] if sh["grade"] else None,
                received_kg=round(sh["qty"] * 0.97, 1) if sh["status"] == HarvestStatus.DELIVERED else None,
                shrinkage_kg=round(sh["qty"] * 0.03, 1) if sh["status"] == HarvestStatus.DELIVERED else None,
                shrinkage_pct=3.0 if sh["status"] == HarvestStatus.DELIVERED else None,
            )
            db.add(h)
            await db.flush()
            seeded_harvests.append(h)
            # Jalur rute yang sudah diterima pabrik selalu punya tagihan pengepul; harga jual demo belum diisi
            factory_user = seeded_users.get("pabrik_indmira")
            if h.received_kg is not None and h.collector_id and factory_user:
                db.add(CollectorSettlement(
                    collector_id=h.collector_id, source="rute", harvest_id=h.id,
                    payable_kg=h.received_kg * (1 - (h.contamination or 0) / 100), moisture=h.moisture,
                    status=SettlementStatus.PENDING_PRICE, created_by_id=factory_user.id, created_at=h.delivered_at,
                    price_basis="menunggu harga: harga jual produk belum diisi di menu Parameter"))

    # 4. Seed Route untuk Driver
    driver_user = seeded_users.get("sopir_budi")
    route_count = (await db.execute(select(func.count(Route.id)))).scalar() or 0
    if route_count == 0 and driver_user and len(seeded_mills) >= 4:
        route = Route(
            driver_id=driver_user.id,
            vehicle_plate="AB 8452 QE",
            status=RouteStatus.IN_PROGRESS,
            vehicle_m3=30.0,
            bulk_density=110.0,
            total_km=42.8,
            baseline_km=68.5,
            saving_pct=37.5,
            total_ton=3.15,
            total_m3=28.6,
            utilization_pct=95.3,
            co2_kg=11.2,
            estimated_hours=2.4,
            planned_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=1),
        )
        db.add(route)
        await db.flush()

        # Route stops (4 penggilingan terdekat)
        stops_plan = [
            {"mill": seeded_mills[0], "order": 1, "ton": 0.95, "scanned": True},
            {"mill": seeded_mills[1], "order": 2, "ton": 0.85, "scanned": True},
            {"mill": seeded_mills[2], "order": 3, "ton": 0.75, "scanned": False},
            {"mill": seeded_mills[3], "order": 4, "ton": 0.60, "scanned": False},
        ]
        for sp in stops_plan:
            m = sp["mill"]
            st = RouteStop(
                route_id=route.id,
                mill_id=m.id,
                stop_order=sp["order"],
                planned_m3=round(sp["ton"] * 1000 / 110, 1),
                planned_ton=sp["ton"],
                actual_ton=sp["ton"] if sp["scanned"] else None,
                qr_scanned=sp["scanned"],
                stop_status="picked_up" if sp["scanned"] else "pending",   # ck_stop_pickup_consistent (PG)
                pickup_at=now - timedelta(minutes=45 * (3 - sp["order"])) if sp["scanned"] else None,
            )
            db.add(st)
        await db.flush()

    # 5. Seed Conversion & Carbon Credit untuk Pabrik
    factory_user = seeded_users.get("pabrik_indmira")
    conv_count = (await db.execute(select(func.count(Conversion.id)))).scalar() or 0
    if conv_count == 0 and factory_user:
        conv1 = Conversion(
            batch_code="BATCH-2026-03-A",
            operator_id=factory_user.id,
            feedstock_ton=50.0,
            feedstock_composition={"sekam_grade_a": 35.0, "sekam_grade_b": 15.0},
            blend_moisture=11.4,
            blend_ash=17.8,
            blend_fc=16.2,
            pyrolysis_temp_c=500.0,
            residence_time_min=45.0,
            biochar_ton=18.5,
            bio_oil_ton=14.2,
            syngas_m3=820.0,
            actual_yield_pct=37.0,
            biochar_ash=48.2,
            biochar_fc=42.1,
            biochar_sio2_pct=88.5,
            biochar_hhv_mj=19.4,
            production_cost=42500000.0,
            selling_price=68000000.0,
            margin=25500000.0,
            processed_at=now - timedelta(days=2),
        )
        db.add(conv1)
        await db.flush()

        cc1 = CarbonCredit(
            conversion_id=conv1.id,
            biomass_ton=50.0,
            transport_km=42.8,
            emission_avoided_tco2=45.6,
            transport_emission_tco2=0.12,
            net_reduction_tco2=45.48,
            methodology="IPCC 2006 Tier 2",
            srn_ppi_eligible=True,
            verified=True,
            period_start=(now - timedelta(days=7)).date(),
            period_end=now.date(),
        )
        db.add(cc1)
        await db.flush()

    await db.commit()
    await seed_energy_if_empty(db)

    # Hitung data ter-seed
    user_cnt = (await db.execute(select(func.count(User.id)))).scalar() or 0
    mill_cnt = (await db.execute(select(func.count(Mill.id)))).scalar() or 0
    harvest_cnt = (await db.execute(select(func.count(Harvest.id)))).scalar() or 0
    route_cnt = (await db.execute(select(func.count(Route.id)))).scalar() or 0
    conv_cnt = (await db.execute(select(func.count(Conversion.id)))).scalar() or 0

    return {
        "status": "success",
        "message": "Demo data berhasil diinisialisasi",
        "counts": {
            "users": user_cnt,
            "mills": mill_cnt,
            "harvests": harvest_cnt,
            "routes": route_cnt,
            "conversions": conv_cnt,
        },
        "demo_accounts": [
            {
                "username": a["username"],
                "phone": a["phone"],
                "password": a["password"],
                "role": a["role"],
                "role_label": a["role_label"],
                "icon": a["icon"],
                "full_name": a["full_name"],
                "description": a["description"],
            }
            for a in DEMO_ACCOUNTS
        ],
    }


DEMO_FACILITY = "Pabrik Pirolisis Sleman"
DEMO_OFFICE_AREA_M2 = 300.0      # kantor + lab ber-AC (dasar IKE); lantai proses dinilai dengan SEC


def demo_energy_history(months: int = 24, end: datetime | None = None) -> list[dict]:
    """Histori listrik bulanan sintetis (DEMO) dengan pola musim panen & dua kejadian pemborosan
    tertanam: kebocoran udara tekan dan blower menyala saat libur produksi."""
    end = end or datetime.now(timezone.utc)
    rng = random.Random(7)
    y, m = end.year, end.month
    periods = []
    for _ in range(months):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        periods.append((y, m))
    periods.reverse()
    rows = []
    for i, (yy, mm) in enumerate(periods):
        harvest = 1.0 + 0.25 * (mm in (3, 4, 8, 9)) - 0.15 * (mm in (12, 1))
        ton = round(330 * harvest * rng.uniform(0.92, 1.08), 1)
        kwh = (18_000 + 95 * ton) * rng.uniform(0.97, 1.03)
        note = None
        if i == months - 7:
            kwh *= 1.22
            note = "DEMO: kebocoran udara tekan (kompresor 24 jam)"
        if i == months - 3:
            kwh += 9_000
            note = "DEMO: blower pengering menyala selama libur produksi"
        hours = 26 * 16 * rng.uniform(0.95, 1.05)
        building = DEMO_OFFICE_AREA_M2 * 12.0 * rng.uniform(0.93, 1.07)       # ≈ 12 kWh/m²/bulan → "Efisien"
        rows.append({"facility": DEMO_FACILITY, "period": f"{yy:04d}-{mm:02d}", "kwh": round(kwh),
                     "building_kwh": round(building),
                     "production_ton": ton, "peak_kw": round(kwh / hours * 2.3, 1), "operating_hours": round(hours),
                     "cost_rp": round(kwh * 1_444.7), "floor_area_m2": DEMO_OFFICE_AREA_M2,
                     "building_type": "ac", "source": "demo", "note": note})
    return rows


async def seed_energy_if_empty(db: AsyncSession) -> bool:
    cnt = (await db.execute(select(func.count(EnergyMeterReading.id)))).scalar() or 0
    if cnt:
        return False
    db.add_all(EnergyMeterReading(**r) for r in demo_energy_history())
    await db.commit()
    return True


async def seed_if_empty(db: AsyncSession) -> bool:
    """Auto-seed saat startup jika tabel users kosong; histori energi diisi terpisah bila kosong."""
    bind_identity(db, *SYSTEM_IDENTITY)
    cnt = (await db.execute(select(func.count(User.id)))).scalar() or 0
    seeded = False
    if cnt == 0:
        print("🌱 Database kosong. Menjalankan auto-seeding demo data Bio-Chain...")
        await seed_demo_data(db, force_reset=False)
        print("✅ Auto-seeding data demo selesai.")
        seeded = True
    if await seed_energy_if_empty(db):
        print("⚡ Histori energi demo 24 bulan ditambahkan.")
    return seeded
