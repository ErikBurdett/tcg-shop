from __future__ import annotations

"""
Headless screenshot capture for review.

Writes PNGs to docs/screenshots/:
1) shop_view.png (floor + furniture + customers + staff)
2) pack_open.png (card background + art)
3) battle_view.png (card art usage)
"""

import os
import sys
from pathlib import Path

import pygame


def main() -> None:
    # Ensure project root is importable when running from tools/.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((1600, 900))

    from game.core.app import GameApp

    app = GameApp(screen)
    out_dir = Path("docs/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Shop view
    app.switch_scene("shop")
    shop = app.scenes["shop"]
    # Ensure a shelf with stock exists so customers will buy.
    layout = app.state.shop_layout
    layout.place("shelf", (6, 6))
    key = layout._key((6, 6))
    stock = layout.shelf_stocks[key]
    stock.product = "booster"
    stock.qty = 6

    shop.start_day()
    # Simulate a few seconds so customers spawn/move.
    for _ in range(180):
        shop.update(1 / 60)
    shop.draw(screen)
    pygame.image.save(screen, str(out_dir / "shop_view.png"))

    # 2) Pack opening / reveal
    app.switch_scene("packs")
    packs = app.scenes["packs"]
    if hasattr(packs, "open_pack"):
        packs.open_pack()
    for _ in range(40):
        packs.update(1 / 60)
    packs.draw(screen)
    pygame.image.save(screen, str(out_dir / "pack_open.png"))

    # 3) Battle view
    app.state.deck.quick_fill(app.state.collection)
    app.switch_scene("battle")
    battle = app.scenes["battle"]
    battle.on_enter()
    for _ in range(2):
        battle.update(1 / 60)
    battle.draw(screen)
    pygame.image.save(screen, str(out_dir / "battle_view.png"))

    print(f"Wrote screenshots to {out_dir.resolve()}")


if __name__ == "__main__":
    main()

