# Asset Manifest (runtime-used images)

This manifest enumerates **every PNG under `game/assets/`**, and flags which ones are **actually loaded/used at runtime** by the current code.

It’s intended as a “source of truth” for generating replacement art with **exact dimensions** while preserving **paths and filenames**.

## 1) Asset Specs (from `README.md`)

### Global
- **Window/Base**: `1600×900` (resizable)
- **Shop grid tile size**: **dynamic**, default `48×48`, clamped to ~`24`–`84` px (shop viewport window scaling)

### Cards
- **Card sprite target sizes**:
  - `64×64` (shop views)
  - `96×96` (pack reveal)
  - smaller variants exist (e.g. battle uses ~`48×48`, `56×56`)
- **Procedural card background sizes**:
  - `160×220` (pack reveal)
  - additional sizes are generated on demand (see “Card background” section)

### Shop
- **Floor tiles**: scaled at runtime to `tile_px×tile_px` (default `48×48`)
- **Furniture**: **source cell is `16×16`**, scaled to `tile_px×tile_px`
- **Customers**: **source `32×32`**, scaled at runtime (e.g. `40×40` or derived from `tile_px`)

---

## 2) Code usage (what loads at runtime)

### Card assets (`game/assets/__init__.py`)
- **Tilesheet**: `game/assets/dungeon-crawl-utumno.png`
  - treated as **32×32 cells**, **64 cols × 48 rows** (expected by code; confirmed by file dims below)
- **Tiny Creatures tiles**: `game/assets/tiny-creatures/Tiles/tile_####.png`
  - Current runtime-used tile numbers:
    - River Guard (uncommon): **1–8**
    - Sproutling (common): **37–48**

### Shop assets (`game/assets/shop/__init__.py`)
- **Floor tiles loaded**: `game/assets/shop/tiles/floor_0.png` … `floor_3.png`
- **Customer sprites loaded**: `game/assets/shop/tiles/customer_0.png` … `customer_7.png`
- **Furniture sheet**: `game/assets/shop/furniture.png`
  - **must remain** `128×64` with **16×16 cells** (8×4 grid)

---

## Replacement targets (generated in this run)

This table is the **source of truth** for automated validation via `tools/verify_assets.py`.

| asset | size | has_alpha |
|---|---:|:---:|
| `game/assets/shop/tiles/floor_0.png` | 48×48 | true |
| `game/assets/shop/tiles/floor_1.png` | 48×48 | true |
| `game/assets/shop/tiles/floor_2.png` | 48×48 | true |
| `game/assets/shop/tiles/floor_3.png` | 48×48 | true |
| `game/assets/shop/tiles/customer_0.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_1.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_2.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_3.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_4.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_5.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_6.png` | 32×32 | true |
| `game/assets/shop/tiles/customer_7.png` | 32×32 | true |
| `game/assets/shop/furniture.png` | 128×64 | true |
| `game/assets/tiny-creatures/Tiles/tile_0001.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0002.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0003.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0004.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0005.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0006.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0007.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0008.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0037.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0038.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0039.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0040.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0041.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0042.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0043.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0044.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0045.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0046.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0047.png` | 32×32 | true |
| `game/assets/tiny-creatures/Tiles/tile_0048.png` | 32×32 | true |
| `game/assets/card_background_160x220.png` | 160×220 | true |

---

## 3) Runtime-used image manifest (34 PNGs)

| asset | size | has_alpha | runtime usage |
|---|---:|:---:|---|
| `game/assets/dungeon-crawl-utumno.png` | 2048×1536 | true | Card sheet (32×32 cells, 64×48 grid) |
| `game/assets/shop/furniture.png` | 128×64 | true | Furniture sheet (16×16 cells, 8×4 grid) |
| `game/assets/shop/tiles/floor_0.png` | 48×48 | true | Shop floor tile (scaled at runtime) |
| `game/assets/shop/tiles/floor_1.png` | 48×48 | true | Shop floor tile (scaled at runtime) |
| `game/assets/shop/tiles/floor_2.png` | 48×48 | true | Shop floor tile (scaled at runtime) |
| `game/assets/shop/tiles/floor_3.png` | 48×48 | true | Shop floor tile (scaled at runtime) |
| `game/assets/shop/tiles/customer_0.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_1.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_2.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_3.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_4.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_5.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_6.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/shop/tiles/customer_7.png` | 32×32 | true | Customer/staff sprite (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0001.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0002.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0003.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0004.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0005.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0006.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0007.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0008.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0037.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0038.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0039.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0040.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0041.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0042.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0043.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0044.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0045.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0046.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0047.png` | 32×32 | true | Card art tile (scaled at runtime) |
| `game/assets/tiny-creatures/Tiles/tile_0048.png` | 32×32 | true | Card art tile (scaled at runtime) |

---

## 4) Mismatches vs documentation (and important notes)

- **Shop floor tiles are source `48×48`**
  - Runtime scales floor tiles to `tile_px×tile_px` (default `48×48`, dynamic), so `48×48` is a good “native” source size.
- **Tiny Creature card tiles are now `32×32` with alpha**
  - Code loads these and scales to the various card target sizes, so a `32×32` master with transparent background works well.
- **Furniture sheet layout is fixed**
  - Must remain `128×64` with **16×16** cells, **8×4** grid. Do not change dimensions or grid.

---

## 5) To-generate list (replacement art targets)

### Floor tiles (runtime used)
- `game/assets/shop/tiles/floor_0.png` … `floor_3.png`
  - **Source**: `48×48`, **alpha required** (true)
  - **Runtime scale**: `tile_px×tile_px` (default `48×48`, dynamic)

### Customers / staff (runtime used)
- `game/assets/shop/tiles/customer_0.png` … `customer_7.png`
  - **Source**: `32×32`, **alpha required** (true)
  - **Runtime scale**: varies (typically ~`40×40`, derived from `tile_px`)

### Furniture sheet (runtime used)
- `game/assets/shop/furniture.png`
  - **Exact**: `128×64`, alpha required (true)
  - **Cell size**: `16×16`
  - **Grid**: 8 columns × 4 rows
  - **Cells used by code** (col,row):
    - `poster`: `(0,2)`
    - `shelf_alt`: `(1,1)`
    - `shelf`: `(1,2)`
    - `counter`: `(7,0)`
    - (additional mappings exist; keep the whole sheet consistent)

### Card art tiles (runtime used)

#### Tiny Creatures individual tiles
- Location: `game/assets/tiny-creatures/Tiles/tile_####.png`
- Replacement target (for runtime-used subset): **`32×32`**, **alpha required** (true)
- Runtime-used subset (current card set):
  - `tile_0001.png` … `tile_0008.png`
  - `tile_0037.png` … `tile_0048.png`

#### Dungeon Crawl Utumno sheet
- `game/assets/dungeon-crawl-utumno.png`
  - **Exact**: `2048×1536`, alpha required (true)
  - **Cell size**: `32×32`
  - **Grid**: `64×48`
  - Used via fixed (col,row) mapping in `CardAssetManager.DUNGEON_CRAWL_MAPPING`

### Card background (procedural; no image file)
Card backgrounds are generated procedurally by:
- `game/assets/__init__.py` → `CardAssetManager.create_card_background(rarity, size)`

Sizes currently generated by runtime usage include:
- `160×220` (pack reveal: `PackOpenScene`)
- `120×160` (shop packs panel: `ShopScene`)
- `56×56` (card-book icon: `ShopScene`)
- battle card rect sizes: `120×70` (hand) and `120×80` (minions) (`BattleScene`)

If you want file-based backgrounds, that would be a **new feature** (currently none are loaded from disk).

This repo also includes a **reference** background image (not currently loaded by code):
- `game/assets/card_background_160x220.png` (160×220)

---

## 6) Full PNG inventory under `game/assets/` (grouped)

### Top-level
- `game/assets/dungeon-crawl-utumno.png` — `2048×1536` — alpha: true — **runtime used**
- `game/assets/card_background_160x220.png` — `160×220` — alpha: true — reference (not runtime loaded)

### Shop
- `game/assets/shop/furniture.png` — `128×64` — alpha: true — **runtime used**
- `game/assets/shop/tiles/floor_0.png` — `48×48` — alpha: true — **runtime used**
- `game/assets/shop/tiles/floor_1.png` — `48×48` — alpha: true — **runtime used**
- `game/assets/shop/tiles/floor_2.png` — `48×48` — alpha: true — **runtime used**
- `game/assets/shop/tiles/floor_3.png` — `48×48` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_0.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_1.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_2.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_3.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_4.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_5.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_6.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/customer_7.png` — `32×32` — alpha: true — **runtime used**
- `game/assets/shop/tiles/decor_0.png` — `32×32` — alpha: true — unused
- `game/assets/shop/tiles/decor_1.png` — `32×32` — alpha: true — unused
- `game/assets/shop/tiles/wall_0.png` — `32×32` — alpha: true — unused
- `game/assets/shop/tiles/wall_1.png` — `32×32` — alpha: true — unused
- `game/assets/shop/tiles/wall_2.png` — `32×32` — alpha: true — unused

### Tiny Creatures pack

#### Examples (unused at runtime)
- `game/assets/tiny-creatures/Examples/tiny_animalsanctuary.png` — `800×450` — alpha: true — unused
- `game/assets/tiny-creatures/Examples/tiny_fishing.png` — `800×450` — alpha: true — unused
- `game/assets/tiny-creatures/Examples/tiny_rpg.png` — `800×450` — alpha: true — unused
- `game/assets/tiny-creatures/Examples/tiny_whowouldwin.png` — `800×450` — alpha: true — unused

#### Preview / tilemaps (unused at runtime)
- `game/assets/tiny-creatures/Preview.png` — `640×800` — alpha: false — unused
- `game/assets/tiny-creatures/Tilemap/Kenney_tiny_dungeon.png` — `203×186` — alpha: false — unused
- `game/assets/tiny-creatures/Tilemap/tilemap.png` — `170×306` — alpha: true — unused
- `game/assets/tiny-creatures/Tilemap/tilemap_packed.png` — `160×288` — alpha: false — unused

#### Individual tiles (180 PNGs; only subset used at runtime)
- `game/assets/tiny-creatures/Tiles/tile_0001.png` … `tile_0180.png`
  - Mixed: some tiles may be regenerated; verify runtime-used subset via section 3 / 5
  - Runtime-used subset listed in section 3 / 5

