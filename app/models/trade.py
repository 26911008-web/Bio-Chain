"""SQLAlchemy ORM — Pasar B2B sekam: listing stok petani, tawaran pengepul, penomoran resi.

Dua skema serah (setara Incoterms 2020, ICC):
  - "jemput" ≈ EXW: pengepul mengambil di lokasi petani; harga = harga di tempat (farm-gate).
  - "antar"  ≈ DAP: petani mengantar ke gudang pengepul; harga sudah termasuk ongkos antar petani.
Harga harapan petani per skema berfungsi sebagai reserve price (Myerson 1981): tawaran di bawahnya ditolak.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Double, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, false, text,
)

from ..database import Base


def _enum(e):
    return Enum(e, native_enum=False, values_callable=lambda x: [m.value for m in x])


class DeliveryScheme(str, enum.Enum):
    JEMPUT = "jemput"
    ANTAR = "antar"


class ListingStatus(str, enum.Enum):
    OPEN = "open"
    PARTIAL = "partially_awarded"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BidStatus(str, enum.Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"      # pengepul membatalkan pembelian yang sudah diterima petani (sebelum ditimbang)


class StockListing(Base):
    __tablename__ = "stock_listings"
    __table_args__ = (
        CheckConstraint("quantity_kg > 0 AND remaining_kg >= 0 AND remaining_kg <= quantity_kg", name="ck_listing_qty"),
        CheckConstraint("allow_jemput OR allow_antar", name="ck_listing_scheme"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("mills.id"), nullable=True)
    quantity_kg = Column(Double, nullable=False)
    commodity = Column(String(24), ForeignKey("biomass_parameters.code"), nullable=False, default="sekam_padi",
                       server_default="sekam_padi")   # 018
    remaining_kg = Column(Double, nullable=False)        # berkurang atomik setiap penerimaan sebagian
    moisture_pct = Column(Double, nullable=True)
    grade_estimate = Column(String(5), nullable=True)
    allow_jemput = Column(Boolean, nullable=False, default=True)
    allow_antar = Column(Boolean, nullable=False, default=False)
    ask_price_jemput = Column(Double, nullable=True)     # Rp/kg, reserve skema jemput
    ask_price_antar = Column(Double, nullable=True)      # Rp/kg, reserve skema antar
    lat = Column(Double, nullable=True)
    lon = Column(Double, nullable=True)
    evidence_photo_url = Column(Text, nullable=True)
    status = Column(_enum(ListingStatus), nullable=False, default=ListingStatus.OPEN, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    
    # 022 Omni Extensions
    transaction_mode = Column(String(16), nullable=False, default="DIRECT", server_default="DIRECT")  # 'DIRECT' | 'BIDDING'
    auction_status = Column(String(16), nullable=False, default="OPEN")      # 'OPEN' | 'ACCEPTED' | 'EXPIRED' | 'CANCELLED'
    auction_expiry = Column(DateTime(timezone=True), nullable=True)
    floor_price = Column(Double, nullable=True)
    logistics_mode = Column(String(16), nullable=False, default="PICKUP")    # 'PICKUP' | 'DELIVER_SELF'
    payment_status = Column(String(16), nullable=False, default="UNPAID")    # 'UNPAID' | 'DP' | 'SETTLED'
    farmer_claimed_qty = Column(Double, nullable=True)
    actual_weighed_qty = Column(Double, nullable=True)
    deviation_kg = Column(Double, nullable=True)
    deviation_pct = Column(Double, nullable=True)
    qc_status = Column(String(16), default="PENDING")                        # 'PENDING' | 'PASS' | 'REJECT'
    qc_rejection_reason = Column(Text, nullable=True)
    # Stock Locking (mencegah double-booking / ghost inventory antar pabrik)
    is_locked = Column(Boolean, nullable=False, default=False, server_default=false())
    locked_by_mill_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    origin_qr_code = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        CheckConstraint("price_per_kg > 0 AND quantity_kg > 0", name="ck_bid_pos"),
        CheckConstraint("accepted_kg >= 0", name="ck_bid_accepted"),
        # Satu tawaran aktif per pengepul per skema per listing (tawaran baru menggantikan yang lama)
        Index("uq_bid_active", "listing_id", "collector_id", "scheme", unique=True,
              sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey("stock_listings.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Pemilik listing (denormalisasi): kebijakan RLS bids untuk petani cukup membaca kolom ini, tanpa subquery
    # ke stock_listings — memutus siklus kebijakan stock_listings ↔ bids (PostgreSQL: infinite recursion).
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    scheme = Column(_enum(DeliveryScheme), nullable=False)
    price_per_kg = Column(Double, nullable=False)
    quantity_kg = Column(Double, nullable=False)
    accepted_kg = Column(Double, nullable=False, default=0)
    pickup_date = Column(String(10), nullable=True)      # YYYY-MM-DD rencana jemput/terima
    est_logistic_cost_per_kg = Column(Double, nullable=True)
    note = Column(Text, nullable=True)
    status = Column(_enum(BidStatus), nullable=False, default=BidStatus.ACTIVE, index=True)
    
    # 022 Omni Extensions
    logistics_mode = Column(String(16), default="PICKUP")
    payment_term = Column(String(16), default="COD")
    pickup_schedule_proposed = Column(DateTime(timezone=True), nullable=True)
    farmer_schedule_status = Column(String(16), default="PENDING")   # 'PENDING' | 'APPROVED' | 'RESCHEDULE_REQUESTED'
    farmer_schedule_note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime(timezone=True), nullable=True)


class TrxSequence(Base):
    """Penghitung resi per (pengirim, penerima, bulan). Dinaikkan atomik via UPSERT ... RETURNING."""
    __tablename__ = "trx_sequences"
    __table_args__ = (UniqueConstraint("sender_code", "receiver_code", "yymm", name="uq_trx_seq"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_code = Column(String(12), nullable=False)
    receiver_code = Column(String(12), nullable=False)
    yymm = Column(String(4), nullable=False)
    last_seq = Column(Integer, nullable=False, default=0)


class CollectorPaymentReputation(Base):
    """Scorecard reputasi pembayaran pengepul (tempo bayar, piutang tertunda, rating)."""
    __tablename__ = "collector_payment_reputations"

    collector_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_transactions = Column(Integer, nullable=False, default=0)
    on_time_dp_count = Column(Integer, nullable=False, default=0)
    on_time_settlement_count = Column(Integer, nullable=False, default=0)
    avg_dp_delay_hours = Column(Double, nullable=False, default=0.0)
    avg_settlement_delay_days = Column(Double, nullable=False, default=0.0)
    punctuality_score = Column(Double, nullable=False, default=100.0)
    outstanding_debt_rp = Column(Double, nullable=False, default=0.0)
    settled_amount_rp = Column(Double, nullable=False, default=0.0)
    rating_tier = Column(String(16), nullable=False, default="EXCELLENT") # EXCELLENT | GOOD | FAIR | POOR
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CollectorRating(Base):
    """Evaluasi performa pengepul oleh petani (rating ketepatan waktu & pembayaran)."""
    __tablename__ = "collector_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)
    punctuality_rating = Column(Integer, nullable=False, default=5)          # 1 - 5
    payment_rating = Column(Integer, nullable=False, default=5)              # 1 - 5
    overall_rating = Column(Double, nullable=False, default=5.0)
    review_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


