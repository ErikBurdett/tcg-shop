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
from game.sim.progression import MAX_LEVEL, PlayerProgression, xp_to_next
from game.sim.skill_tree import SkillTreeState, default_skill_tree
from game.sim.economy_rules import apply_sell_price_pct, xp_from_sale, xp_from_battle_win
from game.sim.skill_tree import Modifiers
from game.sim.economy_rules import effective_sale_price
from game.sim.skill_tree import get_default_skill_tree
from game.sim.economy import customer_spawn_interval
from game.config import (
    CUSTOMER_SPAWN_INTERVAL_MIN,
    CUSTOMER_SPAWN_INTERVAL_START,
    CUSTOMER_SPAWN_RAMP_DAYS,
)


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


def test_staff_pickup_and_restock_smoke() -> None:
    from game.sim.actors import Staff, notify_shelf_change, update_staff
    from game.sim.shop import ShelfStock
    from game.sim.inventory import Inventory
    from game.cards.collection import CardCollection
    from game.cards.deck import Deck

    staff = Staff(pos=(1.5, 10.5), speed_tiles_per_s=10.0)
    inv = Inventory(booster_packs=10, decks=5, singles={"common": 5, "uncommon": 0, "rare": 0, "epic": 0, "legendary": 0})
    col = CardCollection()
    deck = Deck()
    shelves = {"2,2": ShelfStock("booster", qty=0, max_qty=10)}
    blocked = {(2, 2), (10, 7)}  # shelf tile and counter tile are occupied
    notify_shelf_change(staff, "2,2")

    did = False
    for _ in range(300):
        did = update_staff(
            staff,
            0.1,
            grid=(20, 12),
            blocked_tiles=blocked,
            counter_tile=(10, 7),
            shelf_stocks=shelves,
            inventory=inv,
            collection=col,
            deck=deck,
        ) or did
        if shelves["2,2"].qty > 0:
            break
    assert shelves["2,2"].qty > 0
    assert inv.booster_packs < 10  # picked up from inventory at counter


def test_progression_curve_monotonic_and_levelups() -> None:
    # xp_to_next should be monotonic increasing for 1..MAX_LEVEL-1
    prev = 0
    for lvl in range(1, MAX_LEVEL):
        need = xp_to_next(lvl)
        assert need > 0
        assert need >= prev
        prev = need

    p = PlayerProgression(level=1, xp=0, skill_points=0)
    # Add enough XP to multi-level up.
    total = sum(xp_to_next(lvl) for lvl in range(1, 15))
    res = p.add_xp(total)
    assert res.gained_levels >= 14
    assert res.gained_skill_points == res.gained_levels
    assert p.level >= 15
    # Skill points should increase with levels.
    assert p.skill_points == (p.level - 1)

    # Cap behavior.
    p2 = PlayerProgression(level=MAX_LEVEL, xp=999999, skill_points=123)
    res2 = p2.add_xp(999999)
    assert res2.gained_levels == 0
    assert p2.level == MAX_LEVEL
    assert p2.xp == 999999  # unchanged by add_xp at cap; normalization is in from_dict


def test_skill_tree_validation_and_unlock_rules() -> None:
    tree = default_skill_tree()
    prog = PlayerProgression(level=1, xp=0, skill_points=0)
    skills = SkillTreeState()

    # Can't rank up without points.
    ok, _ = skills.can_rank_up(tree, "haggle", prog)
    assert ok is False

    # Give points + rank up.
    prog.skill_points = 5
    ok2, _ = skills.can_rank_up(tree, "haggle", prog)
    assert ok2 is True
    assert skills.rank_up(tree, "haggle", prog) is True
    assert skills.rank("haggle") == 1
    assert prog.skill_points == 4

    # Prereq + level gating.
    ok3, _ = skills.can_rank_up(tree, "premium_display", prog)
    assert ok3 is False  # needs level + prereq ranks
    prog.level = 6
    # still needs haggle rank 3
    ok4, _ = skills.can_rank_up(tree, "premium_display", prog)
    assert ok4 is False
    # rank haggle to 3
    skills.rank_up(tree, "haggle", prog)
    skills.rank_up(tree, "haggle", prog)
    ok5, _ = skills.can_rank_up(tree, "premium_display", prog)
    assert ok5 is True

    # Modifiers caching should change only after rank-up.
    m1 = skills.modifiers(tree)
    assert m1.sell_price_pct > 0.0
    # Calling again returns cached object contents (value equality).
    m2 = skills.modifiers(tree)
    assert m2 == m1


def test_economy_rules_price_and_xp_math() -> None:
    assert apply_sell_price_pct(10, 0.0) == 10
    assert apply_sell_price_pct(10, 0.10) == 11
    assert apply_sell_price_pct(1, -0.99) == 1

    # XP math should be non-negative and scale with modifiers.
    tree = default_skill_tree()
    skills = SkillTreeState(ranks={"haggle": 2})
    prog = PlayerProgression(level=10, xp=0, skill_points=999)
    assert skills.rank_up(tree, "local_reputation", prog) is True
    mods = skills.modifiers(tree)
    assert xp_from_sale(10, mods) >= xp_from_sale(10, Modifiers())
    assert xp_from_battle_win(mods) >= xp_from_battle_win(Modifiers())


def test_save_backcompat_defaults_progression_skills_fixtures() -> None:
    # Old saves won't have these keys; loading should default cleanly.
    from game.core.app import GameState
    from game.config import Prices
    from game.sim.inventory import Inventory
    from game.cards.collection import CardCollection
    from game.cards.deck import Deck
    from game.sim.shop import ShopLayout

    d = {
        "money": 100,
        "day": 1,
        "time_seconds": 0.0,
        "prices": Prices().__dict__,
        "inventory": Inventory().to_dict(),
        "collection": CardCollection().to_dict(),
        "deck": Deck().to_dict(),
        "shop_layout": ShopLayout().to_dict(),
        "pending_orders": [],
        "last_summary": {"revenue": 0, "profit": 0, "units_sold": 0, "customers": 0},
        # no progression/skills/fixtures
    }
    s = GameState.from_dict(d)
    assert s.progression.level == 1
    assert s.skills.rank("haggle") == 0
    assert s.fixtures.shelves == 0
    assert s.shopkeeper_xp == 0


def test_sale_applies_sell_modifier_consistently() -> None:
    # Headless-friendly pygame init.
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    screen = pygame.display.get_surface()
    assert screen is not None

    from game.core.app import GameApp

    app = GameApp(screen)
    tree = get_default_skill_tree()
    # Give skill points and rank up Haggle to increase sell_price_pct.
    app.state.progression.skill_points = 20
    for _ in range(5):
        assert app.state.skills.rank_up(tree, "haggle", app.state.progression) is True
    mods = app.state.skills.modifiers(tree)
    assert mods.sell_price_pct > 0.0

    # Prepare a shelf sale.
    tile = (2, 2)
    app.state.shop_layout.place("shelf", tile)
    key = app.state.shop_layout._key(tile)
    stock = app.state.shop_layout.shelf_stocks[key]
    stock.product = "booster"
    stock.qty = 1
    app.state.prices.booster = 10

    expected = effective_sale_price(app.state.prices, "booster", mods)
    assert expected is not None
    before_money = app.state.money

    shop = app.scenes["shop"]
    shop._process_purchase((key, "booster"))  # type: ignore[attr-defined]
    assert app.state.money - before_money == expected


def test_customer_spawn_interval_ramp() -> None:
    start = float(CUSTOMER_SPAWN_INTERVAL_START)
    end = float(CUSTOMER_SPAWN_INTERVAL_MIN)
    assert customer_spawn_interval(1) == start
    assert customer_spawn_interval(1 + int(CUSTOMER_SPAWN_RAMP_DAYS) * 2) == end
    # Monotonic non-increasing across ramp window.
    prev = customer_spawn_interval(1)
    for d in range(2, 2 + int(CUSTOMER_SPAWN_RAMP_DAYS) + 3):
        cur = customer_spawn_interval(d)
        assert cur <= prev + 1e-9
        assert end - 1e-9 <= cur <= start + 1e-9
        prev = cur


def test_skill_points_reconcile_on_load() -> None:
    # If a save has skill ranks but incorrect/missing skill_points, load should reconcile.
    from game.core.app import GameState
    from game.config import Prices
    from game.sim.inventory import Inventory
    from game.cards.collection import CardCollection
    from game.cards.deck import Deck
    from game.sim.shop import ShopLayout

    d = {
        "money": 100,
        "day": 1,
        "time_seconds": 0.0,
        "prices": Prices().__dict__,
        "inventory": Inventory().to_dict(),
        "collection": CardCollection().to_dict(),
        "deck": Deck().to_dict(),
        "shop_layout": ShopLayout().to_dict(),
        "pending_orders": [],
        "last_summary": {"revenue": 0, "profit": 0, "units_sold": 0, "customers": 0},
        "progression": {"level": 10, "xp": 0, "skill_points": 0},
        "skills": {"ranks": {"haggle": 2, "sparring": 1}},  # spent=3, earned=9 => expected unspent=6
        "fixtures": {"shelves": 0, "counters": 0, "posters": 0},
    }
    s = GameState.from_dict(d)
    assert s.progression.level == 10
    assert s.progression.skill_points == 6


def test_tooltip_lru_cache_eviction() -> None:
    from game.ui.tooltip_manager import TooltipLRUCache, TooltipCacheKey, TooltipStyle

    cache = TooltipLRUCache(max_items=2)
    style = TooltipStyle(
        font_id=1,
        text_color=(255, 255, 255),
        bg_color=(0, 0, 0, 180),
        border_color=(10, 10, 10),
        padding=6,
        max_width=200,
        border_radius=6,
    )
    k1 = TooltipCacheKey(style=style, text="a")
    k2 = TooltipCacheKey(style=style, text="b")
    k3 = TooltipCacheKey(style=style, text="c")
    dummy = object()

    cache.set(k1, dummy)  # type: ignore[arg-type]
    cache.set(k2, dummy)  # type: ignore[arg-type]
    assert cache.get(k1) is dummy
    # Touch k1 so k2 becomes LRU.
    cache.get(k1)
    cache.set(k3, dummy)  # evicts k2
    assert cache.get(k2) is None
    assert cache.get(k1) is dummy
    assert cache.get(k3) is dummy


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
    test_staff_pickup_and_restock_smoke()
    test_progression_curve_monotonic_and_levelups()
    test_skill_tree_validation_and_unlock_rules()
    test_economy_rules_price_and_xp_math()
    test_save_backcompat_defaults_progression_skills_fixtures()
    test_sale_applies_sell_modifier_consistently()
    test_customer_spawn_interval_ramp()
    test_skill_points_reconcile_on_load()
    test_tooltip_lru_cache_eviction()
    print("Sanity checks passed.")


if __name__ == "__main__":
    run()
