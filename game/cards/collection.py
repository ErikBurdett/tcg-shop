from __future__ import annotations

from dataclasses import dataclass

from game.cards.card_defs import CARD_INDEX, CardDef


@dataclass
class CardEntry:
    card_id: str
    qty: int


class CardCollection:
    def __init__(self) -> None:
        self.cards: dict[str, int] = {}
        self.revision: int = 0

    def add(self, card_id: str, amount: int = 1) -> None:
        self.cards[card_id] = self.cards.get(card_id, 0) + amount

    def remove(self, card_id: str, amount: int = 1) -> bool:
        if self.cards.get(card_id, 0) >= amount:
            self.cards[card_id] -= amount
            if self.cards[card_id] <= 0:
                self.cards.pop(card_id, None)
            return True
        return False

    def get(self, card_id: str) -> int:
        return self.cards.get(card_id, 0)

    def entries(self, rarity: str | None = None) -> list[CardEntry]:
        result: list[CardEntry] = []
        for card_id, qty in self.cards.items():
            if rarity and CARD_INDEX[card_id].rarity != rarity:
                continue
            result.append(CardEntry(card_id, qty))
        result.sort(key=lambda e: CARD_INDEX[e.card_id].name)
        return result

    def to_dict(self) -> dict:
        return {"cards": self.cards}

    @classmethod
    def from_dict(cls, data: dict) -> "CardCollection":
        collection = cls()
        collection.cards = dict(data.get("cards", {}))
        return collection

    def as_card(self, card_id: str) -> CardDef:
        return CARD_INDEX[card_id]
