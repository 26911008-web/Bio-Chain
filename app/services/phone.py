"""Normalisasi nomor HP Indonesia (F6).

Bentuk kanonik tetap `08…` (format yang sudah tersimpan di data & dipakai login), sehingga normalisasi tidak
mengubah akun lama. Diterima: `+62 812-3456-7890`, `62812…`, `0062812…`, `0812 3456 7890`, `(0812) 3456.7890`.
Panjang nomor seluler Indonesia: 08 + 8–11 digit (total 10–13 digit).
"""

import re

_DIGITS = re.compile(r"\D+")
MOBILE = re.compile(r"^08\d{8,11}$")


def normalize_phone(raw: str | None) -> str | None:
    """Kembalikan bentuk `08…` atau None bila bukan nomor HP Indonesia yang sah."""
    if not raw:
        return None
    s = raw.strip()
    if not re.fullmatch(r"[\d\s+().\-]+", s):
        return None
    d = _DIGITS.sub("", s)
    if d.startswith("0062"):
        d = "0" + d[4:]
    elif d.startswith("62"):
        d = "0" + d[2:]
    elif d.startswith("8"):
        d = "0" + d
    return d if MOBILE.match(d) else None


def require_phone(raw: str) -> str:
    """Untuk validator Pydantic: normalisasi atau tolak dengan pesan yang jelas."""
    out = normalize_phone(raw)
    if out is None:
        raise ValueError("Nomor HP tidak valid. Gunakan nomor seluler Indonesia, mis. 0812 3456 7890 atau +62 812 3456 7890.")
    return out
