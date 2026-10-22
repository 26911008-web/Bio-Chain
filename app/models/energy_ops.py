"""Log operasi energi harian/shift untuk Prototipe 3 (migrasi 019) — sumber data SEC/IKE ternormalisasi."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint, func

from ..database import Base


class EnergyOperationLog(Base):
    __tablename__ = "energy_operation_logs"
    __table_args__ = (
        UniqueConstraint("facility", "log_date", "shift", name="uq_energy_ops_slot"),
        CheckConstraint("kwh_total >= 0 AND diesel_l >= 0 AND biomass_fuel_kg >= 0", name="ck_eops_nonneg"),
        CheckConstraint("operating_hours > 0 AND operating_hours <= 24", name="ck_eops_hours"),
        CheckConstraint("product_ton > 0", name="ck_eops_ton"),
        CheckConstraint("feed_moisture_pct IS NULL OR (feed_moisture_pct >= 0 AND feed_moisture_pct < 95)", name="ck_eops_mc"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    facility = Column(String(100), nullable=False, index=True)
    log_date = Column(String(10), nullable=False)                 # YYYY-MM-DD
    shift = Column(String(8), nullable=False, default="H", server_default="H")   # H (harian) | S1 | S2 | S3
    kwh_total = Column(Double, nullable=False)
    kwh_dryer = Column(Double)
    kwh_hammer_mill = Column(Double)
    diesel_l = Column(Double, nullable=False, default=0.0, server_default="0")
    biomass_fuel_kg = Column(Double, nullable=False, default=0.0, server_default="0")
    biomass_fuel_code = Column(String(24), ForeignKey("biomass_parameters.code"))
    operating_hours = Column(Double, nullable=False)
    product_ton = Column(Double, nullable=False)
    feed_moisture_pct = Column(Double)
    rated_capacity_t_h = Column(Double)
    note = Column(Text)
    client_event_id = Column(String(64), unique=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                        server_default=func.now())
