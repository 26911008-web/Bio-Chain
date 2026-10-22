"""SQLAlchemy ORM models — Route dan RouteStop untuk logistik."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Double, Enum, ForeignKey, Integer, String,
)
from sqlalchemy.orm import relationship

from ..database import Base


class RouteStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    vehicle_plate = Column(String(20), nullable=True)
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

    planned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    driver = relationship("User", back_populates="routes_as_driver")
    stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan",
                         order_by="RouteStop.stop_order")


class RouteStop(Base):
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("mills.id"), nullable=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)

    stop_order = Column(Integer, nullable=False)
    planned_m3 = Column(Double, nullable=True)
    planned_ton = Column(Double, nullable=True)
    actual_ton = Column(Double, nullable=True)

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
