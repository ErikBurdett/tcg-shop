from __future__ import annotations

"""
Generate replacement pixel-art assets with exact sizes and filenames.

Rules:
- This script overwrites existing PNGs in-place.
- It does NOT change any code paths that load assets.
"""

import os
import random
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "game" / "assets"


def _surface(size: tuple[int, int], *, alpha: bool = True) -> pygame.Surface:
    flags = pygame.SRCALPHA if alpha else 0
    surf = pygame.Surface(size, flags)
    if alpha:
        surf.fill((0, 0, 0, 0))
    return surf


def _px(s: pygame.Surface, x: int, y: int, c: tuple[int, int, int, int]) -> None:
    if 0 <= x < s.get_width() and 0 <= y < s.get_height():
        s.set_at((x, y), c)


def _rect(s: pygame.Surface, x: int, y: int, w: int, h: int, c: tuple[int, int, int, int]) -> None:
    pygame.draw.rect(s, c, pygame.Rect(x, y, w, h))


def _outline(s: pygame.Surface, x: int, y: int, w: int, h: int, c: tuple[int, int, int, int]) -> None:
    pygame.draw.rect(s, c, pygame.Rect(x, y, w, h), 1)


def make_floor_tile(variant: int, size: int = 48) -> pygame.Surface:
    r = random.Random(1000 + variant)
    s = _surface((size, size), alpha=True)
    base = (28, 30, 36, 255)
    _rect(s, 0, 0, size, size, base)

    # Stone blocks
    stone_cols = [(38, 40, 48, 255), (34, 36, 44, 255), (42, 44, 52, 255)]
    grout = (18, 18, 22, 255)
    x = 0
    while x < size:
        bw = r.randint(8, 14)
        y = 0
        while y < size:
            bh = r.randint(8, 14)
            col = stone_cols[(variant + (x // 7) + (y // 5)) % len(stone_cols)]
            # Jitter a bit
            col = (
                max(0, min(255, col[0] + r.randint(-3, 3))),
                max(0, min(255, col[1] + r.randint(-3, 3))),
                max(0, min(255, col[2] + r.randint(-3, 3))),
                255,
            )
            _rect(s, x, y, bw, bh, col)
            _outline(s, x, y, bw, bh, grout)
            # tiny specks
            for _ in range(6):
                sx = x + r.randint(0, max(0, bw - 1))
                sy = y + r.randint(0, max(0, bh - 1))
                _px(s, sx, sy, (col[0] + 10, col[1] + 10, col[2] + 10, 255))
            y += bh
        x += bw

    # Variant-specific accents (subtle)
    if variant == 1:
        pygame.draw.line(s, (60, 65, 75, 255), (3, 14), (size - 6, 10), 1)
    elif variant == 2:
        pygame.draw.line(s, (55, 60, 70, 255), (6, size - 12), (size - 8, size - 18), 1)
    elif variant == 3:
        pygame.draw.line(s, (58, 62, 72, 255), (10, 6), (16, size - 8), 1)

    return s


def _humanoid(sprite_id: int, *, staff: bool) -> pygame.Surface:
    s = _surface((32, 32), alpha=True)
    r = random.Random(2000 + sprite_id)
    skin = (228, 196, 170, 255)
    outline = (20, 22, 28, 255)
    shirt = (70 + r.randint(-20, 20), 120 + r.randint(-20, 20), 160 + r.randint(-20, 20), 255)
    pants = (55, 60, 70, 255)
    hair = (60 + r.randint(-10, 20), 40 + r.randint(-10, 10), 25 + r.randint(-10, 10), 255)
    if staff:
        shirt = (90, 170, 255, 255)
        pants = (60, 60, 70, 255)

    # Body base (centered)
    cx = 16
    # Head
    _rect(s, cx - 4, 5, 8, 7, skin)
    _outline(s, cx - 4, 5, 8, 7, outline)
    # Hair/hat
    if staff:
        _rect(s, cx - 5, 4, 10, 3, (40, 40, 48, 255))
        _rect(s, cx - 4, 2, 8, 3, (40, 40, 48, 255))
    else:
        _rect(s, cx - 4, 5, 8, 2, hair)

    # Torso
    _rect(s, cx - 6, 12, 12, 9, shirt)
    _outline(s, cx - 6, 12, 12, 9, outline)

    # Apron for staff
    if staff:
        _rect(s, cx - 4, 14, 8, 8, (235, 235, 235, 255))
        _outline(s, cx - 4, 14, 8, 8, outline)

    # Arms
    _rect(s, cx - 8, 13, 2, 7, skin)
    _rect(s, cx + 6, 13, 2, 7, skin)
    _outline(s, cx - 8, 13, 2, 7, outline)
    _outline(s, cx + 6, 13, 2, 7, outline)

    # Legs
    _rect(s, cx - 5, 21, 4, 8, pants)
    _rect(s, cx + 1, 21, 4, 8, pants)
    _outline(s, cx - 5, 21, 4, 8, outline)
    _outline(s, cx + 1, 21, 4, 8, outline)

    # Shoes
    _rect(s, cx - 6, 29, 6, 2, (25, 25, 30, 255))
    _rect(s, cx, 29, 6, 2, (25, 25, 30, 255))

    # Eyes
    _px(s, cx - 2, 8, (10, 10, 12, 255))
    _px(s, cx + 1, 8, (10, 10, 12, 255))

    return s


def make_customer(customer_id: int) -> pygame.Surface:
    return _humanoid(customer_id, staff=(customer_id == 0))


def make_furniture_sheet() -> pygame.Surface:
    sheet = _surface((128, 64), alpha=True)

    def cell(col: int, row: int) -> tuple[int, int]:
        return (col * 16, row * 16)

    outline = (20, 22, 28, 255)

    # Poster (0,2): framed art
    x, y = cell(0, 2)
    _rect(sheet, x + 2, y + 2, 12, 12, (70, 55, 45, 255))
    _outline(sheet, x + 2, y + 2, 12, 12, outline)
    _rect(sheet, x + 4, y + 4, 8, 8, (40, 60, 90, 255))
    _px(sheet, x + 7, y + 7, (200, 220, 255, 255))

    # Shelf alt (1,1): brown shelf
    x, y = cell(1, 1)
    wood = (92, 62, 40, 255)
    _rect(sheet, x + 2, y + 4, 12, 10, wood)
    _outline(sheet, x + 2, y + 4, 12, 10, outline)
    _rect(sheet, x + 3, y + 7, 10, 1, (70, 45, 30, 255))
    _rect(sheet, x + 3, y + 11, 10, 1, (70, 45, 30, 255))

    # Shelf (1,2): blue shelf
    x, y = cell(1, 2)
    blue = (60, 110, 160, 255)
    _rect(sheet, x + 2, y + 4, 12, 10, blue)
    _outline(sheet, x + 2, y + 4, 12, 10, outline)
    _rect(sheet, x + 3, y + 7, 10, 1, (40, 80, 120, 255))
    _rect(sheet, x + 3, y + 11, 10, 1, (40, 80, 120, 255))

    # Counter (7,0): table/counter
    x, y = cell(7, 0)
    top = (110, 75, 45, 255)
    leg = (80, 55, 35, 255)
    _rect(sheet, x + 1, y + 5, 14, 4, top)
    _outline(sheet, x + 1, y + 5, 14, 4, outline)
    _rect(sheet, x + 3, y + 9, 2, 6, leg)
    _rect(sheet, x + 11, y + 9, 2, 6, leg)
    _outline(sheet, x + 3, y + 9, 2, 6, outline)
    _outline(sheet, x + 11, y + 9, 2, 6, outline)

    # Fill some additional cells with subtle decor so the sheet isn't empty
    # Plant (4,1)
    x, y = cell(4, 1)
    pot = (95, 60, 40, 255)
    green = (60, 140, 80, 255)
    _rect(sheet, x + 6, y + 10, 4, 5, pot)
    _outline(sheet, x + 6, y + 10, 4, 5, outline)
    _rect(sheet, x + 5, y + 6, 6, 5, green)
    _outline(sheet, x + 5, y + 6, 6, 5, outline)

    # Chair (2,1)
    x, y = cell(2, 1)
    cwood = (95, 70, 45, 255)
    _rect(sheet, x + 5, y + 8, 6, 3, cwood)
    _rect(sheet, x + 5, y + 5, 2, 3, cwood)
    _rect(sheet, x + 9, y + 5, 2, 3, cwood)
    _outline(sheet, x + 5, y + 8, 6, 3, outline)

    return sheet


def make_card_tile(tile_num: int) -> pygame.Surface:
    s = _surface((32, 32), alpha=True)
    r = random.Random(3000 + tile_num)
    outline = (18, 18, 22, 255)

    # Two families to match current usage: 1-8 (knights), 37-48 (slimes/elementals)
    if 1 <= tile_num <= 8:
        armor = (110 + r.randint(-10, 10), 120 + r.randint(-10, 10), 135 + r.randint(-10, 10), 255)
        cloth = (60, 110, 160, 255)
        skin = (228, 196, 170, 255)
        cx = 16
        # Head/helm
        _rect(s, cx - 4, 4, 8, 8, armor)
        _outline(s, cx - 4, 4, 8, 8, outline)
        _rect(s, cx - 2, 6, 4, 2, (20, 22, 28, 255))  # visor
        # Torso
        _rect(s, cx - 6, 12, 12, 10, armor)
        _outline(s, cx - 6, 12, 12, 10, outline)
        _rect(s, cx - 5, 14, 10, 6, cloth)
        # Arms
        _rect(s, cx - 9, 13, 3, 8, armor)
        _rect(s, cx + 6, 13, 3, 8, armor)
        _outline(s, cx - 9, 13, 3, 8, outline)
        _outline(s, cx + 6, 13, 3, 8, outline)
        # Legs
        _rect(s, cx - 5, 22, 4, 8, armor)
        _rect(s, cx + 1, 22, 4, 8, armor)
        _outline(s, cx - 5, 22, 4, 8, outline)
        _outline(s, cx + 1, 22, 4, 8, outline)
        # Sword
        _rect(s, cx + 8, 10, 1, 16, (200, 200, 205, 255))
        _rect(s, cx + 7, 24, 3, 2, (120, 90, 60, 255))
        # Face hint
        _px(s, cx - 2, 8, skin)
        _px(s, cx + 1, 8, skin)
    else:
        body = (70, 180, 120, 255) if (tile_num % 2 == 0) else (90, 140, 230, 255)
        glow = (180, 90, 220, 120)
        # Slime blob
        for y in range(6, 28):
            for x in range(6, 26):
                dx = x - 16
                dy = y - 18
                if dx * dx + dy * dy <= 90 + (tile_num % 5) * 8:
                    _px(s, x, y, body)
        # Outline-ish
        pygame.draw.ellipse(s, outline, pygame.Rect(6, 6, 20, 22), 1)
        # Eyes
        _px(s, 13, 16, (10, 10, 12, 255))
        _px(s, 19, 16, (10, 10, 12, 255))
        # Highlight
        pygame.draw.ellipse(s, glow, pygame.Rect(9, 10, 8, 6), 0)
    return s


def make_card_background_160x220() -> pygame.Surface:
    w, h = 160, 220
    s = _surface((w, h), alpha=True)
    # Dark gradient + vignette-like border (pixel style).
    top = (30, 32, 38, 255)
    bottom = (50, 55, 62, 255)
    for y in range(h):
        t = y / max(1, h - 1)
        c = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
            255,
        )
        pygame.draw.line(s, c, (0, y), (w - 1, y))
    # Border
    pygame.draw.rect(s, (15, 16, 20, 255), pygame.Rect(0, 0, w, h), 2)
    pygame.draw.rect(s, (70, 80, 90, 255), pygame.Rect(2, 2, w - 4, h - 4), 1)
    # Subtle emblem
    pygame.draw.rect(s, (70, 80, 90, 120), pygame.Rect(56, 80, 48, 48), 1)
    pygame.draw.line(s, (70, 80, 90, 120), (56, 104), (104, 104), 1)
    pygame.draw.line(s, (70, 80, 90, 120), (80, 80), (80, 128), 1)
    return s


def main() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))

    # Floor tiles (requested: 48×48)
    tiles_dir = ASSETS / "shop" / "tiles"
    for i in range(4):
        out = tiles_dir / f"floor_{i}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(make_floor_tile(i, 48), str(out))

    # Customers/staff (32×32)
    for i in range(8):
        out = tiles_dir / f"customer_{i}.png"
        pygame.image.save(make_customer(i), str(out))

    # Furniture sheet (128×64, 16×16 cells)
    furniture_path = ASSETS / "shop" / "furniture.png"
    pygame.image.save(make_furniture_sheet(), str(furniture_path))

    # Card tiles: runtime-used subset becomes 32×32 with alpha
    tc_tiles = ASSETS / "tiny-creatures" / "Tiles"
    used_tiles = list(range(1, 9)) + list(range(37, 49))
    for t in used_tiles:
        out = tc_tiles / f"tile_{t:04d}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(make_card_tile(t), str(out))

    # Reference card background (not currently runtime-loaded; procedural backgrounds still used)
    bg_path = ASSETS / "card_background_160x220.png"
    pygame.image.save(make_card_background_160x220(), str(bg_path))

    print("Generated assets:")
    print("- floor_0..3 (48×48)")
    print("- customer_0..7 (32×32)")
    print("- furniture.png (128×64, 16×16 cells)")
    print("- tiny-creatures used tiles (32×32, alpha)")
    print("- card_background_160x220.png (160×220 reference)")


if __name__ == "__main__":
    main()

