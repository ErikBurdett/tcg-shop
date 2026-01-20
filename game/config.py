from __future__ import annotations

from dataclasses import dataclass


WINDOW_SIZE = (1600, 900)
WINDOW_TITLE = "TCG Shop Simulator"
FPS = 60

BASE_RESOLUTION = (1600, 900)
TILE_SIZE = 48
SHOP_GRID = (20, 12)

SAVE_DIR = ".tcg_shop"
SAVE_FILE = "savegame.json"

SEED = 1337


@dataclass
class Prices:
    booster: int = 7
    deck: int = 15
    single_common: int = 1
    single_uncommon: int = 2
    single_rare: int = 4
    single_epic: int = 7
    single_legendary: int = 12


DEFAULT_PRICES = Prices()
START_MONEY = 2000
START_DAY = 1
START_PACKS = 3
