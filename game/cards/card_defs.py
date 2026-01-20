from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardDef:
    card_id: str
    name: str
    rarity: str
    cost: int
    attack: int
    health: int


def _build_cards() -> list[CardDef]:
    cards: list[CardDef] = []
    for idx in range(1, 13):
        cards.append(CardDef(f"c{idx}", f"Sproutling {idx}", "common", 1, 1 + idx % 2, 2))
    for idx in range(1, 9):
        cards.append(CardDef(f"u{idx}", f"River Guard {idx}", "uncommon", 2, 2 + idx % 2, 3))
    for idx in range(1, 6):
        cards.append(CardDef(f"r{idx}", f"Skyblade {idx}", "rare", 3, 3 + idx % 2, 4))
    for idx in range(1, 4):
        cards.append(CardDef(f"e{idx}", f"Voidcaller {idx}", "epic", 4, 4 + idx % 2, 5))
    for idx in range(1, 3):
        cards.append(CardDef(f"l{idx}", f"Ancient Wyrm {idx}", "legendary", 5, 6, 6))
    return cards


CARD_POOL = _build_cards()
CARD_INDEX = {card.card_id: card for card in CARD_POOL}


def get_all_cards() -> list[CardDef]:
    return list(CARD_POOL)


def get_card(card_id: str) -> CardDef:
    return CARD_INDEX[card_id]
