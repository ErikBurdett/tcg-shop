from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pygame

from game.ui.theme import Theme


class Button:
    def __init__(self, rect: pygame.Rect, text: str, on_click: Callable[[], None]) -> None:
        self.rect = rect
        self.text = text
        self.on_click = on_click
        self.hovered = False
        self.enabled = True
        self.tooltip: str | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.enabled:
            return
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()

    def update(self, dt: float) -> None:
        _ = dt

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        color = theme.colors.accent_hover if self.hovered else theme.colors.accent
        if not self.enabled:
            color = theme.colors.panel_alt
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, theme.colors.border, self.rect, 2, border_radius=4)
        text = theme.render_text(theme.font, self.text, theme.colors.text)
        surface.blit(text, text.get_rect(center=self.rect.center))


class Panel:
    def __init__(self, rect: pygame.Rect, title: str | None = None) -> None:
        self.rect = rect
        self.title = title
        # Cached "chrome" surface (background + border + title).
        # Keyed by size + title + theme identity so dragging (position changes) is cheap.
        self._chrome_surface: pygame.Surface | None = None
        self._chrome_key: tuple[int, int, str | None, int, tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]] | None = None
        self._chrome_dirty: bool = True
        # Debug/test hook: count how often we rebuild chrome.
        self._chrome_builds: int = 0

    def mark_dirty(self) -> None:
        """Force rebuilding the cached chrome on next draw."""
        self._chrome_dirty = True

    def _compute_chrome_key(self, theme: Theme) -> tuple[int, int, str | None, int, tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
        w = max(1, int(self.rect.width))
        h = max(1, int(self.rect.height))
        # Font identity matters for the title.
        font_id = id(theme.font)
        return (w, h, self.title, font_id, tuple(theme.colors.panel), tuple(theme.colors.border), tuple(theme.colors.text))

    def _ensure_chrome(self, theme: Theme) -> None:
        key = self._compute_chrome_key(theme)
        if not self._chrome_dirty and self._chrome_surface is not None and self._chrome_key == key:
            return
        w, h, _, _, _, _, _ = key
        surf = pygame.Surface((w, h))
        # Background + border
        surf.fill(theme.colors.panel)
        pygame.draw.rect(surf, theme.colors.border, pygame.Rect(0, 0, w, h), 2)
        # Title
        if self.title:
            text = theme.render_text(theme.font, self.title, theme.colors.text)
            surf.blit(text, (8, 6))
        self._chrome_surface = surf
        self._chrome_key = key
        self._chrome_dirty = False
        self._chrome_builds += 1

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._ensure_chrome(theme)
        if self._chrome_surface is not None:
            surface.blit(self._chrome_surface, self.rect.topleft)


class Label:
    def __init__(self, rect: pygame.Rect, text: str, color: tuple[int, int, int] | None = None) -> None:
        self.rect = rect
        self.text = text
        self.color = color

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        color = self.color or theme.colors.text
        text = theme.render_text(theme.font, self.text, color)
        surface.blit(text, self.rect.topleft)


@dataclass
class ScrollItem:
    key: Any
    label: str
    data: Any


class ScrollList:
    def __init__(self, rect: pygame.Rect, items: list[ScrollItem]) -> None:
        self.rect = rect
        self.items = items
        self.scroll_offset = 0
        self.item_height = 28
        self.on_select: Callable[[ScrollItem], None] | None = None
        self.hover_index: int | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset += -event.y * self.item_height
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        elif event.type == pygame.MOUSEMOTION:
            self.hover_index = self._index_at_pos(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._index_at_pos(event.pos)
            if idx is not None and self.on_select:
                self.on_select(self.items[idx])

    def _index_at_pos(self, pos: tuple[int, int]) -> int | None:
        if not self.rect.collidepoint(pos):
            return None
        rel_y = pos[1] - self.rect.y + self.scroll_offset
        idx = rel_y // self.item_height
        if 0 <= idx < len(self.items):
            return int(idx)
        return None

    def _max_scroll(self) -> int:
        total_height = len(self.items) * self.item_height
        return max(0, total_height - self.rect.height)

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        pygame.draw.rect(surface, theme.colors.panel_alt, self.rect)
        pygame.draw.rect(surface, theme.colors.border, self.rect, 1)
        clip = surface.get_clip()
        surface.set_clip(self.rect)
        y = self.rect.y - self.scroll_offset
        for idx, item in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x, y, self.rect.width, self.item_height)
            if idx == self.hover_index:
                pygame.draw.rect(surface, theme.colors.panel, item_rect)
            text = theme.render_text(theme.font_small, item.label, theme.colors.text)
            surface.blit(text, (item_rect.x + 6, item_rect.y + 6))
            y += self.item_height
        surface.set_clip(clip)


#
# NOTE: Tooltips are now centralized and cached in `game/ui/tooltip_manager.py`
# and integrated via `game/core/scene.py`. Avoid ad-hoc tooltip rendering here.
