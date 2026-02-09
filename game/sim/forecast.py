from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from game.config import DAY_DURATION_SECONDS
from game.sim.analytics import AnalyticsState
from game.sim.shop import ShelfStock
from game.sim.inventory import Inventory


@dataclass(frozen=True)
class RestockSuggestion:
    product: str
    recommended_qty: int
    avg_daily_units: float
    current_total_stock: int
    lead_time_s: float
    reason: str


def _product_keys() -> list[str]:
    return [
        "booster",
        "deck",
        "single_common",
        "single_uncommon",
        "single_rare",
        "single_epic",
        "single_legendary",
    ]


def _current_stock_for_product(product: str, *, inv: Inventory, shelves: dict[str, ShelfStock]) -> int:
    total = 0
    if product == "booster":
        total += int(inv.booster_packs)
    elif product == "deck":
        total += int(inv.decks)
    elif product.startswith("single_"):
        rarity = product.replace("single_", "")
        total += int(inv.singles.get(rarity, 0))
    # add shelf stock
    for stock in shelves.values():
        if int(stock.qty) <= 0:
            continue
        if getattr(stock, "cards", None):
            # listed cards count as singles of that rarity
            if product.startswith("single_"):
                rarity = product.replace("single_", "")
                if stock.cards and stock.product == f"single_{rarity}":
                    total += int(len(stock.cards))
            continue
        if stock.product == product:
            total += int(stock.qty)
    return int(total)


def sales_avg_daily_units(analytics: AnalyticsState, *, day: int, product: str, window_days: int = 3) -> float:
    """Compute average daily units sold over last N days (inclusive of current day if present)."""
    d = max(1, int(day))
    n = max(1, int(window_days))
    total = 0
    days = 0
    for dd in range(d, max(0, d - n), -1):
        m = analytics.days.get(dd)
        if not m:
            continue
        total += int(m.units_sold.get(product, 0))
        days += 1
    if days <= 0:
        return 0.0
    return float(total) / float(days)


def compute_restock_suggestions(
    analytics: AnalyticsState,
    *,
    day: int,
    inv: Inventory,
    shelves: dict[str, ShelfStock],
    lead_time_seconds: float = 30.0,
    window_days: int = 3,
    max_suggestions: int = 4,
) -> list[RestockSuggestion]:
    """Compute suggested reorder quantities (no automation; UI uses this)."""
    sug: list[RestockSuggestion] = []
    lead = max(1.0, float(lead_time_seconds))
    day_seconds = max(1.0, float(DAY_DURATION_SECONDS))
    for product in _product_keys():
        avg_daily = sales_avg_daily_units(analytics, day=day, product=product, window_days=window_days)
        if avg_daily <= 0.0:
            continue
        # Convert daily demand into lead-time demand.
        demand = (avg_daily / day_seconds) * lead
        # Safety: keep a small buffer (10% of daily demand, at least 1).
        safety = max(1.0, avg_daily * 0.10)
        want = float(demand + safety)
        current = _current_stock_for_product(product, inv=inv, shelves=shelves)
        rec = int(max(0, ceil(want - float(current))))
        if rec <= 0:
            continue
        reason = f"avg {avg_daily:0.2f}/day, lead {int(lead)}s"
        sug.append(
            RestockSuggestion(
                product=product,
                recommended_qty=int(rec),
                avg_daily_units=float(avg_daily),
                current_total_stock=int(current),
                lead_time_s=float(lead),
                reason=reason,
            )
        )
    sug.sort(key=lambda s: (s.recommended_qty, s.avg_daily_units), reverse=True)
    return sug[: max(1, int(max_suggestions))]


def top_stockout_shelves(analytics: AnalyticsState, *, day: int, window_days: int = 3, limit: int = 5) -> list[tuple[str, int]]:
    """Return shelves with the highest stockout event count over last N days."""
    d = max(1, int(day))
    n = max(1, int(window_days))
    counts: dict[str, int] = {}
    for dd in range(d, max(0, d - n), -1):
        m = analytics.days.get(dd)
        if not m:
            continue
        for k, v in m.stockouts_by_shelf.items():
            counts[k] = int(counts.get(k, 0)) + int(v)
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return items[: max(1, int(limit))]

