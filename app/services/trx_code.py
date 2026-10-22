"""Generator resi serah-terima atomik: TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[SEQ].

Contoh: TRX-PTN0005-PGP0003-2610-00042 = serah-terima ke-42 dari Petani #5 ke Pengepul #3 pada
Oktober 2026 (WIB). Nomor urut di-reset tiap bulan per pasangan pengirim–penerima.

Atomisitas: satu pernyataan UPSERT
    INSERT ... ON CONFLICT (sender, receiver, yymm) DO UPDATE SET last_seq = last_seq + 1 RETURNING last_seq
Baris penghitung terkunci selama transaksi (PostgreSQL row lock; SQLite penulis tunggal), sehingga dua
serah-terima serentak tidak pernah mendapat nomor sama — tanpa SELECT-lalu-UPDATE yang rawan race.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.trade import TrxSequence
from ..models.user import User, UserRole

WIB = timezone(timedelta(hours=7))          # offset tetap: Windows tidak selalu punya basis data tz
ROLE_CODE = {UserRole.PETANI: "PTN", UserRole.PENGEPUL: "PGP", UserRole.DRIVER: "DRV",
             UserRole.PABRIK: "PBK", UserRole.ADMIN: "ADM", UserRole.AUDITOR: "AUD"}


def party_code(user: User) -> str:
    role = UserRole(user.role.value if hasattr(user.role, "value") else user.role)
    return f"{ROLE_CODE[role]}{user.id:04d}"


def yymm(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(WIB).strftime("%y%m")


async def next_seq(db: AsyncSession, sender: str, receiver: str, period: str) -> int:
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(TrxSequence).values(sender_code=sender, receiver_code=receiver, yymm=period, last_seq=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sender_code", "receiver_code", "yymm"],
        set_={"last_seq": TrxSequence.last_seq + 1},
    ).returning(TrxSequence.last_seq)
    return int((await db.execute(stmt)).scalar_one())


async def new_verification_code(db: AsyncSession, sender: User, receiver: User, now: datetime | None = None) -> str:
    s, r, p = party_code(sender), party_code(receiver), yymm(now)
    return f"TRX-{s}-{r}-{p}-{await next_seq(db, s, r, p):05d}"
