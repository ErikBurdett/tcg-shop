# Staff / Player Character Overview (Roaming Auto‑Stocking + XP)

This project includes a visible “staff” actor (player avatar or NPC) that roams the shop during an active **Day** and automatically restocks shelves.

## Where it lives (code)
- **Simulation/state machine**: `game/sim/actors.py`
  - `Staff` dataclass
  - `update_staff()` state machine
  - restock selection (`choose_restock_plan`) + application (`apply_restock`)
- **Integration + rendering**: `game/scenes/shop_scene.py`
  - Update happens in `_update_day(dt)` (only during the Day phase)
  - Render happens in `_draw_player(surface)` and respects the shop panel’s clipped viewport

## Present features (implemented now)

### Roaming + restocking behavior
- **Active during Day**: the staff runs only when the shop cycle is in **Day** and not paused.
- **Throttled scanning**: shelves are scanned on a cooldown (default ~0.8s) to avoid per-frame O(N) work.
- **Task selection based on shelf contents**:
  - If a shelf’s `product` is `booster` → restock boosters
  - If `deck` → restock decks
  - If `single_<rarity>` → restock that rarity
  - If the shelf has listed card IDs (`ShelfStock.cards`) → restock that same card id from the collection (respecting deck commitments)
- **Physical movement**:
  - staff moves in **tile-space**, dt-based
  - computes a BFS path to a walkable tile adjacent to the shelf
  - path is cached and only recomputed when the target changes
- **Stock action delay**:
  - after reaching the shelf-adjacent tile, staff waits a short `stock_time` before applying stock changes

### XP + level (minimal progression)
- **XP**: staff gains XP from **sales**, **restocking**, and **opening packs**.
- **Level**: derived from XP (currently: \(level = 1 + \lfloor xp / 100 \rfloor\)).
- **Awarding is centralized** in `game/sim/staff_xp.py` (pure award function + config-tunable rates).
- **Persistence**: staff XP is saved in `GameState.shopkeeper_xp` so it survives save/load reliably.

### Rendering (viewport-safe)
- The staff sprite is drawn inside the shop panel clip, using the same world→screen transform as customers.
- Under the feet:
  - a small **XP bar**
  - a cached **“S Lv N”** label (only re-rendered when level changes)

### Debug visuals
- When the debug overlay is enabled (F3), the staff’s **path/target** is drawn in the shop viewport.

## What “restock threshold” means
The staff considers a shelf “needs restock” when its quantity is below a threshold fraction of `max_qty`.
- Current default in code: `restock_threshold_ratio = 0.999` (i.e., restock whenever below “full”)
- Example: `max_qty = 10` → restock when qty ≤ 9

## Current limitations (intentional for now)
- Staff sprite currently reuses an existing sprite as a placeholder.
- Staff does not do “patrol wandering” when no shelves need restock (it remains idle).
- Restock policy is simple threshold-based (no demand forecasting yet).
- Pathing assumes 1×1 objects and treats all placed objects as blocked tiles.

## Eventual features (planned / roadmap ideas)

### Better progression loop
- **Skill upgrades**:
  - faster stocking time
  - larger restock batch size
  - smarter shelf prioritization (profit-per-minute)
- **Staff perks**:
  - auto-ordering when inventory is low
  - restock multiple shelves in a route (batch planning)
- **XP sources**:
  - restocking, completing a full shelf, successful sales volume milestones

### Smarter restock/demand forecasting
- Track sales per product over time to compute demand
- Restock in anticipation (not only below-threshold)
- Optional “restock rules” per shelf (min qty, max qty, priority)

### Better visuals
- Dedicated staff/player sprite sheet (idle/walk/stock animation)
- Stocking animation (short arm/box movement) synced to stock timer
- Small UI hints (tooltip when stocking, highlight target shelf)

