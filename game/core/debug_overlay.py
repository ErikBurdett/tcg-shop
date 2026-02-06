from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import pygame


@dataclass
class DebugFrameStats:
    fps: float = 0.0
    dt_ms: float = 0.0
    input_ms: float = 0.0
    events: int = 0
    update_ms: float = 0.0
    draw_ms: float = 0.0
    draw_calls: int = 0  # counts pygame.draw.* calls (instrumented)
    text_hits: int = 0
    text_misses: int = 0


_ACTIVE: "DebugOverlay | None" = None


def _active() -> "DebugOverlay | None":
    return _ACTIVE


class DebugOverlay:
    """Low-overhead debug overlay + optional instrumentation.

    When disabled:
    - No pygame.draw monkey-patching
    - No widget monkey-patching
    - No timing/counter work in the hot path unless the app explicitly calls begin/end
    """

    def __init__(self) -> None:
        self.enabled = False
        self.frame = DebugFrameStats()
        self._orig_pygame_draw: dict[str, Callable[..., Any]] = {}
        self._t_input_start: float = 0.0
        self._t_update_start: float = 0.0
        self._t_draw_start: float = 0.0

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self._install()
        else:
            self._uninstall()

    def begin_frame(self, *, dt: float, fps: float) -> None:
        """Reset per-frame counters (call once per frame when enabled)."""
        if not self.enabled:
            return
        self.frame.fps = float(fps)
        self.frame.dt_ms = float(dt) * 1000.0
        self.frame.input_ms = 0.0
        self.frame.events = 0
        self.frame.update_ms = 0.0
        self.frame.draw_ms = 0.0
        self.frame.draw_calls = 0
        self.frame.text_hits = 0
        self.frame.text_misses = 0

    def begin_input_timing(self) -> None:
        if not self.enabled:
            return
        self._t_input_start = perf_counter()

    def end_input_timing(self, *, events: int) -> None:
        if not self.enabled:
            return
        self.frame.input_ms = (perf_counter() - self._t_input_start) * 1000.0
        self.frame.events = int(events)

    def begin_update_timing(self) -> None:
        if not self.enabled:
            return
        self._t_update_start = perf_counter()

    def end_update_timing(self) -> None:
        if not self.enabled:
            return
        self.frame.update_ms = (perf_counter() - self._t_update_start) * 1000.0

    def begin_draw_timing(self) -> None:
        if not self.enabled:
            return
        self._t_draw_start = perf_counter()

    def end_draw_timing(self) -> None:
        if not self.enabled:
            return
        self.frame.draw_ms = (perf_counter() - self._t_draw_start) * 1000.0

    def draw(self, surface: pygame.Surface, *, theme: Any, extra_lines: list[str] | None = None) -> None:
        """Render the overlay. Keep this lightweight (runs only when enabled)."""
        if not self.enabled:
            return
        if extra_lines is None:
            extra_lines = []

        font = theme.font_small
        pad = 8
        lines = [
            f"FPS: {self.frame.fps:0.1f}",
            f"dt: {self.frame.dt_ms:0.2f} ms",
            f"input: {self.frame.input_ms:0.2f} ms ({self.frame.events} ev)",
            f"update: {self.frame.update_ms:0.2f} ms",
            f"draw: {self.frame.draw_ms:0.2f} ms",
            f"draw calls: {self.frame.draw_calls}",
            f"text cache: {self.frame.text_hits} hit / {self.frame.text_misses} miss",
            "toggle: F3",
        ] + extra_lines

        # Compute background size
        w = 0
        h = 0
        for line in lines:
            tw, th = font.size(line)
            w = max(w, tw)
            h += th + 2
        w += pad * 2
        h += pad * 2

        x, y = 8, 48
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        surface.blit(bg, (x, y))
        pygame.draw.rect(surface, (70, 80, 90), pygame.Rect(x, y, w, h), 1)

        cy = y + pad
        for line in lines:
            text = font.render(line, True, theme.colors.text)
            surface.blit(text, (x + pad, cy))
            cy += text.get_height() + 2

    # --- instrumentation installs ---

    def _install(self) -> None:
        global _ACTIVE
        _ACTIVE = self
        self._patch_pygame_draw()

    def _uninstall(self) -> None:
        global _ACTIVE
        self._restore_pygame_draw()
        _ACTIVE = None

    def _patch_pygame_draw(self) -> None:
        # Monkey patch only when enabled (so disabled cost is zero).
        if self._orig_pygame_draw:
            return

        draw_mod = pygame.draw
        names = [
            "rect",
            "circle",
            "ellipse",
            "line",
            "aaline",
            "lines",
            "aalines",
            "polygon",
            "arc",
        ]
        for name in names:
            if hasattr(draw_mod, name):
                orig = getattr(draw_mod, name)
                if callable(orig):
                    self._orig_pygame_draw[name] = orig

                    def make_wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
                        def wrapper(*args: Any, **kwargs: Any) -> Any:
                            active = _active()
                            if active is not None:
                                active.frame.draw_calls += 1
                            return fn(*args, **kwargs)

                        return wrapper

                    setattr(draw_mod, name, make_wrapper(orig))

    def _restore_pygame_draw(self) -> None:
        if not self._orig_pygame_draw:
            return
        draw_mod = pygame.draw
        for name, fn in self._orig_pygame_draw.items():
            setattr(draw_mod, name, fn)
        self._orig_pygame_draw.clear()

    # Note: we intentionally do not monkey-patch UI widgets here.
    # UI counters (text cache hits/misses, etc.) are tracked in the UI layer directly.

