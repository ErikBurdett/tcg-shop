from __future__ import annotations

from dataclasses import dataclass


WINDOW_SIZE = (1600, 900)
WINDOW_TITLE = "TCG Shop Simulator"
FPS = 60

BASE_RESOLUTION = (1600, 900)
TILE_SIZE = 48
SHOP_GRID = (20, 12)

SAVE_DIR = ".tcg_shop"
# Legacy single-save filename (pre-save-slots).
SAVE_FILE = "savegame.json"
SAVE_SLOTS = 3
SAVE_SLOT_TEMPLATE = "save_slot_{slot}.json"
SAVE_META_FILE = "slots.json"

# Shown on the main menu. Update this to your repo URL.
PROJECT_URL = "https://github.com/ErikBurdett/tcg-shop"

SEED = 1337


@dataclass
class Prices:
    # "Retail-ish" defaults inspired by real TCG shop pricing (MTG-like).
    booster: int = 6
    deck: int = 25
    single_common: int = 1
    single_uncommon: int = 2
    single_rare: int = 8
    single_epic: int = 18
    single_legendary: int = 40


DEFAULT_PRICES = Prices()
START_MONEY = 2000
START_DAY = 1
START_PACKS = 3
