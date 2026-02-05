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
        # Scenes can disable the legacy top navigation bar (e.g., unified `ShopScene`).
        self.show_top_bar = True
        self.top_buttons: list[Button] = []
        self.day_buttons: list[Button] = []
        self._last_screen_size = self.app.screen.get_size()
        self._build_top_bar()
        self._build_day_buttons()

    def _shop_scene(self) -> object | None:
        # app.scenes may not be populated during early init.
        return getattr(self.app, "scenes", {}).get("shop") if hasattr(self.app, "scenes") else None

    def _is_day_running(self) -> bool:
        shop = self._shop_scene()
        return bool(getattr(shop, "day_running", False))

    def _global_start_day(self) -> None:
        shop = self._shop_scene()
        if shop and hasattr(shop, "start_day"):
            shop.start_day()  # type: ignore[misc]

    def _global_stop_day(self) -> None:
        shop = self._shop_scene()
        if shop and hasattr(shop, "end_day") and getattr(shop, "day_running", False):
            shop.end_day()  # type: ignore[misc]

    def _build_day_buttons(self) -> None:
        self.day_buttons.clear()
        w, h = self.app.screen.get_size()
        margin = 12
        btn_w = 180
        btn_h = 34
        gap = 8
        total_w = btn_w * 2 + gap
        x = max(margin, (w - total_w) // 2)
        y = h - margin - btn_h
        start = Button(pygame.Rect(x, y, btn_w, btn_h), "Start Day", self._global_start_day)
        stop = Button(pygame.Rect(x + btn_w + gap, y, btn_w, btn_h), "Stop Day", self._global_stop_day)
        self.day_buttons = [start, stop]
        self._sync_day_buttons()

    def _sync_day_buttons(self) -> None:
        running = self._is_day_running()
        if not self.day_buttons:
            return
        self.day_buttons[0].text = "Start Day" if not running else "Day Running"
        self.day_buttons[0].enabled = not running
        self.day_buttons[1].text = "Stop Day"
        self.day_buttons[1].enabled = running

    def _build_top_bar(self) -> None:
        self.top_buttons.clear()
        if not self.show_top_bar:
            return
        padding = 8
        width = 110
        height = 34
        x0 = 8
        y0 = 8
        screen_w = self.app.screen.get_width()
        per_row = max(1, (screen_w - x0 * 2) // (width + padding))
        for i, tab in enumerate(self.TABS):
            row = i // per_row
            col = i % per_row
            x = x0 + col * (width + padding)
            y = y0 + row * (height + 8)
            rect = pygame.Rect(x, y, width, height)
            self.top_buttons.append(
                Button(rect, tab.name, on_click=self._make_tab_handler(tab.scene_key))
            )

    def _make_tab_handler(self, key: str) -> Callable[[], None]:
        def handler() -> None:
            self.app.switch_scene(key)

        return handler

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.show_top_bar:
            for button in self.top_buttons:
                button.handle_event(event)
        for button in self.day_buttons:
            button.handle_event(event)

    def update(self, dt: float) -> None:
        _ = dt
        if self.app.screen.get_size() != self._last_screen_size:
            self._last_screen_size = self.app.screen.get_size()
            if self.show_top_bar:
                self._build_top_bar()
            self._build_day_buttons()
        if self.show_top_bar:
            for button in self.top_buttons:
                button.update(dt)
        for button in self.day_buttons:
            button.update(dt)
        self._sync_day_buttons()

    def draw(self, surface: pygame.Surface) -> None:
        if self.show_top_bar:
            for button in self.top_buttons:
                button.draw(surface, self.theme)
        for button in self.day_buttons:
            button.draw(surface, self.theme)

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass
