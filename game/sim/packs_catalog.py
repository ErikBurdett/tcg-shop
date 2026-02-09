from __future__ import annotations

from dataclasses import dataclass

from game.sim.inventory import Inventory


@dataclass(frozen=True)
class PackType:
    pack_id: str
    name: str
    description: str


# Future-proof: multiple sets/pack types can be added here.
PACK_TYPES: tuple[PackType, ...] = (
    PackType("booster", "Booster Pack", "Open a pack to add cards to your collection."),
)


def pack_count(inv: Inventory, pack_id: str) -> int:
    """Return how many packs of `pack_id` exist in inventory."""
    if pack_id == "booster":
        return max(0, int(inv.booster_packs))
    return 0

