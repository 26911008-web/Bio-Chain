"""Bio-Chain v2 — Seed 40+ Real Dedicated Accounts for Concurrency & Load Testing.

Creates 40 distinct user accounts spanning all 5 persona roles:
- 15 Petani (petani_01 .. petani_15)
- 15 Pengepul (pengepul_01 .. pengepul_15)
- 4 Driver (driver_01 .. driver_04)
- 4 Pabrik (pabrik_01 .. pabrik_04)
- 2 Auditor (auditor_01 .. auditor_02)
Total = 40 accounts with role-based attributes and is_active=True.
"""

import asyncio
from sqlalchemy import select
from app.database import db_manager
from app.models.user import User, UserRole, IncentiveTier
from app.models.harvest import Harvest, HarvestStatus, QualityGrade, Mill
from app.models.trade import StockListing
from app.routers.auth import hash_password
from app.security.rls import SYSTEM_IDENTITY, bind_identity, apply_now

PASSWORD_DEFAULT = "BioChain2026!"

ACCOUNTS_SPECS = []

# 15 Petani
for i in range(1, 16):
    num_str = f"{i:02d}"
    ACCOUNTS_SPECS.append({
        "username": f"petani_{num_str}",
        "phone": f"081100010{num_str}",
        "email": f"petani_{num_str}@biochain.id",
        "full_name": f"Petani Sleman #{num_str}",
        "role": UserRole.PETANI,
        "kabupaten": "Sleman",
        "kecamatan": ["Godean", "Moyudan", "Seyegan", "Mlati", "Minggir"][i % 5],
        "lat": -7.76 + (i * 0.005),
        "lon": 110.28 + (i * 0.005),
        "xp_total": 500 + i * 50,
        "tier": IncentiveTier.MITRA_EMAS if i % 2 == 0 else IncentiveTier.PEMASOK_AKTIF,
    })

# 15 Pengepul
for i in range(1, 16):
    num_str = f"{i:02d}"
    ACCOUNTS_SPECS.append({
        "username": f"pengepul_{num_str}",
        "phone": f"081200020{num_str}",
        "email": f"pengepul_{num_str}@biochain.id",
        "full_name": f"Pengepul Hub #{num_str}",
        "role": UserRole.PENGEPUL,
        "kabupaten": "Sleman",
        "kecamatan": ["Sleman", "Tempel", "Ngaglik", "Kalasan", "Depok"][i % 5],
        "lat": -7.71 + (i * 0.004),
        "lon": 110.34 + (i * 0.004),
    })

# 4 Driver
for i in range(1, 5):
    num_str = f"{i:02d}"
    ACCOUNTS_SPECS.append({
        "username": f"driver_{num_str}",
        "phone": f"081300030{num_str}",
        "email": f"driver_{num_str}@biochain.id",
        "full_name": f"Driver Armada #{num_str}",
        "role": UserRole.DRIVER,
        "kabupaten": "Sleman",
        "kecamatan": "Mlati",
        "lat": -7.73 + (i * 0.003),
        "lon": 110.33 + (i * 0.003),
    })

# 4 Pabrik
for i in range(1, 5):
    num_str = f"{i:02d}"
    ACCOUNTS_SPECS.append({
        "username": f"pabrik_{num_str}",
        "phone": f"081400040{num_str}",
        "email": f"pabrik_{num_str}@biochain.id",
        "full_name": f"Pabrik Pirolisis Unit #{num_str}",
        "role": UserRole.PABRIK,
        "kabupaten": "Sleman",
        "kecamatan": "Ngaglik",
        "lat": -7.76 + (i * 0.002),
        "lon": 110.38 + (i * 0.002),
    })

# 2 Auditor
for i in range(1, 3):
    num_str = f"{i:02d}"
    ACCOUNTS_SPECS.append({
        "username": f"auditor_{num_str}",
        "phone": f"081500050{num_str}",
        "email": f"auditor_{num_str}@biochain.id",
        "full_name": f"Auditor ESG #{num_str}",
        "role": UserRole.AUDITOR,
        "kabupaten": "Sleman",
        "kecamatan": "Depok",
        "lat": -7.77,
        "lon": 110.38,
    })


async def seed_40_accounts():
    async with db_manager.async_session() as db:
        bind_identity(db, *SYSTEM_IDENTITY)
        await apply_now(db)

        # Get a mill for harvests
        res_m = await db.execute(select(Mill).limit(1))
        mill = res_m.scalar_one_or_none()
        mill_id = mill.id if mill else None

        created_count = 0
        updated_count = 0
        created_users = []

        hashed_pw = hash_password(PASSWORD_DEFAULT)

        for spec in ACCOUNTS_SPECS:
            res = await db.execute(
                select(User).where((User.username == spec["username"]) | (User.phone == spec["phone"]))
            )
            u = res.scalar_one_or_none()
            if not u:
                u = User(
                    username=spec["username"],
                    phone=spec["phone"],
                    email=spec.get("email"),
                    password_hash=hashed_pw,
                    full_name=spec["full_name"],
                    role=spec["role"],
                    is_active=True,
                    kabupaten=spec.get("kabupaten", "Sleman"),
                    kecamatan=spec.get("kecamatan"),
                    lat=spec.get("lat"),
                    lon=spec.get("lon"),
                    xp_total=spec.get("xp_total", 0),
                    incentive_tier=spec.get("tier", IncentiveTier.PEMULA),
                )
                db.add(u)
                await db.flush()
                created_count += 1
            else:
                u.is_active = True
                u.password_hash = hashed_pw
                updated_count += 1
            created_users.append(u)

        # Ensure each Petani has at least 1 harvest and 1 listing so market has active supply
        petani_users = [u for u in created_users if u.role == UserRole.PETANI]
        listings_added = 0
        for idx, pu in enumerate(petani_users):
            # Check existing listings
            res_l = await db.execute(select(StockListing).where(StockListing.farmer_id == pu.id))
            if not res_l.scalar_one_or_none():
                # Create harvest
                h = Harvest(
                    farmer_id=pu.id,
                    mill_id=mill_id,
                    quantity_kg=2000.0 + (idx * 150),
                    status=HarvestStatus.REPORTED,
                    qr_code=f"QR-PET-{pu.id}-{idx}",
                )
                db.add(h)
                await db.flush()

                # Create listing
                lst = StockListing(
                    farmer_id=pu.id,
                    mill_id=mill_id,
                    quantity_kg=h.quantity_kg,
                    remaining_kg=h.quantity_kg,
                    moisture_pct=11.5 + (idx % 4) * 0.5,
                    allow_jemput=True,
                    ask_price_jemput=400.0 + (idx * 5),
                    allow_antar=True,
                    ask_price_antar=480.0 + (idx * 5),
                    status="open",
                )
                db.add(lst)
                listings_added += 1

        await db.commit()

        print(f"✅ Seeding Complete!")
        print(f"Total target accounts: {len(ACCOUNTS_SPECS)}")
        print(f"Created accounts: {created_count}")
        print(f"Updated accounts: {updated_count}")
        print(f"New stock listings created for Petani: {listings_added}")


if __name__ == "__main__":
    asyncio.run(seed_40_accounts())
