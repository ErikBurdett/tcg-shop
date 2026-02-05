# Save Slots & Persistence

This project supports **3 named save slots** stored on disk in the user’s home directory.

## Where saves live

Saves are written to:
- `~/.tcg_shop/`

Files:
- `save_slot_1.json`
- `save_slot_2.json`
- `save_slot_3.json`
- `slots.json` (slot name metadata)

Legacy compatibility:
- Older builds used a single `savegame.json`. On startup, if it exists and slot 1 is empty, it is migrated into **slot 1**.

## What is stored

Each `save_slot_#.json` is a JSON dump of `GameState` plus a couple of extra metadata keys:
- **`slot_name`**: human-friendly name for the slot
- **`saved_at`**: unix timestamp when the slot was written

Game state includes:
- money, day, time_seconds
- prices
- inventory + pending orders
- collection + deck
- shop layout + shelf stocks (including any listed card IDs)
- last day summary

## How saving works in code

- `game/core/save.py` contains `SaveManager` and `SaveSlotInfo`.
- `GameApp` tracks the currently active slot in `self.active_slot`.
- `GameApp.save_game()` writes `self.state` into `self.active_slot`.
- `GameApp.load_game_slot(slot_id)` sets `active_slot` and loads that slot into `GameState`.

## UI behavior

On launch:
- The game starts in the **Main Menu** scene.
- You can select a slot and choose:
  - **Load** (only enabled if the slot has a save)
  - **New Game** (creates a fresh state and writes it to that slot)
  - **Rename** (type a custom slot name; Enter commits, Esc cancels)
  - **Delete** (removes the slot save file)

In-game:
- The unified **Menu** button contains **Save Game**, **New Game**, and **Exit to Menu**.

## Notes / best practices

- Save files are intentionally simple JSON for iteration speed.
- If you add new fields to `GameState` or other persisted structures, ensure:
  - `to_dict()` includes them
  - `from_dict()` uses safe defaults (`data.get(...)`) to preserve backward compatibility

