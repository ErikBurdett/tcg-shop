from __future__ import annotations

import random

from game.cards.card_defs import CARD_INDEX
from game.cards.collection import CardCollection


class Deck:
    def __init__(self) -> None:
        self.cards: dict[str, int] = {}

    def total(self) -> int:
        return sum(self.cards.values())

    def can_add(self, card_id: str) -> bool:
        return self.cards.get(card_id, 0) < 2 and self.total() < 20

    def add(self, card_id: str) -> bool:
        if not self.can_add(card_id):
            return False
        self.cards[card_id] = self.cards.get(card_id, 0) + 1
        return True

    def remove(self, card_id: str) -> bool:
        if self.cards.get(card_id, 0) > 0:
            self.cards[card_id] -= 1
            if self.cards[card_id] <= 0:
                self.cards.pop(card_id, None)
            return True
        return False

    def is_valid(self) -> bool:
        return self.total() == 20

    def card_list(self) -> list[str]:
        cards: list[str] = []
        for card_id, qty in self.cards.items():
            cards.extend([card_id] * qty)
        return cards

    def shuffled(self, rng: random.Random) -> list[str]:
        cards = self.card_list()
        rng.shuffle(cards)
        return cards

    def quick_fill(self, collection: CardCollection) -> None:
        self.cards.clear()
        for card_id, qty in collection.cards.items():
            for _ in range(min(2, qty)):
                if self.total() >= 20:
                    return
                self.add(card_id)

    def to_dict(self) -> dict:
        return {"cards": self.cards}

    @classmethod
    def from_dict(cls, data: dict) -> "Deck":
        deck = cls()
        deck.cards = dict(data.get("cards", {}))
        return deck

    def summary(self) -> list[tuple[str, int]]:
        items = list(self.cards.items())
        items.sort(key=lambda item: CARD_INDEX[item[0]].name)
        return items
