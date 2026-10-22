"""SQLAlchemy ORM models — User table.

Mendukung 5 role: petani, pengepul, driver, pabrik, admin.
Login via nomor telepon (cocok untuk petani literasi rendah).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Double, Enum, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..database import Base


class UserRole(str, enum.Enum):
    PETANI = "petani"
    PENGEPUL = "pengepul"
    DRIVER = "driver"
    PABRIK = "pabrik"
    ADMIN = "admin"


class IncentiveTier(str, enum.Enum):
    PEMULA = "pemula"
    PEMASOK_AKTIF = "pemasok_aktif"
    MITRA_EMAS = "mitra_emas"
    MITRA_PLATINUM = "mitra_platinum"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=True, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole, native_enum=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    # Geolokasi
    lat = Column(Double, nullable=True)
    lon = Column(Double, nullable=True)
    kecamatan = Column(String(100), nullable=True, index=True)
    kabupaten = Column(String(100), nullable=True)

    # Incentive (petani)
    xp_total = Column(Integer, default=0)
    incentive_tier = Column(Enum(IncentiveTier), default=IncentiveTier.PEMULA)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    harvests_as_farmer = relationship("Harvest", back_populates="farmer",
                                      foreign_keys="Harvest.farmer_id")
    harvests_as_collector = relationship("Harvest", back_populates="collector",
                                         foreign_keys="Harvest.collector_id")
    routes_as_driver = relationship("Route", back_populates="driver")

    def __repr__(self):
        return f"<User {self.id} {self.full_name} ({self.role.value})>"
