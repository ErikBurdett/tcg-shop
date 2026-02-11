from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame
import random

from game.config import FPS, Prices, SEED, START_DAY, START_MONEY, START_PACKS
from game.core.events import EventBus
from game.core.input import InputMap
from game.core.save import SaveManager
from game.core.debug_overlay import DebugOverlay
from game.ui.theme import Theme
from game.sim.inventory import Inventory, InventoryOrder
from game.sim.shop import ShopLayout
from game.sim.progression import PlayerProgression
from game.sim.skill_tree import SkillTreeState, default_skill_tree, reconcile_skill_points
from game.sim.fixtures import FixtureInventory
from game.cards.collection import CardCollection
from game.cards.deck import Deck
from game.cards.card_defs import get_all_cards
from game.scenes.menu import MenuScene
from game.scenes.shop_scene import ShopScene
from game.scenes.manage_scene import ManageScene
from game.scenes.pack_open_scene import PackOpenScene
from game.scenes.deck_build_scene import DeckBuildScene
from game.scenes.battle_scene import BattleScene
from game.scenes.results_scene import ResultsScene
from game.assets import get_asset_manager
from game.sim.economy_rules import fixture_cost
from game.sim.skill_tree import Modifiers, get_default_skill_tree
from game.sim.pricing import PricingSettings
from game.sim.analytics import AnalyticsState


@dataclass
class DaySummary:
    revenue: int = 0
    profit: int = 0
    units_sold: int = 0
    customers: int = 0


@dataclass
class GameState:
    money: int
    day: int
    time_seconds: float
    prices: Prices
    inventory: Inventory
    collection: CardCollection
    deck: Deck
    shop_layout: ShopLayout
    pending_orders: list[InventoryOrder]
    last_summary: DaySummary
    progression: PlayerProgression
    skills: SkillTreeState
    fixtures: FixtureInventory
    shopkeeper_xp: int
    pricing: PricingSettings
    analytics: AnalyticsState

    def to_dict(self) -> dict[str, Any]:
        return {
            "money": self.money,
            "day": self.day,
            "time_seconds": self.time_seconds,
            "prices": self.prices.__dict__,
            "inventory": self.inventory.to_dict(),
            "collection": self.collection.to_dict(),
            "deck": self.deck.to_dict(),
            "shop_layout": self.shop_layout.to_dict(),
            "pending_orders": [order.to_dict() for order in self.pending_orders],
            "last_summary": self.last_summary.__dict__,
            "progression": self.progression.to_dict(),
            "skills": self.skills.to_dict(),
            "fixtures": self.fixtures.to_dict(),
            "shopkeeper_xp": int(self.shopkeeper_xp),
            "pricing": self.pricing.to_dict(),
            "analytics": self.analytics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        prog = PlayerProgression.from_dict(data.get("progression"))
        skills = SkillTreeState.from_dict(data.get("skills"))
        reconcile_skill_points(prog, skills)
        return cls(
            money=data["money"],
            day=data["day"],
            time_seconds=float(data.get("time_seconds", 0.0)),
            prices=Prices(**data["prices"]),
            inventory=Inventory.from_dict(data["inventory"]),
            collection=CardCollection.from_dict(data["collection"]),
            deck=Deck.from_dict(data["deck"]),
            shop_layout=ShopLayout.from_dict(data["shop_layout"]),
            pending_orders=[InventoryOrder.from_dict(d) for d in data.get("pending_orders", [])],
            last_summary=DaySummary(**data["last_summary"]),
            progression=prog,
            skills=skills,
            fixtures=FixtureInventory.from_dict(data.get("fixtures")),
            shopkeeper_xp=max(0, int(data.get("shopkeeper_xp", 0))),
            pricing=PricingSettings.from_dict(data.get("pricing")),
            analytics=AnalyticsState.from_dict(data.get("analytics")),
        )


class GameApp:
    """Main game application and loop."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.input_map = InputMap()
        self.events = EventBus()
        self.save = SaveManager()
        self.active_slot = 1
        self.theme = Theme()
        self.rng = random.Random(SEED)
        self.debug_overlay = False
        self.debug = DebugOverlay()
        self.console_open = False
        self.console_text = ""
        self.console_history: list[str] = []
        self.console_max_history = 6
        self.running = True
        self.state = self._new_game_state()
        self.scenes: dict[str, Any] = {}
        self.current_scene_key = "menu"
        self.battle_reward_pending = False
        # Initialize asset manager for card sprites
        get_asset_manager().init()
        self._build_scenes()

    def _new_game_state(self) -> GameState:
        collection = CardCollection()
        for card in get_all_cards():
            if card.rarity == "common":
                collection.add(card.card_id, 1)
        deck = Deck()
        inventory = Inventory(booster_packs=START_PACKS)
        layout = ShopLayout()
        # Initialize skills (definition is immutable; state stores ranks only).
        _ = default_skill_tree()
        return GameState(
            money=START_MONEY,
            day=START_DAY,
            time_seconds=0.0,
            prices=Prices(),
            inventory=inventory,
            collection=collection,
            deck=deck,
            shop_layout=layout,
            pending_orders=[],
            last_summary=DaySummary(),
            progression=PlayerProgression(),
            skills=SkillTreeState(),
            fixtures=FixtureInventory(),
            shopkeeper_xp=0,
            pricing=PricingSettings(),
            analytics=AnalyticsState(),
        )

    def _build_scenes(self) -> None:
        self.scenes = {
            "menu": MenuScene(self),
            "shop": ShopScene(self),
            "manage": ManageScene(self),
            "packs": PackOpenScene(self),
            "deck": DeckBuildScene(self),
            "battle": BattleScene(self),
            "results": ResultsScene(self),
        }

    def switch_scene(self, key: str) -> None:
        gameplay_tabs = {"shop", "packs", "sell", "deck", "manage", "stats", "skills", "battle"}
        if key in gameplay_tabs:
            target = "shop"
            if target not in self.scenes:
                return
            if self.current_scene_key and self.current_scene_key != target:
                self.scenes[self.current_scene_key].on_exit()
            self.current_scene_key = target
            self.scenes[self.current_scene_key].on_enter()
            shop = self.scenes.get(target)
            if shop and hasattr(shop, "_switch_tab"):
                shop._switch_tab(key)  # type: ignore[attr-defined]
            return

        if key not in self.scenes:
            return
        if self.current_scene_key:
            self.scenes[self.current_scene_key].on_exit()
        self.current_scene_key = key
        self.scenes[self.current_scene_key].on_enter()

    def load_game(self) -> bool:
        data = self.save.load(self.active_slot)
        if not data:
            return False
        self.state = GameState.from_dict(data)
        return True

    def load_game_slot(self, slot_id: int) -> bool:
        self.active_slot = max(1, slot_id)
        return self.load_game()

    def save_game(self) -> None:
        self.save.save(self.active_slot, self.state.to_dict())

    def start_new_game(self, *, save: bool = True) -> None:
        """Reset to a fresh game state and return to the shop."""
        self.state = self._new_game_state()
        if save:
            self.save_game()
        # Rebuild scenes to reset per-scene UI state cleanly.
        self._build_scenes()
        self.current_scene_key = "shop"
        self.scenes[self.current_scene_key].on_enter()

    def start_new_game_slot(self, slot_id: int, *, save: bool = True) -> None:
        self.active_slot = max(1, slot_id)
        self.start_new_game(save=save)

    def process_pending_orders(self) -> None:
        """Deliver any orders whose timer has elapsed."""
        now = self.state.time_seconds
        remaining: list[InventoryOrder] = []
        for order in self.state.pending_orders:
            # Back-compat: if deliver_at is missing/0, deliver immediately.
            deliver_at = order.deliver_at or 0.0
            if deliver_at <= now:
                self.state.inventory.apply_order(order)
                # Analytics: record delivery (per product type).
                day = int(self.state.day)
                if int(order.boosters) > 0:
                    self.state.analytics.record_order_delivered(day=day, t=now, product="booster", qty=int(order.boosters))
                    self.state.analytics.log(day=day, t=now, kind="delivery", message=f"Delivered boosters x{int(order.boosters)}")
                if int(order.decks) > 0:
                    self.state.analytics.record_order_delivered(day=day, t=now, product="deck", qty=int(order.decks))
                    self.state.analytics.log(day=day, t=now, kind="delivery", message=f"Delivered decks x{int(order.decks)}")
                for r, amt in (order.singles or {}).items():
                    if int(amt) > 0:
                        self.state.analytics.record_order_delivered(day=day, t=now, product=f"single_{r}", qty=int(amt))
                        self.state.analytics.log(day=day, t=now, kind="delivery", message=f"Delivered {r} singles x{int(amt)}")
            else:
                remaining.append(order)
        self.state.pending_orders = remaining

    def modifiers(self) -> Modifiers:
        """Return cached aggregated modifiers from the skill tree."""
        return self.state.skills.modifiers(get_default_skill_tree())

    def try_buy_fixture(self, kind: str) -> bool:
        """Attempt to buy a fixture into the player's fixture inventory."""
        cost = fixture_cost(kind, self.modifiers())
        if cost is None:
            return False
        if self.state.money < cost:
            return False
        self.state.money -= cost
        if kind == "shelf":
            self.state.fixtures.shelves += 1
            return True
        if kind == "counter":
            self.state.fixtures.counters += 1
            return True
        if kind == "poster":
            self.state.fixtures.posters += 1
            return True
        return False

    def try_place_object(self, kind: str, tile: tuple[int, int]) -> bool:
        """Attempt to place an object on the shop grid.

        For fixtures (shelf/counter/poster), this consumes an owned fixture from `state.fixtures`.
        If placement fails, the consumed fixture is refunded.
        """
        needs_fixture = kind in {"shelf", "counter", "poster"}
        if needs_fixture:
            if not self.state.fixtures.consume_for_place(kind):
                return False
        before = len(self.state.shop_layout.objects)
        self.state.shop_layout.place(kind, tile)
        after = len(self.state.shop_layout.objects)
        placed = after > before
        if not placed and needs_fixture:
            # Refund on failure.
            if kind == "shelf":
                self.state.fixtures.shelves += 1
            elif kind == "counter":
                self.state.fixtures.counters += 1
            elif kind == "poster":
                self.state.fixtures.posters += 1
        return placed

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            # Clamp dt to avoid huge simulation jumps on hitches (helps UI feel stable).
            dt = min(dt, 1 / 20)
            # Pause simulation time when the shop cycle is paused.
            shop = self.scenes.get("shop")
            sim_paused = bool(getattr(shop, "cycle_active", False) and getattr(shop, "cycle_paused", False)) if shop else False
            if self.debug_overlay:
                self.debug.begin_frame(dt=dt, fps=self.clock.get_fps())
                # Reset per-frame cache counters (shown in overlay).
                if hasattr(self.theme, "text_cache"):
                    self.theme.text_cache.begin_frame()  # type: ignore[attr-defined]
                self.debug.begin_input_timing()
                events = self._handle_events()
                self.debug.end_input_timing(events=events)
            else:
                self._handle_events()
            sim_dt = 0.0 if sim_paused else dt
            self.state.time_seconds += sim_dt
            if sim_dt > 0:
                self.process_pending_orders()
            if self.debug_overlay:
                self.debug.begin_update_timing()
                self.scenes[self.current_scene_key].update(dt)
                self.debug.end_update_timing()
                self.debug.begin_draw_timing()
                self._draw()
                self.debug.end_draw_timing()
                self._log_frame_spike_if_needed()
            else:
                self.scenes[self.current_scene_key].update(dt)
                self._draw()

    def _handle_events(self) -> int:
        count = 0
        for event in pygame.event.get():
            count += 1
            if event.type == pygame.QUIT:
                self.running = False
                return count

            if self.input_map.is_action(event, "debug"):
                self.debug_overlay = not self.debug_overlay
                self.debug.set_enabled(self.debug_overlay)
            if self.input_map.is_action(event, "console"):
                self.console_open = not self.console_open
                if not self.console_open:
                    self.console_text = ""
            if self.input_map.is_action(event, "back") and self.current_scene_key not in ("menu", "shop"):
                self.switch_scene("shop")
            if self.console_open:
                self._handle_console_event(event)
            else:
                self.scenes[self.current_scene_key].handle_event(event)
        return count

    def _handle_console_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_RETURN:
            self._execute_console()
        elif event.key == pygame.K_BACKSPACE:
            self.console_text = self.console_text[:-1]
        elif event.unicode:
            self.console_text += event.unicode

    def _execute_console(self) -> None:
        text = self.console_text.strip()
        if text:
            self.console_history.append(text)
            self.console_history = self.console_history[-self.console_max_history :]
            self._run_console_command(text)
        self.console_text = ""

    def _run_console_command(self, text: str) -> None:
        parts = text.split()
        if not parts:
            return
        cmd = parts[0].lower()
        if cmd == "money" and len(parts) > 1:
            self.state.money += int(parts[1])
        elif cmd == "packs" and len(parts) > 1:
            self.state.inventory.booster_packs += int(parts[1])
        elif cmd == "deckfill":
            self.state.deck.quick_fill(self.state.collection)

    def _draw(self) -> None:
        self.screen.fill(self.theme.colors.bg)
        self.scenes[self.current_scene_key].draw(self.screen)
        if self.debug_overlay:
            self._draw_debug_overlay()
        if self.console_open:
            self._draw_console()
        pygame.display.flip()

    def _draw_debug_overlay(self) -> None:
        scene = self.scenes.get(self.current_scene_key)
        scene_lines: list[str] = []
        if scene and hasattr(scene, "debug_lines"):
            try:
                scene_lines = list(scene.debug_lines())  # type: ignore[misc]
            except Exception:
                scene_lines = []
        hits = 0
        misses = 0
        if hasattr(self.theme, "text_cache"):
            hits = int(getattr(self.theme.text_cache, "frame_hits", 0))  # type: ignore[attr-defined]
            misses = int(getattr(self.theme.text_cache, "frame_misses", 0))  # type: ignore[attr-defined]
        self.debug.frame.text_hits = hits
        self.debug.frame.text_misses = misses

        # Customer spawn metrics (computed only when debug overlay is on).
        active_customers = 0
        spawn_interval_s = 0.0
        next_spawn_s = -1.0
        shop = self.scenes.get("shop")
        try:
            if shop and hasattr(shop, "customers"):
                customers = list(getattr(shop, "customers", []))
                for c in customers:
                    if not bool(getattr(c, "done", False)):
                        active_customers += 1
                schedule = list(getattr(shop, "customer_schedule", []))
                spawned = int(getattr(shop, "spawned", 0))
                phase_timer = float(getattr(shop, "phase_timer", 0.0))
                if len(schedule) >= 2:
                    spawn_interval_s = float(schedule[1] - schedule[0])
                elif len(schedule) == 1:
                    spawn_interval_s = float(getattr(shop, "day_duration", 60.0))
                if schedule and 0 <= spawned < len(schedule):
                    next_spawn_s = max(0.0, float(schedule[spawned]) - phase_timer)
        except Exception:
            active_customers = 0
            spawn_interval_s = 0.0
            next_spawn_s = -1.0
        self.debug.frame.active_customers = active_customers
        self.debug.frame.spawn_interval_s = spawn_interval_s
        self.debug.frame.next_spawn_s = next_spawn_s

        extra = [
            f"Scene: {self.current_scene_key}",
            f"Money: ${self.state.money}",
            f"Day: {self.state.day}",
            f"Boosters: {self.state.inventory.booster_packs}",
            f"Decks: {self.state.inventory.decks}",
            f"Singles: {self.state.inventory.total_singles()}",
        ] + scene_lines
        self.debug.draw(self.screen, theme=self.theme, extra_lines=extra)

    def _log_frame_spike_if_needed(self) -> None:
        """Print one-line spike summary when dt exceeds threshold (debug on only)."""
        if not self.debug_overlay or not self.debug.enabled:
            return
        f = self.debug.frame
        if f.dt_ms <= 25.0:
            return
        print(
            "[frame_spike] "
            f"dt={f.dt_ms:0.2f}ms "
            f"input={f.input_ms:0.2f}ms "
            f"update={f.update_ms:0.2f}ms "
            f"draw={f.draw_ms:0.2f}ms "
            f"customers={f.active_customers} "
            f"tooltips={f.tooltip_count}"
        )

    def _draw_console(self) -> None:
        rect = pygame.Rect(12, 520, 520, 180)
        pygame.draw.rect(self.screen, self.theme.colors.panel, rect)
        pygame.draw.rect(self.screen, self.theme.colors.border, rect, 2)
        font = self.theme.font_small
        y = rect.y + 8
        for line in self.console_history[-self.console_max_history :]:
            self.screen.blit(font.render(line, True, self.theme.colors.text), (rect.x + 8, y))
            y += 18
        prompt = f"> {self.console_text}"
        self.screen.blit(font.render(prompt, True, self.theme.colors.text), (rect.x + 8, rect.bottom - 26))
