## UI responsiveness fixes (snappy drag/resize)

This document describes the changes implemented to reduce input latency and stabilize frame time during UI interactions (especially dragging/resizing windows and the Shop viewport window).

### Summary of symptoms
- Reported FPS was ~60+, but **dragging/resizing felt laggy/choppy**.
- This is typical of **frame-time spikes** (input is sampled each frame, but long draws make the cursor “feel behind”), and/or **event propagation doing extra work while dragging**.

---

## What we added (instrumentation & diagnosis)

### Debug overlay improvements
Files:
- `game/core/debug_overlay.py`
- `game/core/app.py`
- `game/core/scene.py`

Overlay now shows:
- **FPS**
- **dt (ms)**
- **input time (ms)** + event count
- **update time (ms)**
- **draw time (ms)**
- **draw calls** (instrumented by monkey-patching `pygame.draw.*` only while enabled)
- **text cache hit/miss** (per frame)
- **per-scene debug lines** (via `Scene.debug_lines()`)

Why this matters:
- “FPS looks fine” can hide input latency. The overlay exposes when **draw** or **input** spikes during drags.

### Drag latency metrics (ShopScene)
File:
- `game/scenes/shop_scene.py`

While dragging, we track the distance between:
- the **expected** window top-left from `mouse - drag_offset`, and
- the **actual** clamped/applied window top-left.

Displayed as:
- `Drag(<target>) latency: avg Xpx | max Ypx`

This is a practical “how close is the window to the cursor?” metric.

---

## Input smoothness fixes (pointer capture, no click-through)

### Pointer capture & event propagation rules
File:
- `game/scenes/shop_scene.py`

Change:
- When a drag/resize is active (`_drag_target` or `_resize_target` is set):
  - The scene **returns early** from `handle_event()` (except it still processes mouse-up to release capture).
  - This prevents hover/scroll/click handlers from running under the cursor while dragging.

Effect:
- Dragging and resizing now track the cursor consistently without “UI fighting” underneath.
- Prevents regressions where overlapping windows cause hidden buttons/lists to also react.

### Per-frame polling (already correct)
ShopScene already updates drag/resize using `pygame.mouse.get_pos()` every frame in `update()` via `_apply_drag_resize()`, which avoids dependence on MOUSEMOTION event rate/coalescing.

---

## Rendering performance fixes (avoid expensive work during drag/resize)

### Text rendering cache (no per-frame font.render for common UI)
Files:
- `game/ui/text_cache.py` (new)
- `game/ui/theme.py`
- `game/ui/widgets.py`

Change:
- Introduced `TextCache` (LRU) keyed by `(font_id, text, color)`.
- `Theme.render_text(...)` uses the cache.
- Core widgets now use cached text:
  - `Button.draw`
  - `Panel.draw`
  - `Label.draw`
  - `ScrollList.draw`
  - (tooltips are now centralized in `TooltipManager`, which caches rendered tooltip surfaces)

Effect:
- Dramatically reduces per-frame `font.render(...)` work for repeated UI labels (buttons, panel titles, list items).
- Debug overlay reports **cache hits/misses per frame** so you can see if a view is re-rendering too much text.

### Shop window caching during drag/resize (snapshot + throttled preview)
File:
- `game/scenes/shop_scene.py`

Change:
- While the Shop window is being dragged/resized:
  - The shop content is drawn using a **cached snapshot** of the shop window surface.
  - During resize, the snapshot is scaled to the new size as a **throttled preview** (~20 Hz) to reduce CPU load.
  - On mouse release, normal rendering resumes (and existing logic rebuilds the floor/tile scale once).

Effect:
- Greatly reduces draw spikes while moving/resizing the shop viewport.
- Makes the interaction feel “snappy” because the heavy shop rendering path (grid/objects/customers/status) is skipped during the drag.

Trade-off:
- While actively dragging/resizing the Shop window, the shop view can appear “frozen” (snapshot) even though simulation continues. This is intentional for responsiveness and stable frame time.

---

## Event dispatch & hit testing notes

The key improvement here is capture/early-return while dragging, which avoids:
- scanning/handling many widgets per event,
- hover updates causing extra redraw work while the user is just moving a window.

If further optimization is needed later, the next step would be a centralized “window manager” with:
- explicit z-order,
- routing events to the top-most window under cursor,
- per-window cached surfaces.

---

## Tests / verification

### Automated smoke tests
File:
- `game/tests.py`

Added/updated tests:
- `test_debug_overlay_toggle_smoke()`:
  - Enables/disables overlay safely (headless dummy video driver)
  - Verifies `pygame.draw` instrumentation increments draw calls
- `test_text_cache_lru_and_counters()`:
  - Verifies LRU eviction behavior and hit/miss counters

### Manual QA
See `PERF.md` for a focused checklist (drag rapidly, resize rapidly, drag while customers move, verify overlay metrics).

---

## Remaining known hotspots / next steps

If the overlay shows draw spikes even after these changes, likely culprits are:
- large per-frame text generation in custom scene drawing (outside widgets),
- expensive per-frame surface creation (e.g., overlays),
- heavy blit loops in card-book rendering (if expanded to hundreds/thousands of entries).

Recommended follow-ups (incremental):
- Move more scene-specific `font.render` calls onto `Theme.render_text`.
- Add optional caching for large list views (render list region to an offscreen surface and only redraw when dirty).
- Implement a reusable modal stack and true window z-ordering across all panels.

## Related: staff actor rendering
The shop view now also includes a visible staff actor with an XP bar + level indicator. The render path is kept viewport-safe and uses cached text. See `staff_xp_overview.md` for details.

---

## Related: tooltip rendering performance (instant hover, no spikes)

Tooltips were refactored into a centralized manager to prevent per-frame layout/render work while moving the cursor.

Key points:
- **Show delay** (~200ms) prevents flicker when moving across UI.
- **Cached tooltip surfaces** (LRU) keyed by style + text.
- Tooltip drawing is clamped to bounds and **does not intercept clicks**.

Files:
- `game/ui/tooltip_manager.py`
- `game/core/scene.py` (integration for global tooltips)

