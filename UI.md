# UI Architecture, Best Practices, and Roadmap

This project uses a lightweight, immediate-mode UI approach built directly on top of Pygame primitives. Most UI is composed from a small set of widgets (`Button`, `Panel`, `ScrollList`) and orchestrated by scenes.

## How the UI is programmed

### Immediate-mode rendering
- Each frame, the active scene draws the world first (shop floor/objects/customers) and then draws UI panels and controls on top.
- The **draw order** defines the visual stacking (and should match your input “stacking” expectations).

Example draw order in the unified shop scene:

```814:836:game/scenes/shop_scene.py
    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self._draw_grid(surface)
        self._draw_objects(surface)
        self._draw_customers(surface)
        self.order_panel.draw(surface, self.theme)
        if self.current_tab == "manage":
            self.stock_panel.draw(surface, self.theme)
            self.inventory_panel.draw(surface, self.theme)
            if self.manage_card_book_open:
                self.book_panel.draw(surface, self.theme)
        if self.current_tab == "deck":
            self.book_panel.draw(surface, self.theme)
            self.deck_panel.draw(surface, self.theme)
```

### Widget building blocks
The core widgets are intentionally simple and stateless beyond their rect/hover state:

```11:121:game/ui/widgets.py
class Button:
    def __init__(self, rect: pygame.Rect, text: str, on_click: Callable[[], None]) -> None:
        self.rect = rect
        self.text = text
        self.on_click = on_click
        self.hovered = False
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.enabled:
            return
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()

class Panel:
    def __init__(self, rect: pygame.Rect, title: str | None = None) -> None:
        self.rect = rect
        self.title = title
```

### Scenes own UI state
Each scene:
- Maintains UI state (selected tab, selected shelf, selected card, scroll offsets).
- Handles events (mouse, wheel, keys), updates timers/simulation, and draws.

The unified “single screen” experience is implemented in `game/scenes/shop_scene.py` by rendering different panels depending on `current_tab`.

### Global, always-available controls
`Scene` renders a wrapped top bar and a bottom-left Start/Stop day control that proxies to the shop scene:

```30:127:game/core/scene.py
    def __init__(self, app: "GameApp") -> None:
        self.app = app
        self.theme = app.theme
        self.top_buttons: list[Button] = []
        self.day_buttons: list[Button] = []
        self._last_screen_size = self.app.screen.get_size()
        self._build_top_bar()
        self._build_day_buttons()

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.top_buttons:
            button.handle_event(event)
        for button in self.day_buttons:
            button.handle_event(event)
```

## Layout, responsiveness, and resizing

### Responsive layout in `ShopScene`
`ShopScene` computes panel rects from the current window size and clamps them to avoid off-screen placement. It also rebuilds button rects when panels move/resize.

```87:151:game/scenes/shop_scene.py
    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._shop_y_offset = self._top_bar_height + 24
        panel_width = min(420, max(300, int(width * 0.26)))
        panel_height = min(360, max(220, int(height * 0.3)))
        # ... initial placement vs clamped placement ...

    def _clamp_rect(self, rect: pygame.Rect, width: int, height: int) -> pygame.Rect:
        rect.width = max(240, min(rect.width, width - 40))
        rect.height = max(140, min(rect.height, height - self._top_bar_height - 40))
        rect.x = max(8, min(rect.x, width - rect.width - 8))
        rect.y = max(self._top_bar_height + 8, min(rect.y, height - rect.height - 8))
        return rect
```

### Wrapped tabs (no overflow)
Both the base scene tab row and the unified shop tabs wrap into multiple rows when space is limited. This prevents “overlapping/hidden” buttons on smaller windows.

## Input handling and “modal” overlays

### Event order matters
To avoid “double firing” clicks (e.g., clicking a list item also clicking an underlying button), you must:
- Check whether the pointer is inside the top-most interactive region.
- If it is, **handle the event there and return early**.

The Manage “card book overlay” uses this pattern:

```643:675:game/scenes/shop_scene.py
    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        # ...
        if self.current_tab == "manage":
            in_book = False
            if self.manage_card_book_open:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    in_book = self.book_panel.rect.collidepoint(event.pos)
                    if in_book:
                        self._handle_deck_click(event.pos)
                if event.type == pygame.MOUSEWHEEL:
                    in_book = self.book_panel.rect.collidepoint(pygame.mouse.get_pos())
                    if in_book:
                        self._scroll_card_book(-event.y * 24)
            if not in_book:
                if getattr(event, "pos", None) and self.shelf_list.rect.collidepoint(event.pos):
                    self.shelf_list.handle_event(event)
                    return
```

### Dragging/resizing panels
Panels are draggable/resizable via header/handle hit-testing and a clamp step to keep them on screen. When adding a new panel:
- Include it in the drag/resize hit-testing.
- Clamp it in `_layout()` and `_apply_drag_resize()`.
- Rebuild relevant buttons when the panel rect changes.

## Best practices for extending the UI

### Keep simulation and UI separate
- Put gameplay/sim state in `GameState`/`Inventory`/`ShopLayout`.
- Keep UI-only selections and scroll offsets inside the scene.

### Prefer shared “views” for shared data
The **Card Book** is the canonical view of the collection and is reused for:
- Deck building selection
- Manage “List Selected Card” selection

When you add filters/search later, implement them once in the Card Book view and reuse them.

### Don’t create “hidden clickable” areas
- If a panel can overlap another interactive area, enforce capture rules (overlay first).
- Visually dim/disable background controls when a modal is open (roadmap item).

### Keep rendering cheap
- Cache expensive surfaces (e.g., shop floor tiling) rather than recomputing each frame.
- Use `surface.set_clip()` for scroll regions and restore it afterward.

### Make user actions obvious
- Disable buttons when the action can’t succeed.
- Provide feedback text near the relevant panel (errors like “select a shelf first”, “not enough money”, etc.).

## Resources
- Pygame UI fundamentals: [Pygame docs](https://www.pygame.org/docs/)
- Immediate-mode UI patterns: [Dear ImGui principles](https://github.com/ocornut/imgui)
- Game UX patterns: [Game Programming Patterns (UI/state ideas)](https://gameprogrammingpatterns.com/)
- Accessibility checklists: [W3C WAI](https://www.w3.org/WAI/standards-guidelines/wcag/)

## UI Roadmap (more intuitive, more resilient)

### Near-term (high impact)
- **True modal system**: block input to underlying panels; dim background; ESC closes.
- **Toast/status log**: non-intrusive confirmations (order placed, delivery arrived, card listed).
- **Card Book filters**: rarity toggles, search by name/id, sort by owned/value.
- **Shelf UX**: show shelf hover tooltip (contents + price), highlight selected shelf in-world.

### Mid-term
- **Focus manager** for keyboard navigation (tab/enter/esc), plus configurable hotkeys.
- **Responsive typography** and optional UI scaling slider for smaller screens.
- **Reusable layout helpers** (grid/stack) to reduce manual pixel math and overlap risk.

### Long-term
- **Component library**: reusable “CardView”, “InventoryRow”, “ShelfContentsPanel”.
- **State machine for UI flows**: explicit states for manage/order/listing so bugs don’t appear during active simulation.
- **Accessibility**: high-contrast mode, larger text mode, color-blind safe rarity palette.

