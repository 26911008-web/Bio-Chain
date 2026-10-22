"""Bukti bayar ke petani (F8) & persetujuan pemrosesan data pribadi (F12, UU 27/2022 PDP).

Rupiah di tabel ini memakai NUMERIC(14,0) (bilangan bulat Rupiah, tanpa galat float) — kolom harga lama
(`harvests.total_price` dll.) tetap Double; konversi dilakukan sekali di batas layanan (`services/payments.py`).
"""

from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint)

from ..database import Base

_now = lambda: datetime.now(timezone.utc)  # noqa: E731


class FarmerPayment(Base):
    """Pembayaran pengepul → petani atas satu harvest terverifikasi. Satu harvest = satu pembayaran."""
    __tablename__ = "farmer_payments"
    __table_args__ = (
        CheckConstraint("gross_rp >= 0 AND tax_rp >= 0 AND net_rp >= 0", name="ck_fpay_nonneg"),
        CheckConstraint("net_rp = gross_rp - tax_rp - dp_rp", name="ck_fpay_net"),
        CheckConstraint("dp_rp >= 0", name="ck_fpay_dp"),
        CheckConstraint("method IN ('tunai', 'transfer', 'qris', 'ewallet')", name="ck_fpay_method"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=False, unique=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    gross_rp = Column(Numeric(14, 0), nullable=False)
    tax_rp = Column(Numeric(14, 0), nullable=False, default=0)
    net_rp = Column(Numeric(14, 0), nullable=False)
    dp_rp = Column(Numeric(14, 0), nullable=False, default=0)   # uang muka yang dipotong saat pelunasan
    tax_basis = Column(String(80), nullable=True)
    method = Column(String(10), nullable=False)
    reference = Column(String(80), nullable=True)          # no. transfer / ref QRIS / "tunai"
    receipt_code = Column(String(40), nullable=False, unique=True)
    evidence_photo_url = Column(Text, nullable=True)
    client_event_id = Column(String(64), nullable=True, unique=True)
    paid_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class Consent(Base):
    """Jejak persetujuan (append-only). Persetujuan terbaru per (user, tujuan) yang berlaku."""
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("method IN ('aplikasi', 'lisan_via_pengepul', 'tertulis')", name="ck_consent_method"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purpose = Column(String(30), nullable=False)            # layanan_inti | lokasi_gps | foto_bukti
    version = Column(String(20), nullable=False)
    granted = Column(Boolean, nullable=False)
    method = Column(String(20), nullable=False, default="aplikasi")
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class DataRequest(Base):
    """Permintaan subjek data (ekspor / penghapusan) — bukti pemenuhan hak (UU PDP Pasal 5–11)."""
    __tablename__ = "data_requests"
    __table_args__ = (UniqueConstraint("receipt_code", name="uq_datareq_receipt"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)               # ekspor | hapus
    status = Column(String(10), nullable=False, default="selesai")
    receipt_code = Column(String(40), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)



class FarmerDownPayment(Base):
    """Uang muka (DP) pengepul → petani untuk mengikat lot (mis. setelah lelang diterima), dipotong saat pelunasan.

    Status: aktif → dipotong (lunas) | hangus_untuk_petani (pengepul membatalkan sepihak = kompensasi petani)
            | wajib_dikembalikan (stok tidak ada saat dijemput) → dikembalikan."""
    __tablename__ = "farmer_down_payments"
    __table_args__ = (
        CheckConstraint("amount_rp > 0", name="ck_fdp_amount"),
        CheckConstraint("method IN ('tunai', 'transfer', 'qris', 'ewallet')", name="ck_fdp_method"),
        CheckConstraint("status IN ('aktif', 'dipotong', 'hangus_untuk_petani', 'wajib_dikembalikan', 'dikembalikan')",
                        name="ck_fdp_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=False, unique=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount_rp = Column(Numeric(14, 0), nullable=False)
    method = Column(String(10), nullable=False)
    reference = Column(String(80), nullable=True)
    receipt_code = Column(String(40), nullable=False, unique=True)
    status = Column(String(24), nullable=False, default="aktif")
    status_note = Column(Text, nullable=True)
    client_event_id = Column(String(64), nullable=True, unique=True)
    paid_at = Column(DateTime(timezone=True), nullable=False, default=_now)
