from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from game.ui.theme import Theme


@dataclass
class Toast:
    text: str
    ttl: float = 2.5
    color: tuple[int, int, int] | None = None


@dataclass
class ToastManager:
    """Non-blocking toast notifications (UI-only state)."""

    toasts: list[Toast] = field(default_factory=list)

    def push(self, text: str, *, ttl: float = 2.5, color: tuple[int, int, int] | None = None) -> None:
        self.toasts.append(Toast(text=text, ttl=ttl, color=color))
        # Keep a small bounded list.
        if len(self.toasts) > 6:
            self.toasts = self.toasts[-6:]

    def update(self, dt: float) -> None:
        if not self.toasts:
            return
        keep: list[Toast] = []
        for t in self.toasts:
            t.ttl -= dt
            if t.ttl > 0:
                keep.append(t)
        self.toasts = keep

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        if not self.toasts:
            return
        pad = 8
        x = 12
        y = 12
        for t in self.toasts:
            c = t.color or theme.colors.text
            text = theme.render_text(theme.font_small, t.text, c)
            rect = text.get_rect(topleft=(x + pad, y + pad))
            bg = rect.inflate(pad * 2, pad * 2)
            pygame.draw.rect(surface, theme.colors.panel, bg, border_radius=6)
            pygame.draw.rect(surface, theme.colors.border, bg, 1, border_radius=6)
            surface.blit(text, rect)
            y = bg.bottom + 8

