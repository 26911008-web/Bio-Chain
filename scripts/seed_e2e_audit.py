"""Skrip Seeder E2E Scientific Audit — Bio-Chain v2.

Menyuntikkan data uji deterministik:
- 3 Akun Petani dengan Stok Sekam (kadar air 15%, volume 1000 kg per petani)
- 2 Akun Pengepul (KUD Sleman Timur & Barat)
- 1 Akun Pabrik Pirolisis Biochar
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete
from app.database import async_session, engine, Base
from app.models.user import User, UserRole, IncentiveTier
from app.models.trade import StockListing, ListingStatus, DeliveryScheme
from app.models.harvest import Mill
from app.routers.auth import hash_password


USERS_TO_SEED = [
    # 3 Petani
    {
        "username": "petani_audit1",
        "phone": "081911110001",
        "email": "petani1@audit.biochain.id",
        "password": "password123",
        "full_name": "Pak Joko (Godean)",
        "role": UserRole.PETANI,
        "kecamatan": "Godean",
        "kabupaten": "Sleman",
        "lat": -7.768,
        "lon": 110.293,
    },
    {
        "username": "petani_audit2",
        "phone": "081911110002",
        "email": "petani2@audit.biochain.id",
        "password": "password123",
        "full_name": "Bu Sri (Moyudan)",
        "role": UserRole.PETANI,
        "kecamatan": "Moyudan",
        "kabupaten": "Sleman",
        "lat": -7.773,
        "lon": 110.244,
    },
    {
        "username": "petani_audit3",
        "phone": "081911110003",
        "email": "petani3@audit.biochain.id",
        "password": "password123",
        "full_name": "Pak Hadi (Seyegan)",
        "role": UserRole.PETANI,
        "kecamatan": "Seyegan",
        "kabupaten": "Sleman",
        "lat": -7.725,
        "lon": 110.301,
    },
    # 2 Pengepul
    {
        "username": "pengepul_audit1",
        "phone": "081322220001",
        "email": "kud.timur@audit.biochain.id",
        "password": "password123",
        "full_name": "Pak Surya (KUD Sleman Timur)",
        "role": UserRole.PENGEPUL,
        "kecamatan": "Sleman",
        "kabupaten": "Sleman",
        "lat": -7.700,
        "lon": 110.350,
    },
    {
        "username": "pengepul_audit2",
        "phone": "081322220002",
        "email": "kud.barat@audit.biochain.id",
        "password": "password123",
        "full_name": "Pak Bowo (KUD Sleman Barat)",
        "role": UserRole.PENGEPUL,
        "kecamatan": "Godean",
        "kabupaten": "Sleman",
        "lat": -7.760,
        "lon": 110.310,
    },
    # 1 Pabrik
    {
        "username": "pabrik_audit",
        "phone": "081233330001",
        "email": "plant@audit.biochain.id",
        "password": "password123",
        "full_name": "PT Biochar Nusaprima (Plant Ngaglik)",
        "role": UserRole.PABRIK,
        "kecamatan": "Ngaglik",
        "kabupaten": "Sleman",
        "lat": -7.712,
        "lon": 110.385,
    },
]


async def seed():
    print("🌱 Memulai Injeksi Data Uji Deterministik...")
    async with async_session() as s:
        # Cari atau buat users
        user_map = {}
        for udata in USERS_TO_SEED:
            existing = (await s.execute(select(User).where(User.username == udata["username"]))).scalar_one_or_none()
            if existing:
                existing.is_active = True
                user_map[udata["username"]] = existing
            else:
                user = User(
                    username=udata["username"],
                    phone=udata["phone"],
                    email=udata["email"],
                    password_hash=hash_password(udata["password"]),
                    full_name=udata["full_name"],
                    role=udata["role"],
                    is_active=True,
                    kecamatan=udata["kecamatan"],
                    kabupaten=udata["kabupaten"],
                    lat=udata["lat"],
                    lon=udata["lon"],
                    xp_total=500,
                    incentive_tier=IncentiveTier.PEMASOK_AKTIF,
                )
                s.add(user)
                await s.flush()
                user_map[udata["username"]] = user

        print(f"✅ 6 Akun Terverifikasi (3 Petani, 2 Pengepul, 1 Pabrik)")

        # Ambil mill referensi jika ada
        mill = (await s.execute(select(Mill).limit(1))).scalar_one_or_none()
        mill_id = mill.id if mill else None

        # Suntikkan 3 Listing Stok Sekam (1000 kg, kadar air 15%)
        created_listings = []
        for uname in ["petani_audit1", "petani_audit2", "petani_audit3"]:
            farmer = user_map[uname]
            # Cek apakah sudah ada listing open
            cur_listing = (await s.execute(select(StockListing).where(
                StockListing.farmer_id == farmer.id,
                StockListing.status == ListingStatus.OPEN
            ))).scalar_one_or_none()

            if not cur_listing:
                listing = StockListing(
                    farmer_id=farmer.id,
                    mill_id=mill_id,
                    quantity_kg=1000.0,
                    remaining_kg=1000.0,
                    moisture_pct=15.0,
                    grade_estimate="B",
                    allow_jemput=True,
                    allow_antar=True,
                    ask_price_jemput=400.0,
                    ask_price_antar=520.0,
                    lat=farmer.lat,
                    lon=farmer.lon,
                    status=ListingStatus.OPEN,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=14),
                    version=1,
                )
                s.add(listing)
                await s.flush()
                created_listings.append(listing)
            else:
                cur_listing.quantity_kg = 1000.0
                cur_listing.remaining_kg = 1000.0
                cur_listing.moisture_pct = 15.0
                created_listings.append(cur_listing)

        await s.commit()
        print(f"✅ 3 Stok Sekam Siap Bidding: 1000 kg per petani (Kadar Air 15.0%, Grade B)")
        for l in created_listings:
            print(f"   - Listing #{l.id} | Petani ID: {l.farmer_id} | Stok: {l.remaining_kg} kg | Air: {l.moisture_pct}%")


if __name__ == "__main__":
    asyncio.run(seed())
