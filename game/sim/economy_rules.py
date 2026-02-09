from __future__ import annotations

from dataclasses import dataclass

from game.config import Prices
from game.sim.skill_tree import Modifiers
from game.sim.pricing import PricingSettings, retail_base_price


def base_price_for_product(prices: Prices, product: str, pricing: PricingSettings) -> int | None:
    return retail_base_price(prices, pricing, product)


def apply_sell_price_pct(base_price: int, sell_price_pct: float) -> int:
    """Apply a sell price percentage modifier to an integer price."""
    p = int(round(float(base_price) * (1.0 + float(sell_price_pct))))
    return max(1, p)


def effective_sale_price(prices: Prices, product: str, mods: Modifiers, pricing: PricingSettings) -> int | None:
    base = base_price_for_product(prices, product, pricing)
    if base is None:
        return None
    return apply_sell_price_pct(base, mods.sell_price_pct)


FIXTURE_BASE_COST: dict[str, int] = {
    "shelf": 250,
    "counter": 800,
    "poster": 120,
}


def fixture_cost(kind: str, mods: Modifiers) -> int | None:
    base = FIXTURE_BASE_COST.get(kind)
    if base is None:
        return None
    pct = max(0.0, min(0.95, float(mods.fixture_discount_pct)))
    return max(1, int(round(base * (1.0 - pct))))


def xp_from_sale(revenue: int, mods: Modifiers) -> int:
    """XP from a single sale.

    Uses revenue (not profit) so it's always non-negative.
    """
    base = max(0, int(revenue)) * 2
    k = 1.0 + max(0.0, float(mods.sales_xp_pct))
    return max(0, int(round(base * k)))


def xp_from_battle_win(mods: Modifiers) -> int:
    """XP from winning a battle."""
    base = 120
    k = 1.0 + max(0.0, float(mods.battle_xp_pct))
    return max(0, int(round(base * k)))


def xp_from_sell(revenue: int, mods: Modifiers) -> int:
    """XP from selling items/cards back to the market."""
    base = max(0, int(revenue))
    k = 1.0 + max(0.0, float(mods.sales_xp_pct))
    return max(0, int(round(base * k)))

