# Performance / UI Responsiveness QA

This checklist is intended to verify **low input latency** and **stable frame time** during heavy UI interaction (dragging/resizing).

## Tools
- Toggle the debug overlay with **F3**
  - Watch: **input / update / draw (ms)**, **draw calls**, **text cache hit/miss**
  - In `ShopScene`, watch: **Drag(shop) latency** line (avg/max pixels)
  - Staff path/target is drawn in the shop viewport while F3 is enabled (debug visual)

## Manual QA checklist

### Drag panels (general)
- Drag `Ordering`, `Stocking`, `Inventory`, `Card Book`, `Deck` panels rapidly.
- Expected:
  - Panel tracks cursor every frame (no stepping).
  - Debug overlay: **input ms** stays low and stable.
  - No “click-through”: while dragging, other buttons/lists should not react.

### Drag shop viewport window
- Drag the `Shop` window rapidly across the screen.
- Expected:
  - Motion stays smooth.
  - Debug overlay shows **Drag(shop) latency** near 0 most frames.
  - Draw time should not spike badly during drag (shop uses a cached snapshot during drag).

### Resize shop viewport window
- Resize the `Shop` window continuously for ~5 seconds.
- Expected:
  - Resize remains responsive.
  - Shop uses a **throttled preview** while resizing; full re-render resumes on release.
  - After mouse release, shop viewport rescales cleanly and customers remain positioned correctly.

### Drag while simulation runs
- Start Day and drag `Shop` window while customers are moving.
- Expected:
  - Simulation continues (day timer/customers still progress).
  - Visual shop content may “freeze” during active drag/resize (cached snapshot), but UI remains snappy.

## Regression checks
- Open Manage, scroll shelf list, open Card Book, select a card, list to shelf.
- Ensure scroll wheel only affects the hovered scroll area.
- Ensure modal menu still captures input correctly when open.

