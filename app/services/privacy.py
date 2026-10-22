"""Perlindungan data pribadi (F12, UU 27/2022 PDP) & petani tanpa HP (F7).

- Persetujuan dicatat append-only (`consents`); yang berlaku = entri terbaru per tujuan.
- Ekspor data subjek: profil + seluruh catatan transaksi miliknya (JSON, bisa diunduh).
- Hapus akun = ANONIMISASI: identitas (nama, HP, username, email, lokasi) dihapus permanen; catatan transaksi
  (timbangan, pembayaran, biochar) tetap untuk kewajiban audit/pajak, tetapi tidak lagi terhubung ke orang.
- Nomor HP disamarkan di daftar lintas-pengguna (minimisasi data); nomor lengkap hanya lewat aksi "hubungi".
"""

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.compliance import Consent, DataRequest, FarmerPayment
from ..models.harvest import Harvest
from ..models.ledger import BiocharLedgerEntry, CustodyEvent
from ..models.trade import Bid, StockListing
from ..models.user import User, UserRole

CONSENT_VERSION = "2026-10"
PURPOSES = {
    "layanan_inti": "Memproses identitas, lokasi penggilingan, timbangan & pembayaran untuk jual-beli sekam (wajib)",
    "lokasi_gps": "Merekam lokasi GPS saat penjemputan/rute untuk bukti serah-terima & emisi angkut",
    "foto_bukti": "Menyimpan foto bukti timbangan/serah-terima",
}
PROXY_PHONE_PREFIX = "NOHP-"
DELETED_PHONE_PREFIX = "DEL-"


def has_real_phone(phone: str | None) -> bool:
    """False untuk petani tanpa HP (NOHP-…) dan akun yang dianonimkan (DEL-…)."""
    return bool(phone) and not phone.startswith((PROXY_PHONE_PREFIX, DELETED_PHONE_PREFIX))


def mask_phone(phone: str | None) -> str | None:
    if not has_real_phone(phone):
        return None
    return phone[:4] + "*" * max(len(phone) - 8, 2) + phone[-4:] if len(phone) >= 10 else "****"


def _receipt(kind: str) -> str:
    return f"PDP-{kind.upper()[:3]}-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"


async def record_consents(db: AsyncSession, user_id: int, choices: dict[str, bool], method: str = "aplikasi",
                          recorded_by_id: int | None = None) -> None:
    for purpose, granted in choices.items():
        if purpose not in PURPOSES:
            raise HTTPException(422, f"Tujuan persetujuan tidak dikenal: {purpose}")
        db.add(Consent(user_id=user_id, purpose=purpose, version=CONSENT_VERSION, granted=bool(granted),
                       method=method, recorded_by_id=recorded_by_id))


async def current_consents(db: AsyncSession, user_id: int) -> dict:
    rows = (await db.execute(select(Consent).where(Consent.user_id == user_id).order_by(Consent.id))).scalars().all()
    latest = {}
    for c in rows:
        latest[c.purpose] = {"granted": c.granted, "version": c.version, "method": c.method,
                             "at": c.created_at.isoformat() if c.created_at else None}
    return {"version": CONSENT_VERSION,
            "purposes": [{"purpose": p, "description": d, **(latest.get(p) or {"granted": None})}
                         for p, d in PURPOSES.items()],
            "needs_consent": (latest.get("layanan_inti") or {}).get("granted") is not True
                             or (latest.get("layanan_inti") or {}).get("version") != CONSENT_VERSION}


def _row(obj, cols) -> dict:
    out = {}
    for c in cols:
        v = getattr(obj, c, None)
        out[c] = v.value if hasattr(v, "value") else (v.isoformat() if isinstance(v, datetime) else
                                                      (int(v) if c.endswith("_rp") and v is not None else v))
    return out


async def export_data(db: AsyncSession, user: User) -> dict:
    uid = user.id
    harvests = (await db.execute(select(Harvest).where(or_(Harvest.farmer_id == uid, Harvest.collector_id == uid))
                                 .order_by(Harvest.id))).scalars().all()
    payments = (await db.execute(select(FarmerPayment).where(or_(FarmerPayment.farmer_id == uid,
                                                                 FarmerPayment.collector_id == uid)))).scalars().all()
    listings = (await db.execute(select(StockListing).where(StockListing.farmer_id == uid))).scalars().all()
    bids = (await db.execute(select(Bid).where(or_(Bid.collector_id == uid, Bid.farmer_id == uid)))).scalars().all()
    ledger = (await db.execute(select(BiocharLedgerEntry).where(BiocharLedgerEntry.farmer_id == uid))).scalars().all()
    events = (await db.execute(select(CustodyEvent).where(CustodyEvent.actor_id == uid)
                               .order_by(CustodyEvent.id))).scalars().all()
    db.add(DataRequest(user_id=uid, kind="ekspor", status="selesai", receipt_code=(code := _receipt("ekspor"))))
    await db.commit()
    return {
        "receipt_code": code, "generated_at": datetime.now(timezone.utc).isoformat(),
        "legal_basis": "UU 27/2022 Pelindungan Data Pribadi — hak akses & portabilitas data",
        "profile": _row(user, ["id", "username", "phone", "email", "full_name", "role", "kecamatan", "kabupaten",
                               "lat", "lon", "xp_total", "created_at"]),
        "consents": await current_consents(db, uid),
        "harvests": [_row(h, ["id", "qr_code", "status", "quantity_kg", "verified_kg", "received_kg", "grade",
                              "moisture", "total_price", "reported_at", "verified_at", "delivered_at"]) for h in harvests],
        "farmer_payments": [_row(p, ["id", "harvest_id", "gross_rp", "tax_rp", "net_rp", "method", "reference",
                                     "receipt_code", "paid_at"]) for p in payments],
        "stock_listings": [_row(x, ["id", "quantity_kg", "remaining_kg", "status", "created_at"]) for x in listings],
        "bids": [_row(b, ["id", "listing_id", "price_per_kg", "quantity_kg", "status", "created_at"]) for b in bids],
        "biochar_ledger": [_row(e, ["id", "entry_type", "amount_kg", "created_at"]) for e in ledger],
        "custody_events": [_row(e, ["id", "harvest_id", "stage", "weight_kg", "verification_code", "lat", "lon",
                                    "created_at"]) for e in events],
    }


async def anonymize(db: AsyncSession, user: User, reason: str | None) -> dict:
    if user.anonymized_at:
        raise HTTPException(409, "Akun sudah dianonimkan.")
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role == UserRole.ADMIN.value:
        others = (await db.execute(select(User.id).where(User.role == UserRole.ADMIN, User.id != user.id,
                                                         User.is_active.is_(True), User.anonymized_at.is_(None)))).first()
        if not others:
            raise HTTPException(409, "Tidak bisa menghapus admin aktif terakhir.")
    from ..routers.auth import hash_password
    from ..concurrency import run_cpu
    tag = secrets.token_hex(4)
    user.full_name = f"Pengguna terhapus #{user.id}"
    user.phone = f"{DELETED_PHONE_PREFIX}{user.id}-{tag}"[:20]
    user.username = None
    user.email = None
    user.lat = user.lon = None
    user.password_hash = await run_cpu(hash_password, secrets.token_urlsafe(24))
    user.is_active = False
    user.anonymized_at = datetime.now(timezone.utc)
    db.add(DataRequest(user_id=user.id, kind="hapus", status="selesai", receipt_code=(code := _receipt("hapus")),
                       note=(reason or "")[:500] or None))
    await db.commit()
    return {"receipt_code": code, "status": "dianonimkan",
            "kept": "Catatan timbangan, pembayaran & biochar disimpan tanpa identitas untuk kewajiban audit/pajak."}
