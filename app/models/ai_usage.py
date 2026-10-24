"""Pemakaian Asisten AI per akun — dasar kuota harian (app/services/ai_quota.py)."""

from sqlalchemy import Column, Date, ForeignKey, Integer

from ..database import Base


class UserAIUsage(Base):
    """Satu baris per pengguna: jumlah pertanyaan AI pada `last_reset_date` (tanggal lokal kuota)."""
    __tablename__ = "user_ai_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    request_count = Column(Integer, nullable=False, default=0)
    last_reset_date = Column(Date, nullable=False)
