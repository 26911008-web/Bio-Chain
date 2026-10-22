"""F14 — QR lot bertanda tangan HMAC.

Format baru: ``BIO-XXXXXXXX-TTTTTT`` (8 heks acak + 6 karakter base32 HMAC-SHA256 dengan kunci server).
- QR palsu (dibuat dari generator QR/aplikasi lain) atau salah ketik saat input manual langsung dikenali.
- Rute driver memuat *digest* satu arah per stop → HP supir bisa mencocokkan QR **tanpa sinyal** di lokasi,
  tanpa pernah melihat kodenya. Tebak-paksa digest butuh ±2^62 percobaan karena tag bergantung kunci server.

QR lama ``BIO-XXXXXXXX`` (sudah tercetak di nota/karung) tetap diterima selama parameter
``logistik.qr_legacy_policy`` = ``terima_tandai``; pickup-nya ditandai untuk auditor. Tidak ada digest offline
untuk QR lama (32 bit terlalu mudah ditebak-paksa dari digest).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

from ..config import settings

_SIGNED = re.compile(r"^BIO-[0-9A-F]{8}-[A-Z2-7]{6}$")
TAG_LEN = 6


def _key() -> bytes:
    raw = getattr(settings, "QR_HMAC_KEY", "") or ""
    # Tanpa kunci khusus: turunkan dari JWT_SECRET (domain terpisah) — rotasi JWT_SECRET membatalkan QR yang tercetak,
    # jadi produksi sebaiknya mengisi QR_HMAC_KEY sendiri.
    return raw.encode() if raw else hmac.new(settings.JWT_SECRET.encode(), b"biochain-qr-v1", hashlib.sha256).digest()


def _tag(base: str) -> str:
    mac = hmac.new(_key(), f"qr|{base}".encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:TAG_LEN]


def normalize(code: str | None) -> str:
    """Toleran input manual: spasi/huruf kecil/strip ganda diabaikan."""
    return re.sub(r"\s+", "", (code or "")).upper().replace("--", "-")


def new_qr_code(harvest_uuid: str | None = None) -> str:
    base = f"BIO-{(harvest_uuid or secrets.token_hex(4)).replace('-', '')[:8].upper()}"
    return f"{base}-{_tag(base)}"


def is_signed(code: str) -> bool:
    return bool(_SIGNED.match(code or ""))


def signature_valid(code: str) -> bool:
    c = normalize(code)
    if not is_signed(c):
        return False
    base, tag = c.rsplit("-", 1)
    return hmac.compare_digest(tag, _tag(base))


def check_scan(scanned: str | None, stored: str | None) -> str:
    """'ok' | 'ok_legacy' | 'tidak_sah' (format bertanda tangan tapi tag salah: palsu/salah ketik) | 'beda_lot'."""
    s, st = normalize(scanned), normalize(stored)
    if is_signed(s) and not signature_valid(s):
        return "tidak_sah"
    if not st or not hmac.compare_digest(s, st):
        return "beda_lot"
    return "ok" if is_signed(st) else "ok_legacy"


def offline_check(stored: str | None, stop_id: int) -> dict | None:
    """Digest SHA-256(salt + QR) untuk cek offline di HP supir. Hanya untuk QR bertanda tangan."""
    st = normalize(stored)
    if not is_signed(st):
        return None
    salt = hmac.new(_key(), f"salt|{stop_id}".encode(), hashlib.sha256).hexdigest()[:16]
    return {"salt": salt, "sha256": hashlib.sha256((salt + st).encode()).hexdigest()}
