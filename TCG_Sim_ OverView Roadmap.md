# TCG Sim - Python

## 1) Project overview (what it is and how it works today)

TCG Shop Simulator is a Pygame prototype that combines two core loops: a shop/economy loop and a TCG loop (packs → collection/deck → battle AI). The README describes this loop explicitly, plus the tabbed single‑screen UX (Shop / Packs / Deck / Manage / Battle) and a checklist of implemented vs. missing features.

Key implemented loops (from docs + code):

- Shop day simulation : Customers spawn and walk through a simple flow (shelf → counter → exit). Purchases decrement shelf stock and add cash + revenue summaries, then the day ends and the game is saved.

- Inventory / management : There’s an explicit Manage scene for pricing and re‑ordering as a separate UI, and a Manage tab in the shop scene for shelf stocking and ordering (with some overlap). The Manage scene uses pending_orders (applied later), while the Shop scene applies orders immediately, which is an important inconsistency to resolve in the next iteration.

- Card system : Cards are currently hardcoded in card_defs.py (common/uncommon/rare/etc. lists), and pack opening uses a fixed rarity distribution + deterministic 3 common + 1 uncommon + 1 rare+ slot (with RNG).

- Battle loop : Turn‑based battle with mana curve, minions, simple AI, and win rewards (money + booster). The battle rules are in game/cards/battle.py and the UI is in game/scenes/battle_scene.py .

---

## 2) Architecture and module boundaries (full‑stack lens)

The project already exhibits a separation of concerns that can be hardened into clear layers:

### ✅ Simulation / domain layer (logic, deterministic)

- Economy decision logic is in game/sim/economy.py ( daily_customer_count , choose_purchase ). This is pure logic and should remain so for testability and balancing.

- Battle rules live in game/cards/battle.py and are well‑suited to become a pure “reducer” with event logs for replays/AI. Currently it mutates state directly without event logging.

- Cards + decks use CardDef and deck rules (20 cards, max 2 copies) in game/cards/deck.py and card_defs.py . This is deterministic and already easy to unit test.

### ✅ Application / orchestration layer (game state, flow, save)

- game/core/app.py owns the GameState , transitions, saves, and applies pending orders at the start of the day.

### ✅ Presentation / UI layer (Pygame)

- game/scenes/* render UI and call simulation actions. For example, the ShopScene handles object placement and shelf stocking UI (drag + resize panels, tab buttons, etc.).

Best‑practice next step: formalize pure simulation for the shop and battle loops (side‑effect free), while UI layers just render and dispatch events. This will make balancing, AI, and tests much easier.

---

## 3) Current development state (where it is right now)

Based on the README feature checklist and code implementation, the project is at an early vertical‑slice / prototype stage :

What’s implemented (confirmed):

- Shop placement, customers, pricing & ordering (in Manage scene), packs, deck rules, battle flow, single‑screen UI, save/load, dev console.

What’s flagged as missing (confirmed):

- Pricing controls in unified Manage UI (still in separate ManageScene).

- Delayed order delivery (orders are instant).

- Auto‑restock / demand forecasting.

- Pack opening FX + pack art.

- Collection browser filtering/sorting.

- Battle rewards + progression loop.

- Placement rules/collision constraints.

- Accessibility and feedback polish.

Evidence in code:

- Orders are instant or next‑tick : ShopScene applies orders immediately to inventory; ManageScene adds pending_orders that are applied at day start, but still no delivery delay model.

- Placement lacks collision/validation : ShopLayout doesn’t check occupancy or walkability; it just appends an object if in bounds.

Summary : The core loops are playable enough to validate fun, but systems are first‑pass and mostly hardcoded . That’s the perfect time to harden simulation logic, move content to data files, and add UX + progression hooks.

---

## 4) Roadmap (phased, shippable slices)

### Phase 1 — Hardening the vertical slice (Now)

Goal: Make current loops reliable and testable.

- Placement validation & occupancy map Add grid occupancy checks in ShopLayout.place to prevent overlaps and ensure walkable tiles.

- Delayed orders (delivery queue) Convert InventoryOrder into a model with arrival_day so orders arrive in future days. Right now, orders are applied immediately or on day start without delay.

- Unified pricing controls in Manage tab Pricing is currently in ManageScene , not the ShopScene Manage tab. Merge or embed pricing controls for UX consistency.

- Battle UI cohesion Keep battles in the unified UI or enhance with a cohesive “battle pane” to match the project’s single‑screen UX goal.

---

### Phase 2 — Data‑driven content + progression

Goal: Make content extensible without touching code.

- Data‑driven card sets Today, cards are hardcoded in game/cards/card_defs.py . Move to JSON/YAML in a content/sets/* folder, with validation hooks. (More on this below.)

- Collection UX Add filtering, sorting, and a card inspect/zoom overlay. The README explicitly calls this missing.

- Progression loop Add simple rewards (battle → currency → shop upgrades). Currently only wins grant money + boosters, and no meta progression exists.

---

### Phase 3 — Smarter simulation & AI

Goal: Make the shop and battles “strategically deep”.

- Demand model + price elasticity choose_purchase already weights purchase by price (very simple). Replace with an explicit demand function using price elasticity and day‑based demand shifts.

- Customer archetypes Add customers with distinct preferences (budget vs collector vs competitive).

- AI difficulty scaling Move from “simple greedy” to a heuristic + 1‑ply lookahead engine in battle logic; this is natural if battle is event‑sourced.

---

### Phase 4 — Production polish

Goal: A polished game rather than a prototype.

- Animation system, FX pipeline, camera/viewport, texture packing, audio, accessibility controls. This is called out in graphics_overview.md as missing for a fully immersive game.

---

## 5) How to extend card sets + stats (current code and best‑practice upgrades)

### ✅ Current implementation (what you must edit now)

Cards are hardcoded in Python:

- game/cards/card_defs.py defines card IDs, names, rarities, stats.

Pack generation pulls by rarity:

- open_booster pulls 3 commons, 1 uncommon, 1 rare+ by rarity roll.

Art mapping is in code:

- Asset mappings for card art are coded in game/assets/__init__.py (tile numbers + tilesheet coords).

### ✅ Best‑practice approach (data‑driven sets)

Move to data files so designers can ship new sets without editing Python:

```
content/
  sets/
    core_sprouts/
      cards.json
      pack.json
      art.json
```

cards.json example:

```
{
"set_id":"core_sprouts",
"cards":[
{"id":"core_sprouts:sproutling_01","name":"Sproutling 1","rarity":"common","cost":1,"attack":2,"health":2}
]
}
```

Why this matters:

- Content updates don’t require code changes.

- You can ship balance patches without touching logic.

- You can enable mod packs by loading multiple set folders.

Validation best practices:

- Enforce unique IDs and rarity counts.

- Validate art mappings (missing sprites).

- Validate stat bounds.

---

## 6) Shop simulation improvements (specific, high‑impact)

Today, customer selection is a simple weighted choice by price and availability; there’s no stockout or elasticity model beyond a weighted random pick.

### Suggested expansions

1) Demand + price elasticity

Build a demand function:

- demand = base * (price / ref_price) ^ -elasticity

- Use it to stochastically simulate “willingness to buy”.

2) Customer archetypes

- Budget: prefers low price

- Collector: prefers high rarity singles

- Competitive: prefers decks

3) Stockout behavior

If shelf empty → leave or substitute

4) Inventory planning

Add reorder points + forecast UI.

---

## 7) Battle system improvements

Currently, battle rules are simple and stateful (mutating BattleState ).

### Best‑practice improvement: Event‑sourced reducer

Convert to:

```
(state, action) -> (new_state, [events])
```

Benefits

- Replayable combats.

- UI can animate events without guessing rules.

- AI can simulate actions for evaluation.

AI improvements:

- Heuristic scoring of board state.

- 1‑ply lookahead (simulate next move).

- Difficulty scaling by evaluation depth or reduced randomness.

---

## 8) Asset pipeline & creation guide (based on repo docs)

### Canonical sizes (from README + graphics_overview)

- Window: 1600×900 (base).

- Shop grid tile: 48×48 .

- Card art: 64×64 (shop view), 96×96 (pack reveal).

- Pack card background: 160×220 .

- Furniture: 16×16 source , scaled to 48×48.

- Customers: 32×32 source , scaled to 40×40.

### Asset paths used today

- game/assets/tiny-creatures/Tiles/tile_####.png

- game/assets/dungeon-crawl-utumno.png

- game/assets/shop/tiles/floor_#.png

- game/assets/shop/tiles/customer_#.png

- game/assets/shop/furniture.png

### Asset best practices (from docs)

- Power‑of‑two sprite sizes (16/32/64)

- No anti‑aliasing

- PNG with transparency

- Pre‑scale and cache (don’t scale per frame)

- Consistent tile sizes per sheet

---

## 9) AI tools for asset generation (list + example prompts)

### Recommended tool list

Generation

- OpenAI Image / ChatGPT image generation

- Midjourney

- Stable Diffusion (SDXL)

Pixel conversion / cleanup

- Aseprite (best all‑around for pixel work)

- LibreSprite / Piskel (free alternatives)

- Krita / Photoshop (cleanup + masking)

Workflow automation

- ComfyUI (Stable Diffusion workflow engine)

- ImageMagick (batch resize, palette reduce)

- Python + Pillow (batch processing)

---

### Example prompts (start with clean concepts)

A) Character art (clean source)

> “fantasy creature character concept, centered, full body, clear silhouette, minimal background, simple shapes, high contrast edges, front‑facing, no text, no watermark”

B) Pixel‑specific prompt (if using pixel models)

> “pixel art, 32x32 sprite, top‑down RPG style, limited palette, crisp edges, no anti‑aliasing, transparent background, idle pose”

C) Tileable environment prompt

> “pixel art dungeon floor tiles, seamless tileable pattern, 16x16 tileset, limited palette, top‑down, no perspective”

---

## 10) Converting AI art into perfect pixel assets (recommended pipeline)

### Character sprites (transparent)

- Generate character concept on flat background.

- Remove background (Photoshop/Krita/Aseprite).

- Downscale with nearest neighbor to 32×32 (or 16×16 source).

- Palette reduce to 16–32 colors.

- Hand‑clean edges in Aseprite.

- Build sprite sheet with directional frames.

### Environment / tiles

- Generate high‑res tile concept.

- Crop/tiling check.

- Resize to 16×16 with nearest neighbor.

- Palette reduce and edge clean.

- Export with consistent naming ( tile_####.png ).

---

## 11) Gaps & best‑practice improvements to prioritize

Most impactful next upgrades:

- Delayed orders + supplier pipeline (pending_orders with arrival day).

- Unified pricing controls inside ShopScene Manage tab.

- Battle rewards / progression loop (tie battle to shop).

These align directly with the repo’s “not implemented” list and will create the most “sticky” progression loop.

---

## Sources & commands used

Files referenced:

- README.md

- graphics_overview.md

- game/cards/card_defs.py

- game/cards/pack.py

- game/cards/battle.py

- game/cards/deck.py

- game/cards/collection.py

- game/sim/economy.py

- game/sim/shop.py

- game/sim/inventory.py

- game/scenes/shop_scene.py

- game/scenes/manage_scene.py

- game/scenes/battle_scene.py

- game/core/app.py

- game/assets/__init__.py

Commands run:

- sed -n '1,200p' README.md

- sed -n '1,200p' graphics_overview.md

- sed -n '1,200p' game/cards/card_defs.py

- sed -n '1,200p' game/cards/pack.py

- sed -n '1,200p' game/sim/shop.py

- sed -n '1,200p' game/sim/economy.py

- sed -n '1,200p' game/sim/inventory.py

- sed -n '1,200p' game/scenes/shop_scene.py

- sed -n '200,400p' game/scenes/shop_scene.py

- sed -n '400,800p' game/scenes/shop_scene.py

- sed -n '1,200p' game/scenes/manage_scene.py

- sed -n '200,400p' game/scenes/manage_scene.py

- sed -n '1,200p' game/scenes/battle_scene.py

- sed -n '1,200p' game/cards/battle.py

- sed -n '1,200p' game/cards/deck.py

- sed -n '1,200p' game/cards/collection.py

- sed -n '1,200p' game/core/app.py

- sed -n '200,400p' game/core/app.py

- sed -n '1,200p' game/assets/__init__.py

- sed -n '200,400p' game/assets/__init__.py

---

If you want, I can next produce concrete data schemas (cards → packs → shop SKUs) and a validation/loader layer (with tests) tailored to this repo’s structure.
