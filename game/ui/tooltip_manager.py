from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

import pygame

from game.core.debug_overlay import _active as _debug_active
from game.ui.theme import Theme


@dataclass(frozen=True)
class TooltipStyle:
    """Rendering style for tooltips (included in cache key)."""

    font_id: int
    text_color: tuple[int, int, int]
    bg_color: tuple[int, int, int, int]
    border_color: tuple[int, int, int]
    padding: int = 6
    max_width: int = 340
    border_radius: int = 6


@dataclass(frozen=True)
class TooltipCacheKey:
    style: TooltipStyle
    text: str


@dataclass(frozen=True)
class TooltipRender:
    surf: pygame.Surface
    size: tuple[int, int]


class TooltipLRUCache:
    """Pure LRU cache for rendered tooltip surfaces."""

    def __init__(self, *, max_items: int = 256) -> None:
        self.max_items = max(1, int(max_items))
        self._cache: "OrderedDict[TooltipCacheKey, TooltipRender]" = OrderedDict()

    def get(self, key: TooltipCacheKey) -> TooltipRender | None:
        v = self._cache.get(key)
        if v is None:
            return None
        self._cache.move_to_end(key)
        return v

    def set(self, key: TooltipCacheKey, value: TooltipRender) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_items:
            self._cache.popitem(last=False)


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Word-wrap a single paragraph (no newlines) to fit max_width."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _wrap_text_block(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Wrap a possibly multi-line text block, preserving explicit newlines."""
    out: list[str] = []
    for para in (text or "").splitlines():
        wrapped = _wrap_text(font, para, max_width)
        out.extend(wrapped)
    if not out:
        out = [""]
    return out


def _render_tooltip(theme: Theme, *, key: TooltipCacheKey) -> TooltipRender:
    font = theme.font_small  # we key by font_id; keep consistent with Scene usage
    pad = key.style.padding
    max_w = max(120, int(key.style.max_width))
    lines = _wrap_text_block(font, key.text, max_w)

    # Measure.
    text_w = 0
    text_h = 0
    line_h = font.get_height()
    for line in lines:
        w, _h = font.size(line)
        text_w = max(text_w, w)
        text_h += line_h + 2
    text_h = max(line_h, text_h)

    w = text_w + pad * 2
    h = text_h + pad * 2
    w = max(80, min(w, max_w + pad * 2))

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    pygame.draw.rect(surf, key.style.bg_color, pygame.Rect(0, 0, w, h), border_radius=key.style.border_radius)
    pygame.draw.rect(surf, key.style.border_color, pygame.Rect(0, 0, w, h), 1, border_radius=key.style.border_radius)

    cy = pad
    for line in lines:
        t = theme.render_text(font, line, key.style.text_color)
        surf.blit(t, (pad, cy))
        cy += line_h + 2

    return TooltipRender(surf=surf, size=(w, h))


class TooltipManager:
    """Centralized tooltip manager with show delay + cached surfaces.

    Usage pattern:
    - Call set_target(...) each frame you have a tooltip candidate (or clear_target()).
    - Call update(dt, theme=...) each frame.
    - Call draw(surface, theme=...) each frame.
    """

    def __init__(self, *, delay_s: float = 0.2, offset: tuple[int, int] = (12, 12)) -> None:
        self.delay_s = float(delay_s)
        self.offset = offset
        self.cache = TooltipLRUCache(max_items=256)

        self._pending_key: TooltipCacheKey | None = None
        self._pending_pos: tuple[int, int] = (0, 0)
        self._pending_bounds: pygame.Rect | None = None
        self._pending_time: float = 0.0

        self._visible_key: TooltipCacheKey | None = None
        self._visible_pos: tuple[int, int] = (0, 0)
        self._visible_bounds: pygame.Rect | None = None
        self._visible: TooltipRender | None = None

    def clear_target(self) -> None:
        self._pending_key = None
        self._pending_time = 0.0
        self._visible_key = None
        self._visible = None

    def set_target(
        self,
        text: str | None,
        pos: tuple[int, int],
        *,
        theme: Theme,
        bounds: pygame.Rect | None,
        max_width: int = 340,
    ) -> None:
        if not text:
            self.clear_target()
            return

        style = TooltipStyle(
            font_id=id(theme.font_small),
            text_color=theme.colors.text,
            bg_color=(0, 0, 0, 180),
            border_color=theme.colors.border,
            padding=6,
            max_width=int(max_width),
            border_radius=6,
        )
        key = TooltipCacheKey(style=style, text=str(text))
        if key == self._pending_key:
            # Keep the timer running; just update position/bounds.
            self._pending_pos = pos
            self._pending_bounds = bounds
            return

        # New tooltip candidate -> restart delay.
        self._pending_key = key
        self._pending_pos = pos
        self._pending_bounds = bounds
        self._pending_time = 0.0

        # If currently visible is different, hide until delay elapses (prevents flicker).
        if self._visible_key != key:
            self._visible_key = None
            self._visible = None

    def update(self, dt: float, *, theme: Theme) -> None:
        _ = theme
        if not self._pending_key:
            return
        self._pending_time += float(dt)
        if self._pending_time < self.delay_s:
            return

        # Promote to visible.
        if self._visible_key != self._pending_key:
            self._visible_key = self._pending_key
            self._visible = self.cache.get(self._visible_key)
            if self._visible is None:
                self._visible = _render_tooltip(theme, key=self._visible_key)
                self.cache.set(self._visible_key, self._visible)
        self._visible_pos = self._pending_pos
        self._visible_bounds = self._pending_bounds

    def draw(self, surface: pygame.Surface, *, theme: Theme) -> None:
        _ = theme
        if not self._visible_key or not self._visible:
            return

        active = _debug_active()
        if active is not None:
            active.frame.tooltip_count += 1

        sw, sh = surface.get_size()
        bounds = self._visible_bounds or pygame.Rect(0, 0, sw, sh)
        # Always clamp to the screen as well.
        screen_bounds = pygame.Rect(0, 0, sw, sh)
        bounds = bounds.clip(screen_bounds)

        ox, oy = self.offset
        x = int(self._visible_pos[0] + ox)
        y = int(self._visible_pos[1] + oy)
        w, h = self._visible.size

        # Clamp inside bounds.
        if x + w > bounds.right:
            x = bounds.right - w
        if y + h > bounds.bottom:
            y = bounds.bottom - h
        if x < bounds.left:
            x = bounds.left
        if y < bounds.top:
            y = bounds.top

        surface.blit(self._visible.surf, (x, y))

