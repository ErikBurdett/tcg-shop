from __future__ import annotations

import random

from game.cards.pack import open_booster
from game.cards.collection import CardCollection
from game.cards.deck import Deck
from game.cards.battle import BattleState
from game.cards.card_defs import get_all_cards
from game.sim.economy import choose_purchase
from game.config import Prices


def test_pack_generation() -> None:
    rng = random.Random(1)
    pack = open_booster(rng)
    assert len(pack) == 5


def test_deck_rules() -> None:
    collection = CardCollection()
    cards = get_all_cards()
    for card in cards[:10]:
        collection.add(card.card_id, 2)
    deck = Deck()
    deck.quick_fill(collection)
    assert deck.total() == 20
    for card_id, qty in deck.cards.items():
        assert qty <= 2


def test_battle_flow() -> None:
    rng = random.Random(2)
    cards = [card.card_id for card in get_all_cards()]
    player_deck = cards[:20]
    ai_deck = cards[:20]
    battle = BattleState(player_deck, ai_deck, rng)
    battle.start()
    assert battle.player_hand
    battle.end_turn()


def test_economy_purchase() -> None:
    rng = random.Random(3)
    prices = Prices()
    available = ["booster", "single_common"]
    item = choose_purchase(prices, available, rng)
    assert item in {"booster", "single_common", "none"}


def run() -> None:
    test_pack_generation()
    test_deck_rules()
    test_battle_flow()
    test_economy_purchase()
    print("Sanity checks passed.")


if __name__ == "__main__":
    run()
