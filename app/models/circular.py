"""Pengambilan abu bottom ash oleh petani (sisi keluar "Dompet Abu Bottom Ash") untuk lahan sawah.

Alur fisik: petani mengajukan (kg, luas sawah, titik ambil) → pabrik menyerahkan karung di gudang/pengepul →
saat serah-terima barulah ledger `redemption` (negatif) ditulis. Permintaan yang belum diserahkan menahan saldo
(tidak bisa diajukan dua kali), tetapi belum mengurangi ledger — sama seperti stok yang dipesan tetapi belum keluar.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, JSON, CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text

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


class BiocharRequest(Base):
    """Permintaan abu bottom ash oleh petani yang disinkronkan dengan rute penjemputan armada pengepul (Reverse Logistics)."""
    __tablename__ = "biochar_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(36), unique=True, nullable=False)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    requested_kg = Column(Double, nullable=False)
    allocated_kg = Column(Double, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="REQUESTED", index=True)  # REQUESTED | ALLOCATED | LOADED_BACKHAUL | DELIVERED | CANCELLED
    delivery_point = Column(String(150), nullable=True)
    partition_safeguard_verified = Column(Boolean, nullable=False, default=True)  # bebas kontaminasi
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    delivered_at = Column(DateTime(timezone=True), nullable=True)


class BiocharDistribution(Base):
    """Distribusi muatan balik abu bottom ash dari pabrik ke gudang pengepul/armada."""
    __tablename__ = "biochar_distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dispatch_code = Column(String(36), unique=True, nullable=False)
    factory_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    vehicle_plate = Column(String(20), nullable=True)
    total_bags = Column(Integer, default=0)
    total_weight_kg = Column(Double, nullable=False)
    volume_m3 = Column(Double, nullable=False)
    loading_instructions = Column(Text, nullable=True)
    qr_dispatch_token = Column(String(64), unique=True, nullable=False)
    status = Column(String(25), nullable=False, default="DISPATCHED", index=True) # DISPATCHED | RECEIVED_BY_COLLECTOR | DELIVERED_TO_FARMER
    weighed_by_driver_kg = Column(Double, nullable=True)
    slip_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class BiocharQualityEvaluation(Base):
    """Formulir ulasan/rating kualitas abu bottom ash yang diterima petani dari pengepul/pabrik.
    Parameter evaluasi: ukuran butir/mesh, kematangan pirolisis/karbonisasi, kelembapan, dampak tanah.
    """
    __tablename__ = "biochar_quality_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    biochar_request_id = Column(Integer, ForeignKey("biochar_requests.id"), nullable=True, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    batch_code = Column(String(50), nullable=True, index=True)
    grain_size_mesh_rating = Column(Integer, nullable=False, default=5)     # 1-5 (butir/mesh)
    pyrolysis_maturity_rating = Column(Integer, nullable=False, default=5)  # 1-5 (kematangan pirolisis)
    moisture_rating = Column(Integer, nullable=False, default=5)            # 1-5 (kelembapan)
    soil_impact_rating = Column(Integer, nullable=False, default=5)         # 1-5 (dampak tanah/kesuburan)
    overall_score = Column(Double, nullable=False, default=5.0)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class BiocharCircularRequest(Base):
    """Permintaan abu bottom ash sirkular petani (Closed-loop supply chain)."""
    __tablename__ = "biochar_circular_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(40), unique=True, nullable=False)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("stock_listings.id"), nullable=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    requested_kg = Column(Double, nullable=False)
    allocated_kg = Column(Double, nullable=False, default=0.0)
    land_area_ha = Column(Double, nullable=True)
    delivery_point = Column(String(200), nullable=False, default="Lahan Petani")
    status = Column(String(30), nullable=False, default="REQUESTED", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)



