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

# Keep this short (it’s rendered in the main menu side panel).
# Treat this like “last 2 commits” notes / release notes.
RECENT_UPDATES: list[str] = [
    "Shop view is now its own movable + resizable window.",
    "Shop rendering/input is clipped to that window (no accidental placements).",
]

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

# --- Customer pacing / performance safeguards ---
# Spawn interval ramps from START -> MIN over RAMP_DAYS (inclusive-ish).
CUSTOMER_SPAWN_INTERVAL_START = 7.0
CUSTOMER_SPAWN_INTERVAL_MIN = 4.2
CUSTOMER_SPAWN_RAMP_DAYS = 14

# Hard caps to keep gameplay calm + avoid update spikes.
MAX_CUSTOMERS_ACTIVE = 10
MAX_CUSTOMERS_SPAWNED_PER_DAY = 14
MAX_CUSTOMER_SPAWNS_PER_FRAME = 1

# If at cap or cannot spawn, delay the next attempt by this many seconds.
CUSTOMER_SPAWN_RETRY_DELAY = 0.75

# Visit pacing (dt-based; scaled by current tile size).
CUSTOMER_SPEED_TILES_PER_S = 1.4
CUSTOMER_BROWSE_TIME_RANGE = (0.6, 1.4)
CUSTOMER_PAY_TIME_RANGE = (0.25, 0.7)
