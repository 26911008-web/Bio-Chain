"""Seed Multi-Entity E2E Biomassa Supply Chain (Fase 1).

Menyiapkan dataset uji komprehensif:
1. 4 Petani:
   - Petani 1 (Sekam Padi): 12 Ton, MC 14%, Ash 18%, Bulk Density 110 kg/m³
   - Petani 2 (Bonggol Jagung): 10 Ton, MC 15%, Ash 2%, Bulk Density 280 kg/m³
   - Petani 3 (Ampas Tebu): 15 Ton, MC 48%, Ash 3%, Bulk Density 150 kg/m³
   - Petani 4 (Serbuk Kayu Sengon): 14 Ton, MC 12%, Ash 1%, Bulk Density 220 kg/m³
2. 3 Pengepul:
   - Pengepul 1: Khusus Sekam Padi (UD Berkah Sekam)
   - Pengepul 2: Khusus Bonggol Jagung (KUD Jagung Makmur)
   - Pengepul 3: Khusus Kayu & Serat (CV Kayu Serat Lestari)
3. 2 Driver:
   - Driver 1 & Driver 2: Truk Colt Diesel (Kapasitas Maksimal 6 Ton / Volume Bak 16 m³)
4. 2 Pabrik:
   - Pabrik 1: Lini Pelet & Briket (PT Bioenergi Pellet & Briket)
   - Pabrik 2: Lini Pirolisis Biochar & Ekstraksi Silika (PT Nusaprima Biochar & Silika)
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete, update
from app.database import async_session, engine, Base
from app.models.user import User, UserRole, IncentiveTier
from app.models.trade import StockListing, ListingStatus, DeliveryScheme
from app.models.harvest import Harvest, HarvestStatus, QualityGrade, Mill
from app.models.biomass import BiomassParameter, CollectorWarehouse, WarehouseStockMovement
from app.models.route import Route, RouteStatus, RouteStop, StopStatus
from app.routers.auth import hash_password
from app.biomass_seed import BIOMASS_SEED


# 1. Definisi User
USERS_TO_SEED = [
    # 4 Petani
    {
        "username": "petani_sekam",
        "phone": "081111110001",
        "email": "petani.sekam@biochain.test",
        "password": "password123",
        "full_name": "Pak Slamet (Petani Sekam Padi)",
        "role": UserRole.PETANI,
        "kecamatan": "Godean",
        "kabupaten": "Sleman",
        "lat": -7.7680,
        "lon": 110.2930,
    },
    {
        "username": "petani_jagung",
        "phone": "081111110002",
        "email": "petani.jagung@biochain.test",
        "password": "password123",
        "full_name": "Pak Joko (Petani Bonggol Jagung)",
        "role": UserRole.PETANI,
        "kecamatan": "Moyudan",
        "kabupaten": "Sleman",
        "lat": -7.7730,
        "lon": 110.2440,
    },
    {
        "username": "petani_tebu",
        "phone": "081111110003",
        "email": "petani.tebu@biochain.test",
        "password": "password123",
        "full_name": "Pak Sugeng (Petani Ampas Tebu)",
        "role": UserRole.PETANI,
        "kecamatan": "Seyegan",
        "kabupaten": "Sleman",
        "lat": -7.7250,
        "lon": 110.3010,
    },
    {
        "username": "petani_kayu",
        "phone": "081111110004",
        "email": "petani.kayu@biochain.test",
        "password": "password123",
        "full_name": "Pak Widodo (Petani Serbuk Sengon)",
        "role": UserRole.PETANI,
        "kecamatan": "Cangkringan",
        "kabupaten": "Sleman",
        "lat": -7.6320,
        "lon": 110.4350,
    },

    # 4 Pengepul Spesialis (1 Komoditas per Pengepul)
    {
        "username": "pengepul_sekam",
        "phone": "082222220001",
        "email": "pengepul.sekam@biochain.test",
        "password": "password123",
        "full_name": "Haji Mansur (UD Berkah Sekam - Spesialis Sekam)",
        "role": UserRole.PENGEPUL,
        "specialization_commodity": "sekam_padi",
        "kecamatan": "Godean",
        "kabupaten": "Sleman",
        "lat": -7.7610,
        "lon": 110.3010,
    },
    {
        "username": "pengepul_jagung",
        "phone": "082222220002",
        "email": "pengepul.jagung@biochain.test",
        "password": "password123",
        "full_name": "Pak Hartono (KUD Jagung Makmur - Spesialis Jagung)",
        "role": UserRole.PENGEPUL,
        "specialization_commodity": "tongkol_jagung",
        "kecamatan": "Moyudan",
        "kabupaten": "Sleman",
        "lat": -7.7710,
        "lon": 110.2500,
    },
    {
        "username": "pengepul_tebu",
        "phone": "082222220004",
        "email": "pengepul.tebu@biochain.test",
        "password": "password123",
        "full_name": "Pak Kusnadi (UD Tebu Barokah - Spesialis Ampas Tebu)",
        "role": UserRole.PENGEPUL,
        "specialization_commodity": "ampas_tebu",
        "kecamatan": "Seyegan",
        "kabupaten": "Sleman",
        "lat": -7.7280,
        "lon": 110.3050,
    },
    {
        "username": "pengepul_kayu",
        "phone": "082222220003",
        "email": "pengepul.kayu@biochain.test",
        "password": "password123",
        "full_name": "Bu Retno (CV Kayu Serat Lestari - Spesialis Kayu/Serat)",
        "role": UserRole.PENGEPUL,
        "specialization_commodity": "serbuk_sengon",
        "kecamatan": "Mlati",
        "kabupaten": "Sleman",
        "lat": -7.7300,
        "lon": 110.3600,
    },

    # 2 Driver Truk Colt Diesel
    {
        "username": "driver_colt1",
        "phone": "083333330001",
        "email": "driver.colt1@biochain.test",
        "password": "password123",
        "full_name": "Budi Santoso (Driver Truk Colt Diesel 1 - 16 m3 / 6 Ton)",
        "role": UserRole.DRIVER,
        "kecamatan": "Sleman",
        "kabupaten": "Sleman",
        "lat": -7.7100,
        "lon": 110.3550,
    },
    {
        "username": "driver_colt2",
        "phone": "083333330002",
        "email": "driver.colt2@biochain.test",
        "password": "password123",
        "full_name": "Agus Prayitno (Driver Truk Colt Diesel 2 - 16 m3 / 6 Ton)",
        "role": UserRole.DRIVER,
        "kecamatan": "Sleman",
        "kabupaten": "Sleman",
        "lat": -7.7120,
        "lon": 110.3570,
    },

    # 2 Pabrik
    {
        "username": "pabrik_pelet_briket",
        "phone": "084444440001",
        "email": "pabrik.pellet@biochain.test",
        "password": "password123",
        "full_name": "PT Bioenergi Pellet & Briket (Plant Prambanan)",
        "role": UserRole.PABRIK,
        "kecamatan": "Prambanan",
        "kabupaten": "Sleman",
        "lat": -7.7520,
        "lon": 110.4910,
    },
    {
        "username": "pabrik_biochar_silika",
        "phone": "084444440002",
        "email": "pabrik.biochar@biochain.test",
        "password": "password123",
        "full_name": "PT Nusaprima Biochar & Silika (Plant Ngaglik)",
        "role": UserRole.PABRIK,
        "kecamatan": "Ngaglik",
        "kabupaten": "Sleman",
        "lat": -7.7120,
        "lon": 110.3850,
    },
]

# 2. Spesifikasi Listing Stok Petani
FARMER_STOCKS = [
    {
        "username": "petani_sekam",
        "commodity": "sekam_padi",
        "quantity_kg": 12000.0,
        "moisture_pct": 14.0,
        "ash_pct": 18.0,
        "bulk_density": 110.0,
        "ask_jemput": 450.0,
        "ask_antar": 550.0,
    },
    {
        "username": "petani_jagung",
        "commodity": "tongkol_jagung",
        "quantity_kg": 10000.0,
        "moisture_pct": 15.0,
        "ash_pct": 2.0,
        "bulk_density": 280.0,
        "ask_jemput": 400.0,
        "ask_antar": 500.0,
    },
    {
        "username": "petani_tebu",
        "commodity": "ampas_tebu",
        "quantity_kg": 15000.0,
        "moisture_pct": 48.0,
        "ash_pct": 3.0,
        "bulk_density": 150.0,
        "ask_jemput": 250.0,
        "ask_antar": 350.0,
    },
    {
        "username": "petani_kayu",
        "commodity": "serbuk_sengon",
        "quantity_kg": 14000.0,
        "moisture_pct": 12.0,
        "ash_pct": 1.0,
        "bulk_density": 220.0,
        "ask_jemput": 380.0,
        "ask_antar": 480.0,
    },
]


async def seed():
    print("================================================================================")
    print("🌾 MEMULAI SEEDING DATA E2E MULTI-BIOMASSA SUPPLY CHAIN (FASE 1)")
    print("================================================================================")

    # Pastikan skema tabel dibuat
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        # 1. Pastikan Master Biomassa terisi dengan bulk density & batas spesifikasi
        print("\n[1/5] Memeriksa & Memperbarui Master Biomassa...")
        for b_data in BIOMASS_SEED:
            existing_bp = (await s.execute(
                select(BiomassParameter).where(BiomassParameter.code == b_data["code"])
            )).scalar_one_or_none()
            if not existing_bp:
                bp = BiomassParameter(**b_data)
                s.add(bp)
            else:
                for k, v in b_data.items():
                    setattr(existing_bp, k, v)

        # Update spesifikasi spesifik skenario uji
        overrides = {
            "sekam_padi": {"bulk_density_kg_m3": 110.0, "ash_pct_db": 18.0, "moisture_ref_pct": 12.0, "base_price_per_kg": 500.0},
            "tongkol_jagung": {"bulk_density_kg_m3": 280.0, "ash_pct_db": 2.0, "moisture_ref_pct": 15.0, "base_price_per_kg": 450.0},
            "ampas_tebu": {"bulk_density_kg_m3": 150.0, "ash_pct_db": 3.0, "moisture_ref_pct": 50.0, "base_price_per_kg": 300.0},
            "serbuk_sengon": {"bulk_density_kg_m3": 220.0, "ash_pct_db": 1.0, "moisture_ref_pct": 30.0, "base_price_per_kg": 400.0},
        }
        for c_code, vals in overrides.items():
            bp = (await s.execute(select(BiomassParameter).where(BiomassParameter.code == c_code))).scalar_one_or_none()
            if bp:
                for k, v in vals.items():
                    setattr(bp, k, v)
        await s.flush()
        print("   ✅ Master biomassa tersinkronisasi (Sekam, Jagung, Tebu, Sengon).")

        # 2. Injeksi Akun Pengguna (4 Petani, 4 Pengepul, 2 Driver, 2 Pabrik = 12 Akun)
        print("\n[2/5] Menyuntikkan 12 Akun Pengguna Terisolasi...")
        user_map = {}
        for udata in USERS_TO_SEED:
            u = (await s.execute(select(User).where(User.username == udata["username"]))).scalar_one_or_none()
            if not u:
                u = User(
                    username=udata["username"],
                    phone=udata["phone"],
                    email=udata["email"],
                    password_hash=hash_password(udata["password"]),
                    full_name=udata["full_name"],
                    role=udata["role"],
                    specialization_commodity=udata.get("specialization_commodity"),
                    is_active=True,
                    kecamatan=udata["kecamatan"],
                    kabupaten=udata["kabupaten"],
                    lat=udata["lat"],
                    lon=udata["lon"],
                    xp_total=1000,
                    incentive_tier=IncentiveTier.PEMASOK_AKTIF,
                )
                s.add(u)
                await s.flush()
            else:
                u.phone = udata["phone"]
                u.password_hash = hash_password(udata["password"])
                u.full_name = udata["full_name"]
                u.role = udata["role"]
                u.specialization_commodity = udata.get("specialization_commodity")
                u.is_active = True
                u.lat = udata["lat"]
                u.lon = udata["lon"]
            user_map[udata["username"]] = u
            spec_str = f" [Spesialis: {u.specialization_commodity}]" if u.specialization_commodity else ""
            print(f"   👤 {udata['role'].value.upper():8} : {udata['username']:22} | {udata['full_name']}{spec_str}")

        # 3. Buat Gudang Pengepul Spesialis
        print("\n[3/5] Membangun Gudang Pengepul Spesialis...")
        collector_warehouses = [
            ("pengepul_sekam", "Gudang Sekam Sleman", 250.0),
            ("pengepul_jagung", "Gudang Jagung Moyudan", 300.0),
            ("pengepul_tebu", "Gudang Tebu Seyegan", 300.0),
            ("pengepul_kayu", "Gudang Kayu Mlati", 350.0),
        ]
        for col_name, wh_name, cap_m3 in collector_warehouses:
            col_user = user_map[col_name]
            wh = (await s.execute(select(CollectorWarehouse).where(
                CollectorWarehouse.collector_id == col_user.id,
                CollectorWarehouse.name == wh_name
            ))).scalar_one_or_none()
            if not wh:
                wh = CollectorWarehouse(
                    collector_id=col_user.id,
                    name=wh_name,
                    lat=col_user.lat,
                    lon=col_user.lon,
                    capacity_m3=cap_m3,
                    is_covered=True,
                    is_active=True
                )
                s.add(wh)
                await s.flush()
            print(f"   🏭 Gudang Pengepul: {wh.name:25} (Milik: {col_user.username}, Kapasitas: {wh.capacity_m3} m³)")

        # 4. Injeksi Listing Stok & Harvest Petani (4 Komoditas)
        print("\n[4/5] Menerbitkan Stok & Listing 4 Petani...")
        for item in FARMER_STOCKS:
            farmer = user_map[item["username"]]
            
            # Cek/update StockListing
            listing = (await s.execute(select(StockListing).where(
                StockListing.farmer_id == farmer.id,
                StockListing.commodity == item["commodity"]
            ))).scalars().first()

            if not listing:
                listing = StockListing(
                    farmer_id=farmer.id,
                    quantity_kg=item["quantity_kg"],
                    remaining_kg=item["quantity_kg"],
                    commodity=item["commodity"],
                    moisture_pct=item["moisture_pct"],
                    grade_estimate="A",
                    allow_jemput=True,
                    allow_antar=True,
                    ask_price_jemput=item["ask_jemput"],
                    ask_price_antar=item["ask_antar"],
                    lat=farmer.lat,
                    lon=farmer.lon,
                    status=ListingStatus.OPEN,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    version=1,
                )
                s.add(listing)
                await s.flush()
            else:
                listing.quantity_kg = item["quantity_kg"]
                listing.remaining_kg = item["quantity_kg"]
                listing.moisture_pct = item["moisture_pct"]
                listing.status = ListingStatus.OPEN
                listing.ask_price_jemput = item["ask_jemput"]
                listing.ask_price_antar = item["ask_antar"]

            # Buat record Harvest verified terkait untuk rantai pasok
            h = (await s.execute(select(Harvest).where(
                Harvest.farmer_id == farmer.id,
                Harvest.commodity == item["commodity"]
            ))).scalars().first()

            if not h:
                h = Harvest(
                    farmer_id=farmer.id,
                    quantity_kg=item["quantity_kg"],
                    commodity=item["commodity"],
                    status=HarvestStatus.REPORTED,
                    moisture=item["moisture_pct"],
                    ash=item["ash_pct"],
                    grade=QualityGrade.A,
                    base_price_per_kg=item["ask_jemput"],
                    total_price=item["quantity_kg"] * item["ask_jemput"],
                    listing_id=listing.id,
                    qr_code=f"QR-{farmer.username.upper()}-{item['commodity'].upper()}-{listing.id}",
                )
                s.add(h)
                await s.flush()
            else:
                h.quantity_kg = item["quantity_kg"]
                h.moisture = item["moisture_pct"]
                h.ash = item["ash_pct"]
                h.status = HarvestStatus.REPORTED
                h.listing_id = listing.id

            print(f"   🌾 Listing #{listing.id:2} | {farmer.username:15} | Komoditas: {item['commodity']:15} | Tonase: {item['quantity_kg']/1000:4.1f} Ton | MC: {item['moisture_pct']:4.1f}% | Ash: {item['ash_pct']:4.1f}% | Bulk Density: {item['bulk_density']} kg/m³")

        # 5. Injeksi Rute & Spesifikasi Truk Colt Diesel (Driver 1 & 2)
        print("\n[5/5] Menyiapkan Konfigurasi Armada Truk Colt Diesel (Driver 1 & 2)...")
        driver_configs = [
            ("driver_colt1", "AB-1234-CD", 16.0, 110.0),
            ("driver_colt2", "AB-5678-EF", 16.0, 200.0),
        ]
        for d_uname, plate, vol_m3, density in driver_configs:
            d_user = user_map[d_uname]
            r = (await s.execute(select(Route).where(
                Route.driver_id == d_user.id,
                Route.status == RouteStatus.PLANNED
            ))).scalars().first()
            if not r:
                r = Route(
                    driver_id=d_user.id,
                    vehicle_plate=plate,
                    vehicle_m3=vol_m3,
                    bulk_density=density,
                    status=RouteStatus.PLANNED,
                    total_ton=0.0,
                    total_m3=0.0,
                    total_km=0.0,
                )
                s.add(r)
                await s.flush()
            else:
                r.vehicle_plate = plate
                r.vehicle_m3 = vol_m3
                r.bulk_density = density
            print(f"   🚛 Truk Driver: {d_user.username:14} | Plat: {plate} | Kapasitas Bak: {vol_m3} m³ (Batas Maksimal 6.0 Ton)")

        await s.commit()

    print("\n================================================================================")
    print("✅ DATABASE SEEDING FASE 1 SELESAI DENGAN SUKSES!")
    print("   - 4 Petani (Sekam 12t, Jagung 10t, Tebu 15t, Sengon 14t)")
    print("   - 3 Pengepul Spesialis (Sekam, Jagung, Kayu/Serat) & 3 Gudang")
    print("   - 2 Driver Colt Diesel (Kapasitas Maksimal 6 Ton / 16 m³)")
    print("   - 2 Pabrik (Lini Pellet & Briket vs Lini Biochar & Silika)")
    print("   Password standar seluruh akun uji: password123")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(seed())
