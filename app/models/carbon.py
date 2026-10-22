"""F11 — Klaim removal karbon biochar dengan verifikator (empat mata).

Pabrik mengajukan klaim per periode: perhitungan dibekukan (snapshot + SHA-256), serah-terima biochar ke lahan
yang dipakai DIKUNCI ke klaim ini (satu serah-terima hanya boleh di satu klaim aktif → tidak hitung ganda), dan
hasil lab C-org & H/C-org wajib dilampirkan. Auditor (bukan pengaju) memutuskan diverifikasi/ditolak dengan alasan.
Ditolak → kunci dilepas sehingga serah-terima bisa diajukan ulang dalam klaim perbaikan.

Status "diverifikasi" = verifikasi INTERNAL. Tetap bukan kredit karbon sampai diverifikasi VVB & terdaftar SRN-PPI.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text

from ..database import Base

_now = lambda: datetime.now(timezone.utc)  # noqa: E731

CLAIM_STATUSES = ("diajukan", "diverifikasi", "ditolak")


class CarbonClaim(Base):
    __tablename__ = "carbon_claims"
    __table_args__ = (
        CheckConstraint("status IN ('diajukan', 'diverifikasi', 'ditolak')", name="ck_cclaim_status"),
        CheckConstraint("period_end > period_start", name="ck_cclaim_period"),
        CheckConstraint("lab_c_org_pct > 0 AND lab_c_org_pct <= 100", name="ck_cclaim_corg"),
        CheckConstraint("lab_h_corg_ratio > 0", name="ck_cclaim_hc"),
        CheckConstraint("verified_by_id IS NULL OR verified_by_id <> submitted_by_id", name="ck_cclaim_four_eyes"),
        CheckConstraint("status = 'diajukan' OR (verified_by_id IS NOT NULL AND decision_note IS NOT NULL)",
                        name="ck_cclaim_decided"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(24), nullable=False, unique=True)            # CLM-2610-001
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)      # eksklusif
    status = Column(String(12), nullable=False, default="diajukan", index=True)
    lab_c_org_pct = Column(Double, nullable=False)                    # % bk, hasil lab (menggantikan parameter F_C)
    lab_h_corg_ratio = Column(Double, nullable=False)                 # rasio molar H/C-org
    lab_name = Column(String(120), nullable=False)
    lab_report_no = Column(String(80), nullable=False)
    lab_report_url = Column(Text, nullable=False)                     # foto/scan laporan lab
    end_use_kg = Column(Double, nullable=False)                       # Σ serah-terima yang dikunci
    net_removal_tco2e = Column(Double, nullable=False)
    snapshot = Column(JSON, nullable=False)                           # hasil hitung + parameter saat diajukan
    snapshot_sha256 = Column(String(64), nullable=False)
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)


class CarbonClaimItem(Base):
    """Kunci serah-terima biochar → klaim. UNIQUE(redemption_id): satu serah-terima, satu klaim aktif."""
    __tablename__ = "carbon_claim_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("carbon_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    redemption_id = Column(Integer, ForeignKey("biochar_redemptions.id"), nullable=False, unique=True)
    kg = Column(Double, nullable=False)
