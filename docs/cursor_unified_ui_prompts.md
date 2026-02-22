# Cursor Prompts — Unified Gameplay Shell (Step-by-step)

Use these prompts with **Cursor GPT-5.2 High Fast** first, then run the final quality pass with **Claude 3.7 Sonnet (recommended second model for review/refactor safety)**.

---

## Prompt 1 — Scene consolidation router
```text
Refactor this Pygame project so all gameplay scene keys route into a single gameplay shell scene (`shop`) while preserving a standalone `menu` scene.

Requirements:
- Keep menu scene as load/exit hub.
- Route keys {shop,packs,sell,deck,manage,stats,skills,battle} to shop shell.
- On route, call shop._switch_tab(key) if available.
- Do not break existing save/load flow.
- Add tests for switch routing behavior.

Edit:
- game/core/app.py
- game/tests.py
```

## Prompt 2 — Bottom nav + mobile hamburger
```text
Implement a responsive bottom navigation strip in ShopScene:
- Desktop: single horizontal tab row at bottom.
- Mobile breakpoint (<980px): show '☰ Menus' button and toggle tab list.
- Keep existing tab behavior and menu modal behavior.
- Ensure buttons update on resize and do not overlap drag handles.

Edit:
- game/scenes/shop_scene.py
```

## Prompt 3 — Top information chips + hover tooltips
```text
Add a top info bar to ShopScene with chips:
Money, Day, Cycle, XP, Staff.

Requirements:
- Draw compact chips at top.
- Use cached text rendering.
- Add hover tooltips with concise explanations.
- Keep tooltip clamping logic compatible with shop viewport.

Edit:
- game/scenes/shop_scene.py
```

## Prompt 4 — Keep drag/resize stable
```text
Audit drag/resize handling in ShopScene after nav changes.

Requirements:
- Do not regress panel drag/resize behavior.
- Keep fast relayout path during dragging.
- Ensure shop viewport clipping and cached snapshots still work.
- Add/adjust tests where possible.

Edit:
- game/scenes/shop_scene.py
- game/tests.py
```

## Prompt 5 — Documentation + architecture notes
```text
Update docs to explain the unified gameplay shell architecture.

Requirements:
- README section describing Main Menu + single gameplay shell.
- Add docs/unified_gameplay_shell_plan.md with goals, implementation notes, and phased roadmap.
- Keep docs concise and implementation-accurate.
```

---

## Second model review prompt (recommended)

Use with **Claude 3.7 Sonnet**:

```text
Review this branch for architecture safety and regression risk.
Focus on:
1) Scene-routing correctness and unintended side effects.
2) Input handling conflicts between bottom nav, overlays, and drag/resize.
3) Tooltip hit-testing and clipping correctness.
4) Performance hotspots (button rebuilds, text rendering, draw-time allocations).
5) Mobile layout usability and tap target spacing.

Provide:
- concrete bug risks with file/line references,
- suggested patches,
- and a prioritized fix list (P0/P1/P2).
```
