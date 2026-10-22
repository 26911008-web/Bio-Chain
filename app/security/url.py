"""Validasi URL bukti serah-terima untuk mencegah XSS & injeksi skema."""

import re
from typing import Annotated
from pydantic import AfterValidator


def validate_evidence_url(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if v.startswith("/uploads/"):
        return v
    if re.match(r"^https?://[^\s/$.?#].[^\s]*$", v, re.IGNORECASE):
        return v
    raise ValueError("URL bukti tidak sah: hanya skema http://, https://, atau path /uploads/ yang diizinkan.")


EvidenceUrl = Annotated[str, AfterValidator(validate_evidence_url)]
