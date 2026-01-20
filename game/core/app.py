from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame
import random

from game.config import FPS, Prices, SEED, START_DAY, START_MONEY, START_PACKS
from game.core.events import EventBus
from game.core.input import InputMap
from game.core.save import SaveManager
from game.ui.theme import Theme
from game.sim.inventory import Inventory, InventoryOrder
from game.sim.shop import ShopLayout
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
    prices: Prices
    inventory: Inventory
    collection: CardCollection
    deck: Deck
    shop_layout: ShopLayout
    pending_orders: list[InventoryOrder]
    last_summary: DaySummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "money": self.money,
            "day": self.day,
            "prices": self.prices.__dict__,
            "inventory": self.inventory.to_dict(),
            "collection": self.collection.to_dict(),
            "deck": self.deck.to_dict(),
            "shop_layout": self.shop_layout.to_dict(),
            "pending_orders": [order.to_dict() for order in self.pending_orders],
            "last_summary": self.last_summary.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        return cls(
            money=data["money"],
            day=data["day"],
            prices=Prices(**data["prices"]),
            inventory=Inventory.from_dict(data["inventory"]),
            collection=CardCollection.from_dict(data["collection"]),
            deck=Deck.from_dict(data["deck"]),
            shop_layout=ShopLayout.from_dict(data["shop_layout"]),
            pending_orders=[InventoryOrder.from_dict(d) for d in data["pending_orders"]],
            last_summary=DaySummary(**data["last_summary"]),
        )


class GameApp:
    """Main game application and loop."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.input_map = InputMap()
        self.events = EventBus()
        self.save = SaveManager()
        self.theme = Theme()
        self.rng = random.Random(SEED)
        self.debug_overlay = False
        self.console_open = False
        self.console_text = ""
        self.console_history: list[str] = []
        self.console_max_history = 6
        self.running = True
        self.state = self._new_game_state()
        self.scenes: dict[str, Any] = {}
        self.current_scene_key = "shop"
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
        return GameState(
            money=START_MONEY,
            day=START_DAY,
            prices=Prices(),
            inventory=inventory,
            collection=collection,
            deck=deck,
            shop_layout=layout,
            pending_orders=[],
            last_summary=DaySummary(),
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
        if key not in self.scenes:
            return
        if self.current_scene_key:
            self.scenes[self.current_scene_key].on_exit()
        self.current_scene_key = key
        self.scenes[self.current_scene_key].on_enter()

    def load_game(self) -> bool:
        data = self.save.load()
        if not data:
            return False
        self.state = GameState.from_dict(data)
        return True

    def save_game(self) -> None:
        self.save.save(self.state.to_dict())

    def apply_end_of_day_orders(self) -> None:
        for order in self.state.pending_orders:
            self.state.inventory.apply_order(order)
        self.state.pending_orders.clear()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self.scenes[self.current_scene_key].update(dt)
            self._draw()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.input_map.is_action(event, "debug"):
                self.debug_overlay = not self.debug_overlay
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
        font = self.theme.font_small
        fps = int(self.clock.get_fps())
        lines = [
            f"FPS: {fps}",
            f"Scene: {self.current_scene_key}",
            f"Money: {self.state.money}",
            f"Day: {self.state.day}",
            f"Boosters: {self.state.inventory.booster_packs}",
            f"Decks: {self.state.inventory.decks}",
            f"Singles: {self.state.inventory.total_singles()}",
        ]
        x = 8
        y = 52
        for line in lines:
            text = font.render(line, True, self.theme.colors.text)
            self.screen.blit(text, (x, y))
            y += 18

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
