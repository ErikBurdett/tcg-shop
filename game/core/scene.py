from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from game.ui.widgets import Button
from game.ui.theme import Theme
from game.ui.toasts import ToastManager
from game.ui.tooltip_manager import TooltipManager


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
        self.tooltip = TooltipManager(delay_s=0.2)
        self.toasts = ToastManager()
        self._last_screen_size = self.app.screen.get_size()
        self._build_top_bar()
        self._build_day_buttons()

    def _shop_scene(self) -> object | None:
        # app.scenes may not be populated during early init.
        return getattr(self.app, "scenes", {}).get("shop") if hasattr(self.app, "scenes") else None

    def _cycle_state(self) -> tuple[bool, bool]:
        """Return (active, paused) for the shop day/night cycle."""
        shop = self._shop_scene()
        if not shop:
            return (False, False)
        active = bool(getattr(shop, "cycle_active", False))
        paused = bool(getattr(shop, "cycle_paused", False))
        return (active, paused)

    def _global_start_day(self) -> None:
        shop = self._shop_scene()
        if shop and hasattr(shop, "start_day"):
            shop.start_day()  # type: ignore[misc]

    def _global_stop_day(self) -> None:
        shop = self._shop_scene()
        # Stop == pause (do not end/advance the day).
        if shop and hasattr(shop, "end_day"):
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
        start.tooltip = "Start/resume the day-night cycle. Customers will visit and buy from stocked shelves."
        stop.tooltip = "Pause the day-night cycle. Time stops until you resume."
        self.day_buttons = [start, stop]
        self._sync_day_buttons()

    def _sync_day_buttons(self) -> None:
        active, paused = self._cycle_state()
        if not self.day_buttons:
            return
        if not active:
            self.day_buttons[0].text = "Start"
            self.day_buttons[0].enabled = True
            self.day_buttons[1].text = "Pause"
            self.day_buttons[1].enabled = False
        elif paused:
            self.day_buttons[0].text = "Resume"
            self.day_buttons[0].enabled = True
            self.day_buttons[1].text = "Paused"
            self.day_buttons[1].enabled = False
        else:
            self.day_buttons[0].text = "Running"
            self.day_buttons[0].enabled = False
            self.day_buttons[1].text = "Pause"
            self.day_buttons[1].enabled = True

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
            self.top_buttons[-1].tooltip = f"Go to: {tab.name}"

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
        self._update_global_tooltip()
        self.tooltip.update(dt, theme=self.theme)
        self.toasts.update(dt)

    def _tooltip_sources(self) -> list[Button]:
        """Buttons that participate in global tooltip discovery."""
        out: list[Button] = []
        if self.show_top_bar:
            out.extend(self.top_buttons)
        out.extend(self.day_buttons)
        return out

    def _extra_tooltip_text(self, pos: tuple[int, int]) -> str | None:
        _ = pos
        return None

    def _tooltip_bounds(self, pos: tuple[int, int]) -> pygame.Rect | None:
        """Optional bounds to clamp tooltips (e.g. inside a panel/viewport)."""
        _ = pos
        return None

    def _update_global_tooltip(self) -> None:
        pos = pygame.mouse.get_pos()
        extra = self._extra_tooltip_text(pos)
        if extra:
            self.tooltip.set_target(extra, pos, theme=self.theme, bounds=self._tooltip_bounds(pos))
            return
        text: str | None = None
        # Prefer the most recently created buttons (often visually on top).
        for b in reversed(self._tooltip_sources()):
            if not b.enabled:
                continue
            if not b.tooltip:
                continue
            if b.rect.collidepoint(pos):
                text = b.tooltip
                break
        if text:
            self.tooltip.set_target(text, pos, theme=self.theme, bounds=self._tooltip_bounds(pos))
        else:
            self.tooltip.clear_target()

    def draw(self, surface: pygame.Surface) -> None:
        if self.show_top_bar:
            for button in self.top_buttons:
                button.draw(surface, self.theme)
        for button in self.day_buttons:
            button.draw(surface, self.theme)

    def draw_overlays(self, surface: pygame.Surface) -> None:
        """Draw global overlays (toasts, tooltips) on top of all UI."""
        self.toasts.draw(surface, self.theme)
        self.tooltip.draw(surface, theme=self.theme)

    def debug_lines(self) -> list[str]:
        """Optional per-scene debug overlay lines."""
        return []

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass
