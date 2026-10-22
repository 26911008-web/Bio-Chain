"""SQLAlchemy ORM models untuk Operasional Industri Pabrik:
Gate Receptions, Loading Ramps, Factory Invoices, Production Blends, & By-Products.
"""

from datetime import datetime, timezone
import enum
from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Double, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..database import Base


class CarrierType(str, enum.Enum):
    FACTORY_FLEET = "FACTORY_FLEET"
    COLLECTOR_SELF = "COLLECTOR_SELF"


class QcDecision(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    REJECTED = "REJECTED"


class PaymentScheme(str, enum.Enum):
    CASH = "CASH"
    DP = "DP"
    TOP = "TOP"


class TargetProduct(str, enum.Enum):
    BIOPELLET = "BIOPELLET"
    BIOCHAR = "BIOCHAR"
    BIO_SILICA = "BIO_SILICA"
    BRIQUETTE = "BRIQUETTE"


class ByProductType(str, enum.Enum):
    WOOD_VINEGAR = "WOOD_VINEGAR"
    SILICA_ASH = "SILICA_ASH"
    BOTTOM_ASH = "BOTTOM_ASH"
    BIOCHAR_COARSE = "BIOCHAR_COARSE"


class LoadingRamp(Base):
    __tablename__ = "loading_ramps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ramp_code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    biomass_type = Column(String(50), nullable=False, index=True)
    max_capacity_kg = Column(Double, default=50000.0, nullable=False)
    current_stock_kg = Column(Double, default=0.0, nullable=False)
    aggregate_mc = Column(Double, default=12.0, nullable=False)
    aggregate_ash = Column(Double, default=15.0, nullable=False)
    aggregate_lhv_kcal = Column(Double, default=3500.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class GateReception(Base):
    __tablename__ = "gate_receptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_number = Column(String(50), unique=True, nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    delivery_request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=True)
    vehicle_plate = Column(String(20), nullable=False)
    driver_name = Column(String(100), nullable=False)
    logistics_carrier = Column(String(30), default="FACTORY_FLEET", nullable=False)
    biomass_type = Column(String(50), nullable=False, index=True)

    # Weighbridge
    gross_weight = Column(Double, nullable=False)
    tare_weight = Column(Double, nullable=False)
    net_weight = Column(Double, nullable=False)

    # Field QC Parameters
    tested_mc_pct = Column(Double, nullable=False)
    tested_ash_pct = Column(Double, nullable=False)
    tested_lhv_kcal = Column(Double, default=3500.0, nullable=False)
    contamination_pct = Column(Double, default=0.0, nullable=False)

    # 3-State QC Decision
    qc_decision = Column(String(25), default="ACCEPTED", nullable=False, index=True)
    accepted_qty_kg = Column(Double, default=0.0, nullable=False)
    rejected_qty_kg = Column(Double, default=0.0, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    qc_photo_url = Column(String(500), nullable=True)

    allocated_ramp_id = Column(Integer, ForeignKey("loading_ramps.id"), nullable=True)
    return_case_id = Column(Integer, ForeignKey("return_cases.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FactoryInvoice(Base):
    __tablename__ = "factory_invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    gate_reception_id = Column(Integer, ForeignKey("gate_receptions.id"), nullable=True)
    biomass_type = Column(String(50), nullable=False, index=True)

    billable_qty_kg = Column(Double, nullable=False)
    unit_price_rp = Column(Double, nullable=False)
    total_amount_rp = Column(Double, nullable=False)

    payment_scheme = Column(String(15), default="CASH", nullable=False)
    dp_paid_amount = Column(Double, default=0.0, nullable=False)
    remaining_amount = Column(Double, default=0.0, nullable=False)

    due_date = Column(DateTime(timezone=True), nullable=False, index=True)
    is_overdue = Column(Boolean, default=False, nullable=False, index=True)
    status = Column(String(20), default="PENDING", nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    settled_at = Column(DateTime(timezone=True), nullable=True)


class ProductionBlend(Base):
    __tablename__ = "production_blends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blend_code = Column(String(50), unique=True, nullable=False, index=True)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_product = Column(String(30), nullable=False, index=True)

    ramp_allocations = Column(JSON, nullable=False)  # List of {ramp_id, qty_kg, biomass_type}
    total_input_kg = Column(Double, nullable=False)

    final_mc_pct = Column(Double, nullable=False)
    final_ash_pct = Column(Double, nullable=False)
    final_lhv_kcal = Column(Double, nullable=False)

    cost_per_kg = Column(Double, nullable=False)
    target_selling_price_per_kg = Column(Double, nullable=False)
    estimated_margin_rp = Column(Double, nullable=False)
    net_tco2e = Column(Double, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ByProductLedger(Base):
    __tablename__ = "by_product_ledgers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blend_id = Column(Integer, ForeignKey("production_blends.id"), nullable=True)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    by_product_type = Column(String(30), nullable=False, index=True)
    quantity_kg = Column(Double, default=0.0, nullable=False)
    circular_status = Column(String(30), default="STORED", nullable=False, index=True) # STORED | APPROVED_FOR_SOIL | DISPATCHED_TO_COLLECTOR | DELIVERED_TO_FARMER | REJECTED_HAZARDOUS
    # Uji Batas Logam Berat Keamanan Lahan (Pb < 50 ppm, Cd < 2 ppm, As < 10 ppm)
    pb_ppm = Column(Double, default=0.0, nullable=False)
    cd_ppm = Column(Double, default=0.0, nullable=False)
    as_ppm = Column(Double, default=0.0, nullable=False)
    is_safety_passed = Column(Boolean, default=False, nullable=False)
    lab_cert_no = Column(String(80), nullable=True)
    recipient_farmer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
