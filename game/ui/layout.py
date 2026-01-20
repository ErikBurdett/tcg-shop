from __future__ import annotations

import pygame


def anchor_rect(screen: pygame.Surface, size: tuple[int, int], anchor: str, padding: int = 12) -> pygame.Rect:
    width, height = size
    sw, sh = screen.get_size()
    if anchor == "topleft":
        return pygame.Rect(padding, padding, width, height)
    if anchor == "topright":
        return pygame.Rect(sw - width - padding, padding, width, height)
    if anchor == "bottomleft":
        return pygame.Rect(padding, sh - height - padding, width, height)
    if anchor == "bottomright":
        return pygame.Rect(sw - width - padding, sh - height - padding, width, height)
    if anchor == "center":
        return pygame.Rect((sw - width) // 2, (sh - height) // 2, width, height)
    return pygame.Rect(padding, padding, width, height)
