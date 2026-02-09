from __future__ import annotations

from game.config import MARKET_BUY_PRICES, SELLBACK_FACTOR


def market_buy_price(key: str) -> int:
    """Market buy price for a product or rarity key (fixed; player cannot change)."""
    return max(1, int(MARKET_BUY_PRICES.get(str(key), 1)))


def sellable_copies(*, owned: int, in_deck: int) -> int:
    """Return how many copies are sellable (cannot sell committed deck copies)."""
    return max(0, int(owned) - int(in_deck))


def sellback_unit_price(market_price: int, *, factor: float = SELLBACK_FACTOR) -> int:
    """Unit payout for selling back to market."""
    p = max(1, int(market_price))
    f = float(factor)
    if f < 0.0:
        f = 0.0
    if f > 1.0:
        f = 1.0
    return max(1, int(round(p * f)))


def sellback_total(market_price: int, qty: int, *, factor: float = SELLBACK_FACTOR) -> int:
    q = max(0, int(qty))
    if q <= 0:
        return 0
    return sellback_unit_price(market_price, factor=factor) * q

