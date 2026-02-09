from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from game.config import MARKET_BUY_PRICES, WHOLESALE_UNIT_COSTS, Prices

PricingMode = Literal["absolute", "markup"]


@dataclass
class PricingSettings:
    """Player-configurable retail pricing controls.

    - absolute: retail uses stored `Prices` fields (player edits dollar amounts)
    - markup: retail is derived from supplier/wholesale unit cost and a markup %.
    """

    mode: PricingMode = "absolute"
    # key is the same product key used for Prices fields: booster, deck, single_common, ...
    markup_pct: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PricingSettings":
        if not data:
            return cls()
        mode = data.get("mode", "absolute")
        if mode not in ("absolute", "markup"):
            mode = "absolute"
        raw = data.get("markup_pct", {}) or {}
        mp: dict[str, float] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    mp[str(k)] = float(v)
                except Exception:
                    continue
        return cls(mode=mode, markup_pct=mp)

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "markup_pct": dict(self.markup_pct)}

    def get_markup_pct(self, product_key: str) -> float:
        return clamp_markup_pct(self.markup_pct.get(product_key, 0.0))

    def set_markup_pct(self, product_key: str, pct: float) -> None:
        self.markup_pct[product_key] = clamp_markup_pct(pct)


def clamp_markup_pct(pct: float) -> float:
    """Clamp markup to a sane range: 0%..200%."""
    p = float(pct)
    if p < 0.0:
        return 0.0
    if p > 2.0:
        return 2.0
    return p


def product_key(product: str) -> str | None:
    """Return the PricingSettings/Prices field key for a product id."""
    if product in {"booster", "deck"}:
        return product
    if product.startswith("single_"):
        return product
    return None


def wholesale_unit_cost(product: str) -> int | None:
    """Supplier/wholesale unit cost for ordering (NOT affected by retail pricing/markup)."""
    k = product_key(product)
    if not k:
        return None
    v = WHOLESALE_UNIT_COSTS.get(k)
    if v is None:
        return None
    return max(1, int(v))


def wholesale_order_total(product: str, qty: int) -> int | None:
    """Total supplier cost for ordering `qty` units of product."""
    unit = wholesale_unit_cost(product)
    if unit is None:
        return None
    q = max(0, int(qty))
    return max(1, unit * max(1, q)) if q > 0 else 0


def compute_retail_price(wholesale_cost: int, markup_pct: float) -> int:
    """Compute a retail price from wholesale cost and markup percent."""
    base = max(1, int(wholesale_cost))
    pct = clamp_markup_pct(markup_pct)
    return max(1, int(round(base * (1.0 + pct))))


def retail_base_price(prices: Prices, pricing: PricingSettings, product: str) -> int | None:
    """Retail base price before skill modifiers."""
    k = product_key(product)
    if not k:
        return None
    if pricing.mode == "absolute":
        return int(getattr(prices, k))
    # markup mode
    unit = wholesale_unit_cost(product)
    if unit is None:
        return None
    return compute_retail_price(unit, pricing.get_markup_pct(k))


def market_buy_price_single(rarity: str) -> int:
    """Market buy price for random singles (independent of player retail pricing)."""
    return max(1, int(MARKET_BUY_PRICES.get(str(rarity), 1)))

