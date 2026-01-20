from __future__ import annotations

import random

from game.cards.card_defs import CARD_POOL


RARITY_ROLL = [
    ("rare", 0.80),
    ("epic", 0.18),
    ("legendary", 0.02),
]


def open_booster(rng: random.Random) -> list[str]:
    commons = [c for c in CARD_POOL if c.rarity == "common"]
    uncommons = [c for c in CARD_POOL if c.rarity == "uncommon"]
    rares = [c for c in CARD_POOL if c.rarity in {"rare", "epic", "legendary"}]
    cards: list[str] = []
    cards.extend([rng.choice(commons).card_id for _ in range(3)])
    cards.append(rng.choice(uncommons).card_id)
    roll = rng.random()
    cumulative = 0.0
    chosen_rarity = "rare"
    for rarity, chance in RARITY_ROLL:
        cumulative += chance
        if roll <= cumulative:
            chosen_rarity = rarity
            break
    candidates = [c for c in rares if c.rarity == chosen_rarity]
    cards.append(rng.choice(candidates).card_id)
    return cards
