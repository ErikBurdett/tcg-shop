# Unified Gameplay Shell Refactor Plan

## Goal
Consolidate runtime UI to:
1. **Main Menu scene** on load/exit.
2. **Single gameplay scene (shop shell)** where all tabs, windows, gameplay, and overlays live.

This keeps the shop viewport centered while preserving drag/resize behavior, responsive layout, and low-latency UI updates.

## What changed in this branch
- `GameApp.switch_scene()` now routes gameplay scene keys to the unified `shop` shell and changes tabs there.
- Legacy top-left global scene tabs were reduced to only `Shop` and `Menu` for compatibility.
- Shop shell now suppresses legacy bottom day buttons (scene-level) and owns all controls.
- Bottom tab strip is now primary navigation on desktop.
- Responsive mobile breakpoint adds a hamburger menu (`☰ Menus`) to toggle tab buttons.
- Added top info chip bar (Money, Day, Cycle, XP, Staff) with hover tooltip details.

## Layout target (inspired by MMO/strategy UIs)
- **Top bar**: compact info + hover tooltips.
- **Center**: fixed focal gameplay viewport (shop).
- **Right side**: vertical panels (Ordering, Stocking, Inventory, etc.).
- **Bottom**: horizontal gameplay tabs.

## Next implementation steps
1. Standardize panel docking behavior and optional snap zones.
2. Add mobile touch hit-area tuning and long-press tooltips.
3. Move all "menu actions" (save/new/exit) into a single consistent modal.
4. Add perf telemetry counters per panel and drag frame budget.
5. Add regression tests for scene routing + tab routing.

## Performance notes
- Keep text rendering cached (`theme.render_text`).
- Avoid rebuilding button objects while dragging; keep fast rect-reflow path.
- Keep tooltip calculations O(number of visible controls).
- Route scene changes to tab switches to avoid scene reconstruction churn.


## PR packaging note
- Keep screenshot regeneration optional for local validation, but avoid committing regenerated PNGs when using PR tooling that rejects binary diffs.
