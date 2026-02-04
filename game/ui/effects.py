from __future__ import annotations

import pygame


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
        gw = rect.width + glow_radius * 2
        gh = rect.height + glow_radius * 2
        glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
        # Outer -> inner rings (soft falloff)
        for i in range(glow_radius, 0, -1):
            a = int(glow_alpha * (i / glow_radius) ** 2)
            ring_rect = pygame.Rect(glow_radius - i, glow_radius - i, rect.width + i * 2, rect.height + i * 2)
            pygame.draw.rect(
                glow,
                (color[0], color[1], color[2], a),
                ring_rect,
                width=1,
                border_radius=border_radius,
            )
        surface.blit(glow, (rect.x - glow_radius, rect.y - glow_radius))

    pygame.draw.rect(surface, color, rect, width=border_width, border_radius=border_radius)

