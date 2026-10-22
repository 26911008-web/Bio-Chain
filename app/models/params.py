"""SQLAlchemy ORM — nilai parameter asumsi aktif + riwayat perubahan (audit)."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from ..database import Base


class SystemParameter(Base):
    __tablename__ = "system_parameters"

    key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ParameterChange(Base):
    """Append-only: siapa mengubah asumsi apa, dari berapa ke berapa, dan mengapa."""
    __tablename__ = "parameter_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(80), nullable=False, index=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)        # null = dikembalikan ke default
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_by_role = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
