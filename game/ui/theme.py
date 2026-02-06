from __future__ import annotations

import pygame

from game.ui.text_cache import TextCache


class Colors:
    bg = (20, 22, 28)
    panel = (34, 38, 46)
    panel_alt = (28, 30, 36)
    border = (70, 80, 90)
    text = (235, 235, 235)
    muted = (170, 170, 170)
    accent = (90, 170, 255)
    accent_hover = (120, 190, 255)
    danger = (220, 80, 80)
    good = (90, 200, 110)
    card_common = (180, 180, 180)
    card_uncommon = (90, 200, 130)
    card_rare = (90, 140, 230)
    card_epic = (180, 90, 220)
    card_legendary = (230, 160, 40)


class Theme:
    """Fonts and colors used across the UI."""

    def __init__(self) -> None:
        pygame.font.init()
        self.colors = Colors()
        self.font_small = pygame.font.SysFont("arial", 16)
        self.font = pygame.font.SysFont("arial", 20)
        self.font_large = pygame.font.SysFont("arial", 28)
        self.font_title = pygame.font.SysFont("arial", 48, bold=True)
        self.text_cache = TextCache(max_items=2048)

    def render_text(
        self, font: pygame.font.Font, text: str, color: tuple[int, int, int] | None = None
    ) -> pygame.Surface:
        """Render text using a shared cache."""
        c = color or self.colors.text
        return self.text_cache.render(font, text, c)
