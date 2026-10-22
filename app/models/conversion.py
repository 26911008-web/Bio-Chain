"""SQLAlchemy ORM models — Conversion, CarbonCredit, IncentiveEvent."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Double, ForeignKey, Integer, String, Text, JSON,
)

from ..database import Base


class Conversion(Base):
    """Hasil konversi pirolisis — satu record per batch produksi."""
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String(50), unique=True, nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Input
    feedstock_ton = Column(Double, nullable=False)
    feedstock_composition = Column(JSON, nullable=True)
    blend_moisture = Column(Double, nullable=True)
    blend_ash = Column(Double, nullable=True)
    blend_fc = Column(Double, nullable=True)

    # Process
    pyrolysis_temp_c = Column(Double, nullable=True)
    residence_time_min = Column(Double, nullable=True)

    # Output
    biochar_ton = Column(Double, nullable=True)
    bio_oil_ton = Column(Double, nullable=True)
    syngas_m3 = Column(Double, nullable=True)
    actual_yield_pct = Column(Double, nullable=True)

    # Quality biochar
    biochar_ash = Column(Double, nullable=True)
    biochar_fc = Column(Double, nullable=True)
    biochar_sio2_pct = Column(Double, nullable=True)
    biochar_hhv_mj = Column(Double, nullable=True)

    # Economics
    production_cost = Column(Double, nullable=True)
    selling_price = Column(Double, nullable=True)
    margin = Column(Double, nullable=True)

    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CarbonCredit(Base):
    """Tracking emisi CO₂ yang dihindari — untuk ESG reporting."""
    __tablename__ = "carbon_credits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)

    biomass_ton = Column(Double, nullable=False)
    transport_km = Column(Double, nullable=True)

    emission_avoided_tco2 = Column(Double, nullable=True)
    transport_emission_tco2 = Column(Double, nullable=True)
    net_reduction_tco2 = Column(Double, nullable=True)

    methodology = Column(String(100), default="IPCC 2006 Tier 2")
    srn_ppi_eligible = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)

    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IncentiveEvent(Base):
    """Log setiap perubahan XP petani — audit trail gamifikasi."""
    __tablename__ = "incentive_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)

    xp_earned = Column(Integer, nullable=False)
    xp_before = Column(Integer, nullable=False)
    xp_after = Column(Integer, nullable=False)
    tier_before = Column(String(30), nullable=True)
    tier_after = Column(String(30), nullable=True)

    reason = Column(Text, nullable=True)
    bonus_notes = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
