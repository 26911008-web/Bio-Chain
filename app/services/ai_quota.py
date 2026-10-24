"""Kuota harian Asisten AI per akun (tabel `user_ai_usage`, migrations/029_ai_daily_quota.sql).

Pemesanan kuota = SATU pernyataan UPSERT atomik (SQLite ≥ 3.35 dan PostgreSQL): reset otomatis bila tanggal
lokal berganti, tambah 1 bila masih di bawah batas, dan tidak mengubah apa pun bila kuota habis (RETURNING
kosong). Kuota dipesan SEBELUM LLM dipanggil, sehingga dua permintaan bersamaan tidak bisa sama-sama lolos
di hitungan terakhir; bila provider gagal sebelum mengirim jawaban, kuota dikembalikan (`refund`).
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import db_manager
from ..models.ai_usage import UserAIUsage
from ..security.rls import bind_identity

_TZ_LABEL = {7: "WIB", 8: "WITA", 9: "WIT", 0: "UTC"}

_CONSUME = text("""
INSERT INTO user_ai_usage (user_id, request_count, last_reset_date) VALUES (:uid, 1, :today)
ON CONFLICT (user_id) DO UPDATE SET
  request_count = CASE WHEN user_ai_usage.last_reset_date < :today THEN 1
                       ELSE user_ai_usage.request_count + 1 END,
  last_reset_date = :today
WHERE user_ai_usage.last_reset_date < :today OR user_ai_usage.request_count < :limit
RETURNING request_count
""").bindparams(bindparam("today", type_=Date))

_REFUND = text("""
UPDATE user_ai_usage SET request_count = request_count - 1
WHERE user_id = :uid AND last_reset_date = :today AND request_count > 0
""").bindparams(bindparam("today", type_=Date))


def _tz() -> timezone:
    return timezone(timedelta(hours=settings.AI_QUOTA_UTC_OFFSET_HOURS))


def tz_label() -> str:
    h = settings.AI_QUOTA_UTC_OFFSET_HOURS
    return _TZ_LABEL.get(h, f"UTC{h:+d}")


def quota_day(now: datetime | None = None) -> date:
    """Tanggal kuota = tanggal di zona waktu lokal (default WIB), bukan tanggal UTC."""
    return (now or datetime.now(timezone.utc)).astimezone(_tz()).date()


def exhausted_message() -> str:
    return (f"Kuota harian Anda sudah habis (maksimal {settings.AI_DAILY_QUOTA} pertanyaan/hari). "
            f"Kuota direset pukul 00.00 {tz_label()}.")


async def consume(db: AsyncSession, user_id: int) -> int | None:
    """Pesan 1 kuota. Kembalikan sisa kuota hari ini; None bila kuota tidak dibatasi (AI_DAILY_QUOTA=0).
    Melempar QuotaExhausted bila sudah habis. Pemanggil yang meng-commit transaksi."""
    if settings.AI_DAILY_QUOTA <= 0:
        return None
    row = (await db.execute(_CONSUME, {"uid": user_id, "today": quota_day(),
                                       "limit": settings.AI_DAILY_QUOTA})).first()
    if row is None:
        raise QuotaExhausted(exhausted_message())
    return max(settings.AI_DAILY_QUOTA - int(row[0]), 0)


async def refund(db: AsyncSession, user_id: int) -> None:
    """Kembalikan 1 kuota hari ini (provider gagal sebelum jawaban terkirim)."""
    if settings.AI_DAILY_QUOTA > 0:
        await db.execute(_REFUND, {"uid": user_id, "today": quota_day()})


async def refund_detached(user_id: int, role: str) -> None:
    """`refund` dengan sesi sendiri — untuk generator streaming (sesi request sudah ditutup)."""
    async with db_manager.async_session() as s:
        bind_identity(s, user_id, role)
        await refund(s, user_id)
        await s.commit()


async def status(db: AsyncSession, user_id: int) -> dict:
    """Sisa kuota hari ini untuk ditampilkan di UI (tanpa mengubah apa pun)."""
    limit = settings.AI_DAILY_QUOTA
    if limit <= 0:
        return {"limit": None, "used": 0, "remaining": None, "resets_at": None}
    today = quota_day()
    row = (await db.execute(select(UserAIUsage.request_count, UserAIUsage.last_reset_date)
                            .where(UserAIUsage.user_id == user_id))).first()
    used = int(row[0]) if row and row[1] == today else 0
    resets_at = datetime.combine(today + timedelta(days=1), time(0), tzinfo=_tz())
    return {"limit": limit, "used": used, "remaining": max(limit - used, 0),
            "resets_at": resets_at.isoformat(), "tz": tz_label()}


class QuotaExhausted(Exception):
    pass
