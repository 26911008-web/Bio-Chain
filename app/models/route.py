"""SQLAlchemy ORM models — Route dan RouteStop untuk logistik."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Double, Enum, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.orm import relationship

from ..database import Base


class RouteStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StopStatus(str, enum.Enum):
    PENDING = "pending"          # menunggu dijemput
    PICKED_UP = "picked_up"      # QR dipindai, barang di truk
    FAILED = "failed"            # supir tiba, barang tidak dapat diambil (stok hilang, basah, akses jalan)
    CANCELLED = "cancelled"      # dibatalkan sebelum dijemput (pengepul batal jual / pabrik batalkan rute)


# Stop yang masih "memegang" harvest: hanya satu per harvest. Stop gagal/batal melepas harvest
# sehingga bisa dijadwalkan ulang ke rute lain.
LIVE_STOP_STATUSES = ("pending", "picked_up")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    vehicle_plate = Column(String(20), nullable=True)
    logistics_carrier = Column(String(30), default="FACTORY_FLEET", index=True)
    status = Column(Enum(RouteStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]), default=RouteStatus.PLANNED, index=True)

    # Vehicle params
    vehicle_m3 = Column(Double, default=30)
    bulk_density = Column(Double, default=110)

    # Calculated results
    total_km = Column(Double, nullable=True)
    total_cost = Column(Double, nullable=True)
    total_ton = Column(Double, nullable=True)
    total_m3 = Column(Double, nullable=True)
    utilization_pct = Column(Double, nullable=True)
    co2_kg = Column(Double, nullable=True)
    estimated_hours = Column(Double, nullable=True)

    # Savings
    baseline_km = Column(Double, nullable=True)
    saving_pct = Column(Double, nullable=True)

    # Realisasi (GPS) & emisi ISO 14083 — diisi saat complete-route dari jejak GPS yang tersinkron
    optimizer = Column(String(40), nullable=True)
    actual_km = Column(Double, nullable=True)
    fuel_l = Column(Double, nullable=True)
    co2e_wtw_kg = Column(Double, nullable=True)
    co2e_per_ton_kg = Column(Double, nullable=True)
    emission_detail = Column(JSON, nullable=True)

    # Pembatalan
    cancel_reason = Column(Text, nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    planned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    driver = relationship("User", back_populates="routes_as_driver", foreign_keys=[driver_id])
    stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan",
                         order_by="RouteStop.stop_order")


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (
        # Dua dispatch serentak untuk harvest yang sama → yang kedua IntegrityError → 409.
        # Hanya stop yang masih hidup: stop gagal/batal tidak menghalangi penjadwalan ulang.
        Index("uq_route_stops_harvest_live", "harvest_id", unique=True,
              sqlite_where=text("harvest_id IS NOT NULL AND stop_status IN ('pending', 'picked_up')"),
              postgresql_where=text("harvest_id IS NOT NULL AND stop_status IN ('pending', 'picked_up')")),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("mills.id"), nullable=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)

    stop_order = Column(Integer, nullable=False)
    planned_m3 = Column(Double, nullable=True)
    planned_ton = Column(Double, nullable=True)
    actual_ton = Column(Double, nullable=True)

    stop_status = Column(String(12), nullable=False, default=StopStatus.PENDING.value, server_default="pending")
    fail_reason = Column(String(30), nullable=True)
    fail_note = Column(Text, nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    # Proof of Pickup
    pickup_photo = Column(String(500), nullable=True)
    qr_scanned = Column(Boolean, default=False)
    pickup_at = Column(DateTime(timezone=True), nullable=True)

    lat_arrived = Column(Double, nullable=True)
    lon_arrived = Column(Double, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    route = relationship("Route", back_populates="stops")
    mill = relationship("Mill", back_populates="route_stops")


class RouteTrackPoint(Base):
    """Titik GPS jejak truk. Direkam perangkat walau tanpa sinyal, dikirim belakangan (store & forward).
    `client_point_id` unik → unggah ulang batch yang sama tidak menggandakan titik."""
    __tablename__ = "route_track_points"
    __table_args__ = (Index("ix_track_route_time", "route_id", "recorded_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_point_id = Column(String(64), nullable=False, unique=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    lat = Column(Double, nullable=False)
    lon = Column(Double, nullable=False)
    accuracy_m = Column(Double, nullable=True)
    speed_mps = Column(Double, nullable=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
