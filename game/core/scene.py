from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from game.ui.widgets import Button
from game.ui.theme import Theme


@dataclass
class Tab:
    name: str
    scene_key: str


class Scene:
    """Base class for all scenes."""

    TABS = [
        Tab("Shop", "shop"),
        Tab("Manage", "manage"),
        Tab("Packs", "packs"),
        Tab("Deck", "deck"),
        Tab("Battle", "battle"),
        Tab("Menu", "menu"),
    ]

    def __init__(self, app: "GameApp") -> None:
        self.app = app
        self.theme = app.theme
        self.top_buttons: list[Button] = []
        self._build_top_bar()

    def _build_top_bar(self) -> None:
        self.top_buttons.clear()
        padding = 8
        width = 110
        height = 34
        x = 8
        y = 8
        for tab in self.TABS:
            rect = pygame.Rect(x, y, width, height)
            self.top_buttons.append(
                Button(rect, tab.name, on_click=self._make_tab_handler(tab.scene_key))
            )
            x += width + padding

    def _make_tab_handler(self, key: str) -> Callable[[], None]:
        def handler() -> None:
            self.app.switch_scene(key)

        return handler

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.top_buttons:
            button.handle_event(event)

    def update(self, dt: float) -> None:
        for button in self.top_buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for button in self.top_buttons:
            button.draw(surface, self.theme)

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass
