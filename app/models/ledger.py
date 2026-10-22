"""SQLAlchemy ORM models — Chain-of-custody & ledger abu bottom ash / sirkular (ekonomi sirkular).

Kedua tabel bersifat append-only: koreksi dicatat sebagai entri baru, bukan UPDATE/DELETE,
sehingga auditor bisa merekonstruksi setiap kilogram dari petani sampai kembali ke petani.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint,
)

from ..database import Base


class CustodyStage(str, enum.Enum):
    FARMER_REPORT = "farmer_report"
    COLLECTOR_WEIGH = "collector_weigh"
    COLLECTOR_REJECT = "collector_reject"
    DRIVER_PICKUP = "driver_pickup"
    FACTORY_RECEIVE = "factory_receive"
    FACTORY_REJECT = "factory_reject"
    CONVERSION = "conversion"


class CustodyEvent(Base):
    """Satu baris per serah-terima / perubahan status harvest."""
    __tablename__ = "custody_events"
    __table_args__ = (CheckConstraint("weight_kg IS NULL OR weight_kg >= 0", name="ck_custody_weight_nonneg"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=False, index=True)
    stage = Column(String(30), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    weight_kg = Column(Double, nullable=True)

    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(20), nullable=False)

    # Offline-first: kunci idempotensi dari perangkat + waktu kejadian di perangkat
    client_event_id = Column(String(64), unique=True, nullable=True)
    client_recorded_at = Column(DateTime(timezone=True), nullable=True)
    lat = Column(Double, nullable=True)
    lon = Column(Double, nullable=True)
    note = Column(Text, nullable=True)

    # Serah-terima antar node: resi unik TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[SEQ] + bukti foto (opsional)
    verification_code = Column(String(40), unique=True, nullable=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    evidence_photo_url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversionInput(Base):
    """Harvest mana masuk ke batch pirolisis mana, dan porsinya."""
    __tablename__ = "conversion_inputs"
    __table_args__ = (CheckConstraint("input_kg > 0", name="ck_conv_input_pos"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id"), nullable=False, index=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=False, unique=True)  # dikonsumsi sekali
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    input_kg = Column(Double, nullable=False)
    share = Column(Double, nullable=False)       # input_kg / Σ input_kg batch
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BiocharLedgerEntry(Base):
    """Dompet abu bottom ash petani: saldo = Σ amount_kg. Positif = alokasi, negatif = penebusan."""
    __tablename__ = "biochar_ledger"
    __table_args__ = (
        UniqueConstraint("conversion_id", "harvest_id", "entry_type", name="uq_ledger_alloc_once"),
        UniqueConstraint("batch_id", "harvest_id", "entry_type", name="uq_ledger_batch_alloc_once"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=True, index=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)
    entry_type = Column(String(20), nullable=False)   # allocation | redemption | adjustment
    amount_kg = Column(Double, nullable=False)
    note = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
