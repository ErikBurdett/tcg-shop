from __future__ import annotations

import random

from game.cards.pack import open_booster
from game.cards.collection import CardCollection
from game.cards.deck import Deck
from game.cards.battle import BattleState
from game.cards.card_defs import get_all_cards
from game.sim.economy import choose_purchase
from game.config import Prices
from game.sim.inventory import Inventory, InventoryOrder
from game.sim.shop import ShopLayout


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

def test_shop_no_overlap_place() -> None:
    layout = ShopLayout()
    layout.objects.clear()
    layout.shelf_stocks.clear()
    layout.place("shelf", (2, 2))
    layout.place("counter", (2, 2))
    assert len(layout.objects) == 1


def test_order_delivery_apply() -> None:
    inv = Inventory()
    order = InventoryOrder(5, 0, {}, 20, 0, 10.0)
    # should not apply until delivery time, mimicking app logic
    now = 9.0
    if order.deliver_at <= now:
        inv.apply_order(order)
    assert inv.booster_packs == 0
    now = 10.0
    if order.deliver_at <= now:
        inv.apply_order(order)
    assert inv.booster_packs == 5


def test_debug_overlay_toggle_smoke() -> None:
    # Headless-friendly pygame init.
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    screen = pygame.display.get_surface()
    assert screen is not None

    from game.core.debug_overlay import DebugOverlay
    from game.ui.theme import Theme
    from game.ui.widgets import Button, Panel

    theme = Theme()
    overlay = DebugOverlay()

    # Enable and verify instrumentation doesn't crash.
    overlay.set_enabled(True)
    overlay.begin_frame(dt=1 / 60, fps=60.0)
    overlay.begin_input_timing()
    overlay.end_input_timing(events=3)

    # pygame.draw.* calls should be counted.
    pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(0, 0, 1, 1))
    assert overlay.frame.draw_calls >= 1

    # Disable should restore patched functions.
    overlay.set_enabled(False)
    pygame.draw.rect(screen, (0, 255, 0), pygame.Rect(0, 0, 1, 1))


def test_text_cache_lru_and_counters() -> None:
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))

    from game.ui.text_cache import TextCache

    font = pygame.font.SysFont("arial", 16)
    cache = TextCache(max_items=2)
    cache.begin_frame()
    s1 = cache.render(font, "hello", (255, 255, 255))
    assert cache.frame_misses == 1 and cache.frame_hits == 0
    s2 = cache.render(font, "hello", (255, 255, 255))
    assert s1 is s2
    assert cache.frame_hits == 1
    # Fill + evict oldest
    cache.render(font, "a", (255, 255, 255))
    cache.render(font, "b", (255, 255, 255))
    # "hello" should have been evicted (LRU) since max_items=2
    cache.begin_frame()
    s3 = cache.render(font, "hello", (255, 255, 255))
    assert cache.frame_misses == 1
    assert s3 is not s1


def test_day_night_pause_smoke() -> None:
    # Basic smoke test: pausing should freeze shop phase_timer progression.
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    screen = pygame.display.get_surface()
    assert screen is not None

    from game.core.app import GameApp

    app = GameApp(screen)
    shop = app.scenes["shop"]
    # Start day
    shop.start_day()
    assert shop.cycle_active is True
    assert shop.cycle_paused is False
    # Advance a bit
    shop.update(0.5)
    t1 = shop.phase_timer
    assert t1 >= 0.0
    # Pause
    shop.end_day()
    assert shop.cycle_paused is True
    # Updating scene should not advance cycle when paused
    shop.update(1.0)
    assert shop.phase_timer == t1


def test_staff_choose_restock_plan() -> None:
    from game.sim.actors import choose_restock_plan
    from game.sim.shop import ShelfStock
    from game.sim.inventory import Inventory
    from game.cards.collection import CardCollection
    from game.cards.deck import Deck

    inv = Inventory(booster_packs=5, decks=0, singles={"common": 0, "uncommon": 0, "rare": 0, "epic": 0, "legendary": 0})
    col = CardCollection()
    deck = Deck()
    # booster shelf low => should pick booster
    shelves = {"2,2": ShelfStock("booster", qty=1, max_qty=10)}
    plan = choose_restock_plan((0, 0), shelf_stocks=shelves, inventory=inv, collection=col, deck=deck)
    assert plan is not None and plan.product == "booster"

    # listed card shelf should prefer card restock if collection allows
    from game.cards.card_defs import get_all_cards

    cid = get_all_cards()[0].card_id
    col.add(cid, 2)
    shelves = {"3,3": ShelfStock(f"single_{get_all_cards()[0].rarity}", qty=1, max_qty=10, cards=[cid])}
    plan2 = choose_restock_plan((0, 0), shelf_stocks=shelves, inventory=Inventory(), collection=col, deck=deck)
    assert plan2 is not None and plan2.card_id == cid


def run() -> None:
    test_pack_generation()
    test_deck_rules()
    test_battle_flow()
    test_economy_purchase()
    test_shop_no_overlap_place()
    test_order_delivery_apply()
    test_debug_overlay_toggle_smoke()
    test_text_cache_lru_and_counters()
    test_day_night_pause_smoke()
    test_staff_choose_restock_plan()
    print("Sanity checks passed.")


if __name__ == "__main__":
    run()
