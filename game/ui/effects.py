from __future__ import annotations

import pygame


_glow_cache: dict[tuple[int, int, tuple[int, int, int], int, int, int], pygame.Surface] = {}


def draw_glow_border(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    border_width: int = 2,
    glow_radius: int = 4,
    glow_alpha: int = 80,
    border_radius: int = 0,
) -> None:
    """Draw a subtle colored glow around rect + a crisp border.

    This uses a small temporary surface per call (fast enough for our current UI scale).
    """
    if glow_radius > 0 and glow_alpha > 0:
        key = (rect.width, rect.height, color, glow_radius, glow_alpha, border_radius)
        glow = _glow_cache.get(key)
        if glow is None:
            gw = rect.width + glow_radius * 2
            gh = rect.height + glow_radius * 2
            glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
            # Outer -> inner rings (soft falloff)
            for i in range(glow_radius, 0, -1):
                a = int(glow_alpha * (i / glow_radius) ** 2)
                ring_rect = pygame.Rect(
                    glow_radius - i,
                    glow_radius - i,
                    rect.width + i * 2,
                    rect.height + i * 2,
                )
                pygame.draw.rect(
                    glow,
                    (color[0], color[1], color[2], a),
                    ring_rect,
                    width=1,
                    border_radius=border_radius,
                )
            if len(_glow_cache) > 128:
                _glow_cache.clear()
            _glow_cache[key] = glow
        surface.blit(glow, (rect.x - glow_radius, rect.y - glow_radius))

    pygame.draw.rect(surface, color, rect, width=border_width, border_radius=border_radius)

