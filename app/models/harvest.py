"""SQLAlchemy ORM models — Harvest, Mill, dan tabel terkait supply chain."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Double, Enum, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..database import Base


class HarvestStatus(str, enum.Enum):
    """State machine: reported → verified → collected → delivered → converted;
    reported/collected → rejected. Transisi hanya lewat `app.services.custody.transition`."""
    REPORTED = "reported"
    VERIFIED = "verified"
    COLLECTED = "collected"
    DELIVERED = "delivered"
    CONVERTED = "converted"
    REJECTED = "rejected"


class QualityGrade(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    TOLAK = "TOLAK"


class Mill(Base):
    __tablename__ = "mills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    kecamatan = Column(String(100), nullable=False, index=True)
    kabupaten = Column(String(100), default="Sleman")
    lat = Column(Double, nullable=False)
    lon = Column(Double, nullable=False)
    capacity_ton = Column(Double, default=5.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    harvests = relationship("Harvest", back_populates="mill")
    route_stops = relationship("RouteStop", back_populates="mill")


class Harvest(Base):
    __tablename__ = "harvests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True)

    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("mills.id"), nullable=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    quantity_kg = Column(Double, nullable=False)   # estimasi petani (bukan dasar pembayaran)
    status = Column(Enum(HarvestStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]), default=HarvestStatus.REPORTED, index=True)

    # Quality assessment
    moisture = Column(Double, nullable=True)
    ash = Column(Double, nullable=True)
    volatile_matter = Column(Double, nullable=True)
    fixed_carbon = Column(Double, nullable=True)
    contamination = Column(Double, default=0)
    grade = Column(Enum(QualityGrade, native_enum=False, values_callable=lambda x: [e.value for e in x]), nullable=True)
    quality_score = Column(Double, nullable=True)

    # Proof
    photo_url = Column(Text, nullable=True)
    qr_code = Column(String(100), unique=True, nullable=True)

    # Pricing
    base_price_per_kg = Column(Double, nullable=True)
    incentive_multiplier = Column(Double, default=1.0)
    total_price = Column(Double, nullable=True)

    # Mass balance: berat di tiap titik serah-terima. Timbangan pabrik = angka otoritatif.
    verified_kg = Column(Double, nullable=True)     # timbangan pengepul → dasar harga ke petani
    picked_up_kg = Column(Double, nullable=True)    # catatan supir (informatif, bukan otoritatif)
    received_kg = Column(Double, nullable=True)     # timbangan pabrik
    shrinkage_kg = Column(Double, nullable=True)    # verified_kg − received_kg
    shrinkage_pct = Column(Double, nullable=True)
    discrepancy_flag = Column(Boolean, default=False, nullable=False, index=True)
    discrepancy_note = Column(Text, nullable=True)
    rejected_reason = Column(Text, nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    received_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id"), nullable=True, index=True)
    version = Column(Integer, default=1, nullable=False)   # dinaikkan setiap transisi (compare-and-swap)

    # Asal pasar B2B: harga & skema hasil kesepakatan lelang (menggantikan harga dasar saat verifikasi)
    listing_id = Column(Integer, ForeignKey("stock_listings.id"), nullable=True, index=True)
    bid_id = Column(Integer, ForeignKey("bids.id"), nullable=True)
    agreed_price_per_kg = Column(Double, nullable=True)
    delivery_scheme = Column(String(10), nullable=True)
    # Rantai ke pabrik: harvest dilampirkan pengepul pada Delivery Request → QC → batch → dompet biochar
    delivery_request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=True, index=True)

    reported_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    farmer = relationship("User", back_populates="harvests_as_farmer",
                          foreign_keys=[farmer_id])
    collector = relationship("User", back_populates="harvests_as_collector",
                             foreign_keys=[collector_id])
    mill = relationship("Mill", back_populates="harvests")
