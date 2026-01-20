from __future__ import annotations

import random

from game.config import Prices


def daily_customer_count(day: int, rng: random.Random) -> int:
    base = 6 + day
    return max(6, int(rng.randint(base - 2, base + 3)))


def choose_purchase(prices: Prices, available: list[str], rng: random.Random) -> str:
    """Choose a product type from available shelf stock."""
    if not available:
        return "none"
    weights: list[float] = []
    for product in available:
        if product == "booster":
            weight = max(0.2, 1.2 - prices.booster / 10.0)
        elif product == "deck":
            weight = max(0.2, 1.0 - prices.deck / 20.0)
        elif product.startswith("single_"):
            rarity = product.replace("single_", "")
            price = getattr(prices, f"single_{rarity}")
            weight = max(0.2, 1.4 - price / 4.0)
        else:
            weight = 0.2
        weights.append(weight)
    choice = rng.choices(available, weights)[0]
    return choice
