from __future__ import annotations

from dataclasses import dataclass


WINDOW_SIZE = (1600, 900)
WINDOW_TITLE = "TCG Shop Simulator"
FPS = 60

BASE_RESOLUTION = (1600, 900)
TILE_SIZE = 48
SHOP_GRID = (20, 12)

# Day/night pacing (real-time seconds).
DAY_DURATION_SECONDS = 300.0
NIGHT_DURATION_SECONDS = 60.0

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
    # "Retail-ish" defaults (lowered for a more playable early game economy).
    # Note: wholesale ordering costs are a separate source of truth (supplier unit costs).
    booster: int = 4
    deck: int = 18
    single_common: int = 1
    single_uncommon: int = 2  # can't go below 1 without collapsing rarity pricing
    single_rare: int = 6
    single_epic: int = 12
    single_legendary: int = 28


DEFAULT_PRICES = Prices()
START_MONEY = 1400  # enough to buy a counter + shelf and still order early inventory
START_DAY = 1
START_PACKS = 3

# --- Pricing model separation ---
# Wholesale/supplier unit costs are a distinct source of truth from retail prices.
# Critical: player pricing changes (absolute or markup) must NOT change these supplier costs.
WHOLESALE_UNIT_COSTS: dict[str, int] = {
    "booster": 2,
    "deck": 11,
    "single_common": 1,
    "single_uncommon": 1,
    "single_rare": 4,
    "single_epic": 7,
    "single_legendary": 17,
}

# Market buy prices for random singles by rarity.
# Critical: these are independent of player retail pricing (player cannot "move the market").
MARKET_BUY_PRICES: dict[str, int] = {
    # Sealed products
    "booster": 2,
    "deck": 11,
    # Singles by rarity
    "common": 1,
    "uncommon": 2,
    "rare": 6,
    "epic": 12,
    "legendary": 28,
}

# Sell-back factor (player sells items/cards back to the market at a discount).
# Kept below 1.0 to prevent buy->sell loops from generating profit.
SELLBACK_FACTOR = 0.6

# --- Staff progression XP awards ---
# These govern the roaming staff/shopkeeper progression (shopkeeper_xp, shown under the sprite).
# Tune these for a rewarding loop; levels are derived from total XP (see staff XP module).
XP_PER_SALE_DOLLAR = 2.0
XP_PER_RESTOCK_ITEM = 3.0
XP_PER_PACK_OPENED = 12

# Optional multipliers for single-card sales/restocks based on rarity.
STAFF_XP_SINGLE_RARITY_MULT: dict[str, float] = {
    "common": 1.0,
    "uncommon": 1.15,
    "rare": 1.4,
    "epic": 1.8,
    "legendary": 2.4,
}

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
