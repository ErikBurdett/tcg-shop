# TCG Shop Simulator (Pygame Prototype)

Top-down trading card shop sim with a full card game loop: run your shop, manage inventory and pricing, open packs, build a deck, and battle AI opponents.

## Requirements
- Python 3.11+
- Linux/WSL2

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Controls
- Mouse: UI interactions
- ESC: Back / pause
- F3: Toggle debug overlay
- ` (backtick): Toggle dev console
- SPACE: End turn (battle)
- Bottom-middle: Start/Stop day controls (global)

## Gameplay Loop
1. Start on the main menu and pick a save slot (Load or New Game).
2. Run the shop day in the top-down scene.
3. Manage inventory and pricing in Manage.
4. Open boosters in Packs.
5. Build a 20-card deck in Deck.
6. Battle AI in Battle.
7. Spend skill points and view modifiers in Skills.
7. Save via the unified Menu button.

## What’s New (recent changes)
- **Unified UI improvements**
  - **Tabs never overflow**: top nav wraps to multiple rows on small windows.
  - **Global Start/Stop Day**: pinned bottom-middle across screens via the base `Scene`.
  - **Draggable/resizable panels**: ordering/stocking/inventory/book/deck panels can be moved/resized.
  - **Shop in a window**: the shop playfield is inside a **movable + resizable Shop panel** (with a clipped viewport).
- **Order management**
  - Orders are **delivered ~30 seconds after purchase** (real-time), not “next day”.
  - Manage inventory shows an **Incoming (ETA)** queue.
- **Pricing + market**
  - More **MTG-like retail defaults** for boosters/decks/singles by rarity.
  - **Wholesale ordering** derived from retail (simple margin model).
  - You can **buy random singles** by rarity (adds a random card of that rarity).
- **Shelf listing**
  - Shelves can hold **specific listed card IDs** (not only “single_rare xN”).
  - In Manage, “List Selected Card” opens a **collection card book menu** where you pick a card and list it to the selected shelf.
  - Selecting a shelf now shows **its contents** (including listed cards summary) in the Inventory panel.
- **Visual**
  - Cards gain a subtle **rarity-colored edge glow** in key UI renders.
- **Simulation**
  - **Day/Night cycle**: ~300s day + ~60s night, with **pause/resume**.
  - **Autosave**: game auto-saves at the **start of every night**.
  - **Roaming staff**: visible staff actor auto-restocks low shelves (based on shelf contents) and gains XP/levels.
- **Progression + UI feedback**
  - **Player progression**: earn XP from **shop sales** and **battle wins**, level up, and gain **skill points**.
  - **Skills tab**: unlock skill nodes with prerequisites; modifiers are cached and applied to economy.
  - **Global tooltips + toasts**: hover UI for quick tips; key actions show non-blocking notifications.
- **Fixture economy**
  - Shelves/counters/posters must be **purchased** before they can be placed (existing placed fixtures remain owned on load).

## Asset Specs
### Global Pixel Sizes
- Window size: `1600x900` (resizable)
- Base resolution: `1600x900`
- Shop grid tile size: **dynamic** (default `48x48`, scales with the Shop window; clamped to ~`24`–`84` px)

### Card Art Sizes
- Card art target size: `64x64` in shop view
- Card art target size: `96x96` in pack reveal
- Card background size: `160x220` in pack reveal

### Shop Art Sizes
- Floor tiles: scaled to `48x48`
- Furniture sprites: source `16x16`, scaled to `48x48`
- Customer sprites: source `32x32`, scaled to `40x40` in shop

### Asset Structure & Naming
- Card art
  - `game/assets/tiny-creatures/Tiles/tile_####.png` (individual tiles)
  - `game/assets/dungeon-crawl-utumno.png` (tilesheet, 32x32 grid)
- Shop art
  - `game/assets/shop/tiles/floor_#.png` (floor tiles)
  - `game/assets/shop/tiles/customer_#.png` (customers)
  - `game/assets/shop/furniture.png` (16x16 furniture sheet)

## Feature Checklist
### Implemented
- [x] Shop grid placement (shelves, counter, poster)
- [x] Fixture purchase inventory (buy fixtures before placement)
- [x] Customer traffic and purchases
- [x] Roaming staff actor that auto-restocks shelves (with XP/level)
- [x] Inventory ordering and shelf stocking
- [x] Delayed delivery queue (real-time, ~30s)
- [x] Pricing controls in unified Manage UI
- [x] Buy random singles by rarity
- [x] List specific cards onto shelves for sale
- [x] Booster pack generation and collection
- [x] Deck build rules (20 cards, max 2 copies)
- [x] Battle flow with AI
- [x] Unified single-screen UI tabs
- [x] Responsive UI (tab wrapping) + draggable panels
- [x] Shop scene is contained in a movable/resizable window (clipped viewport)
- [x] Save/load system
- [x] Three named save slots (menu-driven)
- [x] Dev console commands
- [x] Player progression (XP/level/skill points)
- [x] Skill tree (20+ nodes, prerequisites, cached modifiers)
- [x] Sell price modifier applied consistently (UI + transactions)

### Not Implemented / Incomplete
- [ ] Sell flow UI (buylist/retail sliders, confirmations, receipts)
- [ ] Demand forecasting / smarter auto-restock policies (current: threshold-based staff restock)
- [ ] Pack opening FX and pack artwork
- [ ] Collection browser filters/sorting/search (rarity, name, owned, value)
- [ ] Deeper progression effects (more skills wired into simulation beyond pricing/XP/fixture discount)
- [ ] Placement rules / collision constraints
- [ ] Accessibility options (text size, contrast)
- [ ] Audio/visual feedback for key actions

## Card Sets
### Current Set: "Core Sprouts"
Each card is listed as: `Name — Cost / Attack / Health`

#### Commons (Sproutling)
- Sproutling 1 — 1 / 2 / 2
- Sproutling 2 — 1 / 1 / 2
- Sproutling 3 — 1 / 2 / 2
- Sproutling 4 — 1 / 1 / 2
- Sproutling 5 — 1 / 2 / 2
- Sproutling 6 — 1 / 1 / 2
- Sproutling 7 — 1 / 2 / 2
- Sproutling 8 — 1 / 1 / 2
- Sproutling 9 — 1 / 2 / 2
- Sproutling 10 — 1 / 1 / 2
- Sproutling 11 — 1 / 2 / 2
- Sproutling 12 — 1 / 1 / 2

#### Uncommons (River Guard)
- River Guard 1 — 2 / 3 / 3
- River Guard 2 — 2 / 2 / 3
- River Guard 3 — 2 / 3 / 3
- River Guard 4 — 2 / 2 / 3
- River Guard 5 — 2 / 3 / 3
- River Guard 6 — 2 / 2 / 3
- River Guard 7 — 2 / 3 / 3
- River Guard 8 — 2 / 2 / 3

#### Rares (Skyblade)
- Skyblade 1 — 3 / 4 / 4
- Skyblade 2 — 3 / 3 / 4
- Skyblade 3 — 3 / 4 / 4
- Skyblade 4 — 3 / 3 / 4
- Skyblade 5 — 3 / 4 / 4

#### Epics (Voidcaller)
- Voidcaller 1 — 4 / 5 / 5
- Voidcaller 2 — 4 / 4 / 5
- Voidcaller 3 — 4 / 5 / 5

#### Legendaries (Ancient Wyrm)
- Ancient Wyrm 1 — 5 / 6 / 6
- Ancient Wyrm 2 — 5 / 6 / 6

## Dev Console
Open with ` and enter commands:
- `money 500` (add money)
- `packs 3` (add boosters)
- `deckfill` (quick fill deck)

## UI / Documentation
- `graphics_overview.md`: rendering + asset pipeline reference
- `UI.md`: UI architecture, best practices, and UI roadmap
- `TCG_Sim_ OverView Roadmap.md`: higher-level feature roadmap
- `saves.md`: save slot system details
- `staff_xp_overview.md`: staff/player actor overview + XP system notes

## Tests
Run sanity checks:
```bash
python -m game.tests
```

## Project Structure
- `main.py` entry point
- `game/core/` engine loop, save/load, input
- `game/scenes/` UI scenes (shop, packs, deck, battle)
- `game/sim/` economy, inventory, shop layout
- `game/cards/` cards, packs, battle logic
- `game/assets/` sprites and asset loaders

## Contributing
- Use Python 3.11+
- Keep changes focused and add tests where possible
- Run `python -m game.tests` before submitting

## License
No license specified yet.
