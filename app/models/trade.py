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
    UniqueConstraint, text,
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
