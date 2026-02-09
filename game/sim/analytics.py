from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EventLogEntry:
    day: int
    t: float  # state.time_seconds at time of event
    kind: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"day": int(self.day), "t": float(self.t), "kind": str(self.kind), "message": str(self.message)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventLogEntry":
        return cls(
            day=int(data.get("day", 1)),
            t=float(data.get("t", 0.0)),
            kind=str(data.get("kind", "event")),
            message=str(data.get("message", "")),
        )


@dataclass
class DailyMetrics:
    visitors: int = 0
    revenue: int = 0
    # units sold by product key: booster, deck, single_common, ...
    units_sold: dict[str, int] = field(default_factory=dict)
    revenue_by_product: dict[str, int] = field(default_factory=dict)
    # restock items moved onto shelves (manual + staff)
    restocked: dict[str, int] = field(default_factory=dict)
    # orders placed/delivered (units)
    orders_placed: dict[str, int] = field(default_factory=dict)
    orders_delivered: dict[str, int] = field(default_factory=dict)
    # stockout events by shelf key (times a shelf hits qty=0 due to sales)
    stockouts_by_shelf: dict[str, int] = field(default_factory=dict)
    packs_opened: int = 0
    sells_back: int = 0  # count of sellback actions confirmed

    def to_dict(self) -> dict[str, Any]:
        return {
            "visitors": int(self.visitors),
            "revenue": int(self.revenue),
            "units_sold": dict(self.units_sold),
            "revenue_by_product": dict(self.revenue_by_product),
            "restocked": dict(self.restocked),
            "orders_placed": dict(self.orders_placed),
            "orders_delivered": dict(self.orders_delivered),
            "stockouts_by_shelf": dict(self.stockouts_by_shelf),
            "packs_opened": int(self.packs_opened),
            "sells_back": int(self.sells_back),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyMetrics":
        m = cls()
        m.visitors = int(data.get("visitors", 0))
        m.revenue = int(data.get("revenue", 0))
        m.units_sold = {str(k): int(v) for k, v in (data.get("units_sold", {}) or {}).items()}
        m.revenue_by_product = {str(k): int(v) for k, v in (data.get("revenue_by_product", {}) or {}).items()}
        m.restocked = {str(k): int(v) for k, v in (data.get("restocked", {}) or {}).items()}
        m.orders_placed = {str(k): int(v) for k, v in (data.get("orders_placed", {}) or {}).items()}
        m.orders_delivered = {str(k): int(v) for k, v in (data.get("orders_delivered", {}) or {}).items()}
        m.stockouts_by_shelf = {str(k): int(v) for k, v in (data.get("stockouts_by_shelf", {}) or {}).items()}
        m.packs_opened = int(data.get("packs_opened", 0))
        m.sells_back = int(data.get("sells_back", 0))
        return m


@dataclass
class AnalyticsState:
    """Persisted analytics (balancing + player-facing stats)."""

    days: dict[int, DailyMetrics] = field(default_factory=dict)
    event_log: list[EventLogEntry] = field(default_factory=list)
    max_events: int = 400  # cap persisted log size

    def _day(self, day: int) -> DailyMetrics:
        d = max(1, int(day))
        if d not in self.days:
            self.days[d] = DailyMetrics()
        return self.days[d]

    def log(self, *, day: int, t: float, kind: str, message: str) -> None:
        self.event_log.append(EventLogEntry(day=int(day), t=float(t), kind=str(kind), message=str(message)))
        if len(self.event_log) > int(self.max_events):
            self.event_log = self.event_log[-int(self.max_events) :]

    def record_visitor(self, *, day: int, t: float) -> None:
        self._day(day).visitors += 1

    def record_sale(
        self,
        *,
        day: int,
        t: float,
        product: str,
        revenue: int,
        shelf_key: str | None = None,
        became_empty: bool = False,
    ) -> None:
        m = self._day(day)
        m.revenue += int(revenue)
        m.units_sold[product] = int(m.units_sold.get(product, 0)) + 1
        m.revenue_by_product[product] = int(m.revenue_by_product.get(product, 0)) + int(revenue)
        if became_empty and shelf_key:
            m.stockouts_by_shelf[str(shelf_key)] = int(m.stockouts_by_shelf.get(str(shelf_key), 0)) + 1

    def record_restock(self, *, day: int, t: float, product: str, qty: int) -> None:
        if qty <= 0:
            return
        m = self._day(day)
        m.restocked[product] = int(m.restocked.get(product, 0)) + int(qty)

    def record_pack_open(self, *, day: int, t: float, packs: int) -> None:
        if packs <= 0:
            return
        self._day(day).packs_opened += int(packs)

    def record_order_placed(self, *, day: int, t: float, product: str, qty: int) -> None:
        if qty <= 0:
            return
        m = self._day(day)
        m.orders_placed[product] = int(m.orders_placed.get(product, 0)) + int(qty)

    def record_order_delivered(self, *, day: int, t: float, product: str, qty: int) -> None:
        if qty <= 0:
            return
        m = self._day(day)
        m.orders_delivered[product] = int(m.orders_delivered.get(product, 0)) + int(qty)

    def record_sellback(self, *, day: int, t: float, revenue: int) -> None:
        _ = revenue
        self._day(day).sells_back += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": {str(k): v.to_dict() for k, v in self.days.items()},
            "event_log": [e.to_dict() for e in self.event_log],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AnalyticsState":
        if not data:
            return cls()
        s = cls()
        raw_days = data.get("days", {}) or {}
        if isinstance(raw_days, dict):
            for k, v in raw_days.items():
                try:
                    day = int(k)
                except Exception:
                    continue
                if isinstance(v, dict):
                    s.days[day] = DailyMetrics.from_dict(v)
        raw_log = data.get("event_log", []) or []
        if isinstance(raw_log, list):
            for e in raw_log[-s.max_events :]:
                if isinstance(e, dict):
                    s.event_log.append(EventLogEntry.from_dict(e))
        return s

