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
    REPORTED = "reported"
    VERIFIED = "verified"
    COLLECTED = "collected"
    DELIVERED = "delivered"
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

    quantity_kg = Column(Double, nullable=False)
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
