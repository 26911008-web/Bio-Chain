"""Engine ⑥ — Incentive Engine.

Sistem gamifikasi XP untuk mendorong petani menjual sekam berkualitas
dan tepat waktu. XP kumulatif → Tier → Bonus harga.
"""

from pydantic import BaseModel, Field

# M2 fix: Single canonical IncentiveTier from models.user
from ..models.user import IncentiveTier
from ..params import P


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
    grade_xp = {"A": P("insentif.xp_grade_A"), "B": P("insentif.xp_grade_B"), "C": P("insentif.xp_grade_C"),
                "TOLAK": 0.0}
    on_time, lean = P("insentif.bonus_on_time"), P("insentif.bonus_lean_season")
    base = int(event.quantity_ton * grade_xp.get(event.grade, 0) * 10)

    bonuses = []
    multiplier = 1.0

    if event.on_time:
        multiplier += on_time
        bonuses.append(f"⏰ Bonus tepat waktu (+{on_time:.0%} XP)")

    if event.is_peak_season:
        multiplier += lean
        bonuses.append(f"📦 Bonus pasokan musim paceklik (+{lean:.0%} XP)")

    if event.grade == "A":
        bonuses.append("⭐ Kualitas Grade A — XP maksimum!")

    xp_earned = max(0, int(base * multiplier))
    new_total = event.farmer_xp + xp_earned

    tier = tier_for(new_total)

    return IncentiveResult(
        xp_earned=xp_earned,
        new_total_xp=new_total,
        tier=tier,
        price_multiplier=tier_price_bonus(tier),
        bonus_notes=bonuses,
    )


def tier_thresholds() -> list[tuple[IncentiveTier, int]]:
    """Ambang XP aktif (menu Parameter → Insentif), urut naik."""
    return [(IncentiveTier.PEMULA, 0), (IncentiveTier.PEMASOK_AKTIF, int(P("insentif.tier_aktif_xp"))),
            (IncentiveTier.MITRA_EMAS, int(P("insentif.tier_emas_xp"))),
            (IncentiveTier.MITRA_PLATINUM, int(P("insentif.tier_platinum_xp")))]


def tier_for(xp: int) -> IncentiveTier:
    return [t for t, lo in tier_thresholds() if xp >= lo][-1]


def tier_price_bonus(tier: IncentiveTier) -> float:
    return {IncentiveTier.PEMULA: 1.0, IncentiveTier.PEMASOK_AKTIF: P("insentif.bonus_price_aktif"),
            IncentiveTier.MITRA_EMAS: P("insentif.bonus_price_emas"),
            IncentiveTier.MITRA_PLATINUM: P("insentif.bonus_price_platinum")}[tier]


def next_tier_xp(xp: int) -> int | None:
    return next((lo for _, lo in tier_thresholds() if xp < lo), None)
