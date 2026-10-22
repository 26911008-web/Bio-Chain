"""Engine ⑥ — Incentive Engine.

Sistem gamifikasi XP untuk mendorong petani menjual sekam berkualitas
dan tepat waktu. XP kumulatif → Tier → Bonus harga.
"""

from pydantic import BaseModel, Field

# M2 fix: Single canonical IncentiveTier from models.user
from ..models.user import IncentiveTier


TIER_THRESHOLDS = {
    IncentiveTier.PEMULA: (0, 99),
    IncentiveTier.PEMASOK_AKTIF: (100, 499),
    IncentiveTier.MITRA_EMAS: (500, 1499),
    IncentiveTier.MITRA_PLATINUM: (1500, float("inf")),
}

TIER_PRICE_BONUS = {
    IncentiveTier.PEMULA: 1.00,
    IncentiveTier.PEMASOK_AKTIF: 1.05,
    IncentiveTier.MITRA_EMAS: 1.12,
    IncentiveTier.MITRA_PLATINUM: 1.20,
}


class DeliveryEvent(BaseModel):
    farmer_xp: int = Field(0, ge=0, description="XP kumulatif petani saat ini")
    quantity_ton: float = Field(..., gt=0)
    grade: str = Field(..., pattern="^(A|B|C|TOLAK)$")
    on_time: bool = Field(True)
    is_peak_season: bool = Field(False)


class IncentiveResult(BaseModel):
    xp_earned: int
    new_total_xp: int
    tier: IncentiveTier
    price_multiplier: float
    bonus_notes: list[str]


def calculate_incentive(event: DeliveryEvent) -> IncentiveResult:
    """Hitung XP dan insentif dari satu event pengiriman.

    base_xp = quantity × grade_multiplier × 10
    bonus_on_time = +20%
    bonus_paceklik = +50%
    """
    grade_xp = {"A": 3.0, "B": 2.0, "C": 1.0, "TOLAK": 0.0}
    base = int(event.quantity_ton * grade_xp.get(event.grade, 0) * 10)

    bonuses = []
    multiplier = 1.0

    if event.on_time:
        multiplier += 0.20
        bonuses.append("⏰ Bonus tepat waktu (+20% XP)")

    if event.is_peak_season:
        multiplier += 0.50
        bonuses.append("📦 Bonus pasokan musim paceklik (+50% XP)")

    if event.grade == "A":
        bonuses.append("⭐ Kualitas Grade A — XP maksimum!")

    xp_earned = max(0, int(base * multiplier))
    new_total = event.farmer_xp + xp_earned

    tier = IncentiveTier.PEMULA
    for t, (lo, hi) in TIER_THRESHOLDS.items():
        if lo <= new_total <= hi:
            tier = t
            break
    # Handle > max threshold
    if new_total >= 1500:
        tier = IncentiveTier.MITRA_PLATINUM

    return IncentiveResult(
        xp_earned=xp_earned,
        new_total_xp=new_total,
        tier=tier,
        price_multiplier=TIER_PRICE_BONUS[tier],
        bonus_notes=bonuses,
    )
