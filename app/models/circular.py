"""Pengambilan biochar oleh petani (sisi keluar "Dompet Biochar") untuk lahan sawah.

Alur fisik: petani mengajukan (kg, luas sawah, titik ambil) → pabrik menyerahkan karung di gudang/pengepul →
saat serah-terima barulah ledger `redemption` (negatif) ditulis. Permintaan yang belum diserahkan menahan saldo
(tidak bisa diajukan dua kali), tetapi belum mengurangi ledger — sama seperti stok yang dipesan tetapi belum keluar.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text

from ..database import Base

_now = lambda: datetime.now(timezone.utc)  # noqa: E731

REDEMPTION_STATUSES = ("diajukan", "diserahkan", "dibatalkan")
PICKUP_POINTS = ("pabrik", "pengepul")


class BiocharRedemption(Base):
    __tablename__ = "biochar_redemptions"
    __table_args__ = (
        CheckConstraint("kg > 0", name="ck_bredeem_kg_pos"),
        CheckConstraint("land_area_ha IS NULL OR land_area_ha > 0", name="ck_bredeem_area_pos"),
        CheckConstraint("status IN ('diajukan', 'diserahkan', 'dibatalkan')", name="ck_bredeem_status"),
        CheckConstraint("pickup_point IN ('pabrik', 'pengepul')", name="ck_bredeem_pickup"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kg = Column(Double, nullable=False)
    land_area_ha = Column(Double, nullable=True)            # luas sawah tujuan aplikasi
    pickup_point = Column(String(10), nullable=False, default="pabrik")
    status = Column(String(12), nullable=False, default="diajukan", index=True)
    note = Column(Text, nullable=True)
    estimate = Column(JSON, nullable=True)                  # snapshot rumus manfaat saat diajukan (audit)
    ledger_entry_id = Column(Integer, ForeignKey("biochar_ledger.id"), nullable=True)
    handed_over_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    handed_over_at = Column(DateTime(timezone=True), nullable=True)
    cancel_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


EFFICIENCY_PROCESSES = ("lapor_stok", "uji_mutu", "jemput_rute", "angkut", "terima_pabrik", "produksi", "energi",
                        "pembayaran", "biochar_sawah", "lainnya")
EFFICIENCY_STATUSES = ("rencana", "berjalan", "terverifikasi", "batal")


class EfficiencyAction(Base):
    """Register penghematan & pengurangan dampak lingkungan per proses rantai pasok.

    Baris ditulis manusia (aksi perbaikan + bukti); penghematan OTOMATIS dari data (rute teroptimasi, biochar ke
    sawah, pembakaran terbuka dihindari) dihitung on-the-fly di services/efficiency.py dan tidak disimpan di sini,
    sehingga tidak terhitung dua kali."""
    __tablename__ = "efficiency_actions"
    __table_args__ = (
        CheckConstraint("status IN ('rencana', 'berjalan', 'terverifikasi', 'batal')", name="ck_effact_status"),
        CheckConstraint("saving_rp IS NULL OR saving_rp >= 0", name="ck_effact_rp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    process = Column(String(20), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    metric = Column(String(60), nullable=True)             # mis. "kWh/t sekam", "km/t", "% lot ditolak"
    baseline_value = Column(Double, nullable=True)
    current_value = Column(Double, nullable=True)
    saving_rp = Column(Double, nullable=True)               # per periode
    saving_co2e_kg = Column(Double, nullable=True)          # per periode (boleh negatif bila menambah emisi)
    period = Column(String(7), nullable=True)               # YYYY-MM tercatat
    status = Column(String(14), nullable=False, default="rencana", index=True)
    evidence = Column(Text, nullable=True)                  # tautan foto/nota/hasil meter
    source_opportunity = Column(String(40), nullable=True)  # kode peluang yang ditindaklanjuti
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)
