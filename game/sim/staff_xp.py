from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from game.config import (
    STAFF_XP_SINGLE_RARITY_MULT,
    XP_PER_PACK_OPENED,
    XP_PER_RESTOCK_ITEM,
    XP_PER_SALE_DOLLAR,
)

StaffXpEventType = Literal["sale", "restock", "pack_open"]


@dataclass(frozen=True)
class StaffXpAwardResult:
    gained_xp: int
    prev_xp: int
    new_xp: int
    prev_level: int
    new_level: int

    @property
    def leveled_up(self) -> bool:
        return self.new_level > self.prev_level


def staff_level_from_xp(total_xp: int) -> int:
    """Derive staff level from total XP (simple, fast)."""
    return max(1, 1 + max(0, int(total_xp)) // 100)


def _rarity_from_product(product: str | None) -> str | None:
    if not product:
        return None
    if product.startswith("single_"):
        return product.replace("single_", "")
    return None


def _rarity_mult(product: str | None) -> float:
    rarity = _rarity_from_product(product)
    if not rarity:
        return 1.0
    return float(STAFF_XP_SINGLE_RARITY_MULT.get(rarity, 1.0))


def compute_staff_xp(event_type: StaffXpEventType, amount: int, *, product: str | None = None) -> int:
    """
    Compute staff XP gained for an event.

    - sale: amount = sale dollars
    - restock: amount = items actually moved onto shelf
    - pack_open: amount = packs opened
    """
    amt = max(0, int(amount))
    if amt <= 0:
        return 0
    mult = _rarity_mult(product)
    if event_type == "sale":
        xp = int(round(float(amt) * float(XP_PER_SALE_DOLLAR) * mult))
        return max(1, xp)
    if event_type == "restock":
        xp = int(round(float(amt) * float(XP_PER_RESTOCK_ITEM) * mult))
        return max(1, xp)
    # pack_open
    return int(amt) * int(XP_PER_PACK_OPENED)


def award_staff_xp_total(
    current_total_xp: int, event_type: StaffXpEventType, amount: int, *, product: str | None = None
) -> StaffXpAwardResult:
    """Pure award function: returns the updated total XP and derived level info."""
    prev_xp = max(0, int(current_total_xp))
    gained = compute_staff_xp(event_type, amount, product=product)
    new_xp = prev_xp + int(gained)
    prev_level = staff_level_from_xp(prev_xp)
    new_level = staff_level_from_xp(new_xp)
    return StaffXpAwardResult(
        gained_xp=int(gained),
        prev_xp=prev_xp,
        new_xp=new_xp,
        prev_level=prev_level,
        new_level=new_level,
    )

