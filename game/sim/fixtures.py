from __future__ import annotations

from dataclasses import dataclass, field

from game.sim.shop import ShopLayout


@dataclass
class FixtureInventory:
    """Counts of owned-but-not-placed fixtures.

    Placed fixtures live in `ShopLayout.objects`. This inventory tracks additional fixtures
    the player can place.
    """

    shelves: int = 0
    counters: int = 0
    posters: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"shelves": int(self.shelves), "counters": int(self.counters), "posters": int(self.posters)}

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "FixtureInventory":
        if not data:
            return cls()
        return cls(
            shelves=max(0, int(data.get("shelves", 0))),  # type: ignore[arg-type]
            counters=max(0, int(data.get("counters", 0))),  # type: ignore[arg-type]
            posters=max(0, int(data.get("posters", 0))),  # type: ignore[arg-type]
        )

    def can_place(self, kind: str) -> bool:
        if kind == "shelf":
            return self.shelves > 0
        if kind == "counter":
            return self.counters > 0
        if kind == "poster":
            return self.posters > 0
        return True

    def consume_for_place(self, kind: str) -> bool:
        if kind == "shelf":
            if self.shelves <= 0:
                return False
            self.shelves -= 1
            return True
        if kind == "counter":
            if self.counters <= 0:
                return False
            self.counters -= 1
            return True
        if kind == "poster":
            if self.posters <= 0:
                return False
            self.posters -= 1
            return True
        return True


def count_placed_fixtures(layout: ShopLayout) -> dict[str, int]:
    counts: dict[str, int] = {"shelf": 0, "counter": 0, "poster": 0}
    for obj in layout.objects:
        if obj.kind in counts:
            counts[obj.kind] += 1
    return counts

