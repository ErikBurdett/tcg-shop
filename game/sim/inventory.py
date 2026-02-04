from __future__ import annotations

from dataclasses import dataclass


RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]


@dataclass
class InventoryOrder:
    boosters: int
    decks: int
    singles: dict[str, int]
    cost: int
    arrival_day: int = 0
    deliver_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "boosters": self.boosters,
            "decks": self.decks,
            "singles": self.singles,
            "cost": self.cost,
            "arrival_day": self.arrival_day,
            "deliver_at": self.deliver_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InventoryOrder":
        return cls(
            data["boosters"],
            data.get("decks", 0),
            data.get("singles", {}),
            data.get("cost", 0),
            data.get("arrival_day", 0),
            float(data.get("deliver_at", 0.0)),
        )


class Inventory:
    """Store inventory of boosters, decks, and singles by rarity."""

    def __init__(
        self, booster_packs: int = 0, decks: int = 0, singles: dict[str, int] | None = None
    ) -> None:
        self.booster_packs = booster_packs
        self.decks = decks
        if singles is None:
            singles = {rarity: 0 for rarity in RARITIES}
        self.singles = singles

    def total_singles(self) -> int:
        return sum(self.singles.values())

    def add_boosters(self, amount: int) -> None:
        self.booster_packs += amount

    def remove_boosters(self, amount: int) -> bool:
        if self.booster_packs >= amount:
            self.booster_packs -= amount
            return True
        return False

    def add_decks(self, amount: int) -> None:
        self.decks += amount

    def remove_decks(self, amount: int) -> bool:
        if self.decks >= amount:
            self.decks -= amount
            return True
        return False

    def add_singles(self, rarity: str, amount: int) -> None:
        self.singles[rarity] = self.singles.get(rarity, 0) + amount

    def remove_single(self, rarity: str) -> bool:
        if self.singles.get(rarity, 0) > 0:
            self.singles[rarity] -= 1
            return True
        return False

    def apply_order(self, order: InventoryOrder) -> None:
        self.booster_packs += order.boosters
        self.decks += order.decks
        for rarity, amount in order.singles.items():
            self.add_singles(rarity, amount)

    def to_dict(self) -> dict:
        return {"booster_packs": self.booster_packs, "decks": self.decks, "singles": self.singles}

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        return cls(data["booster_packs"], data.get("decks", 0), data["singles"])
