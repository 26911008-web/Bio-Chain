"""Model SQLAlchemy ORM untuk Notifikasi Transaksi Biomassa Lintas Persona."""

from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship

from ..database import Base

_now = lambda: datetime.now(timezone.utc)


class NotificationStatusGroup(str, enum.Enum):
    PENDING_ACTION = "PENDING_ACTION"          # 🟡 Menunggu Verifikasi & Tindakan
    IN_PROGRESS = "IN_PROGRESS"                # 🔵 Dalam Proses & Logistik
    COMPLETED = "COMPLETED"                    # 🟢 Selesai & Lunas
    ALERT_DISCREPANCY = "ALERT_DISCREPANCY"    # 🔴 Perhatian & Refraksi / Ditolak


class Notification(Base):
    """Pencatatan notifikasi peristiwa transaksi biomassa lintas persona (Petani, Pengepul, Driver, Pabrik, Auditor, Admin)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_role = Column(String(20), nullable=True, index=True)  # petani | pengepul | driver | pabrik | auditor | admin | all
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True, index=True)
    transaction_code = Column(String(80), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status_group = Column(String(30), nullable=False, default="PENDING_ACTION", index=True)
    actor_role = Column(String(20), nullable=True)
    actor_name = Column(String(100), nullable=True)
    action_type = Column(String(50), nullable=True)     # "trace" | "qr" | "pay" | "verify" | "view"
    action_payload = Column(String(200), nullable=True) # code or id for action
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    harvest = relationship("Harvest", foreign_keys=[harvest_id])
