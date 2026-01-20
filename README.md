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

## Gameplay Loop
1. Run the shop day in the top-down scene.
2. Manage inventory and pricing in Manage.
3. Open boosters in Packs.
4. Build a 20-card deck in Deck.
5. Battle AI in Battle.
6. Save/load via Menu.

## Current Features
### Shop & Economy
- Place shop objects (shelves, counter, poster) on a grid.
- Run a shop day with customer traffic and sales.
- Dynamic pricing and shelf stocking (manual restock).
- Money, day counter, and sales summary.
- Customers path to shelves and counter, then exit.

### Inventory & Management
- Booster packs, decks, and singles tracked by rarity.
- Order boosters, decks, and singles (immediate delivery).
- Stock shelves from inventory, fill to capacity.
- Select shelves via list or by clicking the shelf tile.

### Cards & Packs
- Booster packs generate 5 cards with rarity distribution.
- Card collection and deck building (20-card deck rule, max 2 copies).
- Card assets with rarity-based backgrounds and borders.

### Battle
- Simple AI battle loop using deck lists.
- Turn-based flow and basic combat resolution.

### UX & Tools
- Unified single-screen UI with tabs (Shop, Packs, Deck, Manage, Battle).
- Resizable window and responsive UI layout.
- Moveable/resizable Manage panels.
- Dev console (money, packs, deckfill).
- Save/load game state.

## Missing / Incomplete
### Shop Management
- No tutorial or guided onboarding for new players.
- No staff upgrades, marketing, or store upgrades.
- No shop customization beyond basic placements.
- No constraints/validation for placement overlaps.

### Inventory & Management
- Pricing controls are not exposed in the unified Manage UI.
- Pending order delivery delay is not implemented (orders are instant).
- No auto-restock or demand forecasting tools.
- Shelf list lacks visual selection highlight in the list itself.

### Packs & Collection
- Pack opening lacks animations/FX and pack artwork.
- No collection UI with filters/sorting in the unified UI.
- No in-game card inspection (zoom/details).

### Battle
- Battle UI is minimal and not integrated into the unified screen.
- No rewards flow or campaign progression.
- Limited AI depth and difficulty scaling.

### UX/Polish
- No keybinds for manage actions.
- Limited audio/visual feedback for actions (ordering, stocking, sales).
- Accessibility settings (text size, contrast) not available.

## Feature Completion Checklist (Suggested)
- [ ] Integrate full Manage UI (pricing sliders, reorder queues, stock tools).
- [ ] Add clear shelf selection indicators and list highlighting.
- [ ] Add pack opening animation + card reveal FX.
- [ ] Add collection viewer with filters/sorting.
- [ ] Add battle rewards + progression loop back into shop.
- [ ] Add placement rules (no overlapping objects, clear walk paths).
- [ ] Add audio/visual feedback for key actions.

## Dev Console
Open with ` and enter commands:
- `money 500` (add money)
- `packs 3` (add boosters)
- `deckfill` (quick fill deck)

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
