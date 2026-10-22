"""SQLAlchemy ORM — histori konsumsi energi bulanan per fasilitas (sumber analisis Engine ⑩)."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint

from ..database import Base


class EnergyMeterReading(Base):
    __tablename__ = "energy_readings"
    __table_args__ = (
        UniqueConstraint("facility", "period", name="uq_energy_facility_period"),
        CheckConstraint("kwh >= 0 AND production_ton >= 0", name="ck_energy_nonneg"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    facility = Column(String(100), nullable=False, index=True)
    period = Column(String(7), nullable=False)               # YYYY-MM
    kwh = Column(Double, nullable=False)                     # total fasilitas
    building_kwh = Column(Double, nullable=True)             # gedung/kantor (dasar IKE)
    production_ton = Column(Double, nullable=False, default=0)   # sekam diproses
    peak_kw = Column(Double, nullable=True)
    operating_hours = Column(Double, nullable=True)
    cost_rp = Column(Double, nullable=True)
    floor_area_m2 = Column(Double, nullable=False)
    building_type = Column(String(10), nullable=False, default="ac")
    source = Column(String(20), nullable=False, default="meter")   # meter | manual | demo
    note = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
