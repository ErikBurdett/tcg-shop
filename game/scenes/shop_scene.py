from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.config import SHOP_GRID, TILE_SIZE
from game.core.scene import Scene
from game.sim.economy import daily_customer_count, choose_purchase
from game.ui.widgets import Button, Panel, ScrollList, ScrollItem
from game.sim.inventory import RARITIES, InventoryOrder
from game.cards.card_defs import CARD_INDEX
from game.cards.pack import open_booster
from game.assets import get_asset_manager
from game.assets.shop import get_shop_asset_manager

MINI_GRID = (14, 8)
MINI_TILE = 42


@dataclass
class Customer:
    pos: pygame.Vector2
    target: pygame.Vector2
    state: str
    sprite_id: int = 0
    purchase: tuple[str, str] | None = None
    done: bool = False


class ShopScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        # Hide base scene tabs; use custom unified tabs instead.
        self.top_buttons.clear()
        self.day_running = False
        self.day_timer = 0.0
        self.day_duration = 60.0
        self.customers: list[Customer] = []
        self.customer_schedule: list[float] = []
        self.spawned = 0
        self.selected_object = "shelf"
        self.current_tab = "shop"
        self.tabs = ["shop", "packs", "deck", "manage", "battle"]
        self.tab_buttons: list[Button] = []
        self.revealed_cards: list[str] = []
        self.reveal_index = 0
        self._top_bar_height = 48
        self._panel_padding = 16
        self._shop_y_offset = self._top_bar_height + 16
        self._last_screen_size = self.app.screen.get_size()
        self.panel = Panel(pygame.Rect(0, 0, 280, 300), "Controls")
        self.shelf_list = ScrollList(pygame.Rect(0, 0, 100, 100), [])
        self.selected_shelf_key: str | None = None
        self.product_index = 0
        self.products = [
            "booster",
            "deck",
            "single_common",
            "single_uncommon",
            "single_rare",
            "single_epic",
            "single_legendary",
        ]
        self.buttons: list[Button] = []
        self._floor_surface: pygame.Surface | None = None
        self._layout_initialized = False
        self._drag_target: str | None = None
        self._drag_offset = pygame.Vector2()
        self._resize_target: str | None = None
        self._resize_start = pygame.Vector2()
        self._resize_origin = pygame.Vector2()
        self._layout()
        self._build_buttons()
        self._init_assets()

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._shop_y_offset = self._top_bar_height + 24
        panel_width = min(420, max(320, int(width * 0.28)))
        panel_height = min(420, max(300, int(height * 0.4)))
        default_panel = pygame.Rect(
            width - panel_width - self._panel_padding,
            self._top_bar_height + self._panel_padding,
            panel_width,
            panel_height,
        )
        if not self._layout_initialized:
            panel_rect = default_panel
            list_rect = pygame.Rect(
                panel_rect.x,
                panel_rect.bottom + self._panel_padding,
                panel_rect.width,
                max(180, height - panel_rect.bottom - self._panel_padding * 2),
            )
        else:
            panel_rect = self.panel.rect.copy()
            list_rect = self.shelf_list.rect.copy()
            panel_rect = self._clamp_rect(panel_rect, width, height)
            list_rect = self._clamp_rect(list_rect, width, height)
        self.panel = Panel(panel_rect, "Controls")
        self.shelf_list = ScrollList(list_rect, self.shelf_list.items)
        self._last_screen_size = (width, height)
        self._layout_initialized = True

    def _clamp_rect(self, rect: pygame.Rect, width: int, height: int) -> pygame.Rect:
        rect.width = max(240, min(rect.width, width - 40))
        rect.height = max(140, min(rect.height, height - self._top_bar_height - 40))
        rect.x = max(8, min(rect.x, width - rect.width - 8))
        rect.y = max(self._top_bar_height + 8, min(rect.y, height - rect.height - 8))
        return rect

    def _build_buttons(self) -> None:
        self._build_tab_btns()
        x = self.panel.rect.x + 20
        y = self.panel.rect.y + 40
        button_width = self.panel.rect.width - 40
        self.buttons = []
        if self.current_tab == "shop":
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 34), "Start Day", self.start_day),
                Button(pygame.Rect(x, y + 46, button_width, 30), "Shelf", lambda: self._set_object("shelf")),
                Button(pygame.Rect(x, y + 82, button_width, 30), "Counter", lambda: self._set_object("counter")),
                Button(pygame.Rect(x, y + 118, button_width, 30), "Poster", lambda: self._set_object("poster")),
            ]
        elif self.current_tab == "packs":
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 34), "Open Pack", self._open_pack),
                Button(pygame.Rect(x, y + 46, button_width, 30), "Reveal All", self._reveal_all),
            ]
        elif self.current_tab == "manage":
            half = (button_width - 10) // 2
            prod_y = y + 84
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 32), "Order Boosters ($20)", self._order_boosters),
                Button(pygame.Rect(x, y + 38, button_width, 32), "Order Decks ($30)", self._order_decks),
                Button(pygame.Rect(x, y + 76, button_width, 32), "Order Singles (x5)", self._order_singles_current),
                Button(pygame.Rect(x, prod_y, half, 28), "Booster", lambda: self._set_product("booster")),
                Button(pygame.Rect(x + half + 10, prod_y, half, 28), "Deck", lambda: self._set_product("deck")),
                Button(pygame.Rect(x, prod_y + 32, half, 28), "Common", lambda: self._set_product("single_common")),
                Button(pygame.Rect(x + half + 10, prod_y + 32, half, 28), "Uncommon", lambda: self._set_product("single_uncommon")),
                Button(pygame.Rect(x, prod_y + 64, half, 28), "Rare", lambda: self._set_product("single_rare")),
                Button(pygame.Rect(x + half + 10, prod_y + 64, half, 28), "Epic", lambda: self._set_product("single_epic")),
                Button(pygame.Rect(x, prod_y + 96, half, 28), "Legendary", lambda: self._set_product("single_legendary")),
                Button(pygame.Rect(x, prod_y + 132, button_width, 28), "Stock 1", lambda: self._stock_shelf(1)),
                Button(pygame.Rect(x, prod_y + 164, button_width, 28), "Stock 5", lambda: self._stock_shelf(5)),
                Button(pygame.Rect(x, prod_y + 196, button_width, 28), "Fill Shelf", self._fill_shelf),
                Button(pygame.Rect(x, prod_y + 228, button_width, 28), "Prev Shelf", lambda: self._select_adjacent_shelf(-1)),
                Button(pygame.Rect(x, prod_y + 260, button_width, 28), "Next Shelf", lambda: self._select_adjacent_shelf(1)),
                Button(pygame.Rect(x, prod_y + 292, button_width, 28), "Clear Selection", self._clear_shelf_selection),
            ]
        elif self.current_tab == "battle":
            btn = Button(pygame.Rect(x, y, button_width, 34), "Start Battle", self._start_battle)
            btn.enabled = self.app.state.deck.is_valid()
            self.buttons = [btn]

    def _build_tab_btns(self) -> None:
        self.tab_buttons = []
        x = 20
        y = 8
        btn_w = 120
        btn_h = 32
        gap = 12
        for i, tab in enumerate(self.tabs):
            rect = pygame.Rect(x + i * (btn_w + gap), y, btn_w, btn_h)
            self.tab_buttons.append(Button(rect, tab.title(), lambda t=tab: self._switch_tab(t)))

    def _switch_tab(self, tab: str) -> None:
        self.current_tab = tab
        self._build_buttons()
        if tab == "manage":
            self._refresh_shelves()

    def _open_pack(self) -> None:
        if self.app.state.inventory.booster_packs <= 0:
            return
        self.app.state.inventory.booster_packs -= 1
        self.revealed_cards = open_booster(self.app.rng)
        for cid in self.revealed_cards:
            self.app.state.collection.add(cid, 1)
        self.reveal_index = 0

    def _reveal_all(self) -> None:
        self.reveal_index = len(self.revealed_cards)

    def _start_battle(self) -> None:
        if self.app.state.deck.is_valid():
            self.app.switch_scene("battle")

    def _set_product(self, product: str) -> None:
        if product in self.products:
            self.product_index = self.products.index(product)

    def _select_adjacent_shelf(self, delta: int) -> None:
        keys = sorted(self.app.state.shop_layout.shelf_stocks.keys())
        if not keys:
            return
        if self.selected_shelf_key not in keys:
            self.selected_shelf_key = keys[0]
            return
        idx = keys.index(self.selected_shelf_key)
        self.selected_shelf_key = keys[(idx + delta) % len(keys)]

    def _clear_shelf_selection(self) -> None:
        self.selected_shelf_key = None

    def _refresh_shelves(self) -> None:
        layout = self.app.state.shop_layout
        items: list[ScrollItem] = []
        for key, stock in layout.shelf_stocks.items():
            x, y = key.split(",")
            label = f"Shelf ({x},{y}) - {stock.product} x{stock.qty}"
            items.append(ScrollItem(key, label, stock))
        self.shelf_list.items = items
        self.shelf_list.on_select = self._select_shelf

    def _select_shelf(self, item: ScrollItem) -> None:
        self.selected_shelf_key = item.key

    def _prev_product(self) -> None:
        self.product_index = (self.product_index - 1) % len(self.products)

    def _next_product(self) -> None:
        self.product_index = (self.product_index + 1) % len(self.products)

    def _fill_shelf(self) -> None:
        if not self.selected_shelf_key:
            return
        shelf = self.app.state.shop_layout.shelf_stocks.get(self.selected_shelf_key)
        if not shelf:
            return
        remaining = shelf.max_qty - shelf.qty
        if remaining > 0:
            self._stock_shelf(remaining)

    def _stock_shelf(self, amount: int) -> None:
        if not self.selected_shelf_key:
            return
        layout = self.app.state.shop_layout
        shelf = layout.shelf_stocks.get(self.selected_shelf_key)
        if not shelf:
            return
        product = self.products[self.product_index]
        capacity = shelf.max_qty - shelf.qty
        if capacity <= 0:
            return
        to_add = min(amount, capacity)
        inv = self.app.state.inventory
        if product == "booster":
            to_add = min(to_add, inv.booster_packs)
            if to_add <= 0:
                return
            inv.booster_packs -= to_add
        elif product == "deck":
            to_add = min(to_add, inv.decks)
            if to_add <= 0:
                return
            inv.decks -= to_add
        elif product.startswith("single_"):
            rarity = product.replace("single_", "")
            available = inv.singles.get(rarity, 0)
            to_add = min(to_add, available)
            if to_add <= 0:
                return
            inv.singles[rarity] -= to_add
        else:
            return
        shelf.product = product
        shelf.qty += to_add
        self._refresh_shelves()

    def _order_boosters(self) -> None:
        cost = 20
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(5, 0, {}, cost)
        self.app.state.inventory.apply_order(order)
        self._refresh_shelves()

    def _order_decks(self) -> None:
        cost = 30
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(0, 3, {}, cost)
        self.app.state.inventory.apply_order(order)
        self._refresh_shelves()

    def _order_singles_current(self) -> None:
        product = self.products[self.product_index]
        if not product.startswith("single_"):
            return
        rarity = product.replace("single_", "")
        cost = 5 + RARITIES.index(rarity) * 2
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(0, 0, {rarity: 5}, cost)
        self.app.state.inventory.apply_order(order)
        self._refresh_shelves()

    def _init_assets(self) -> None:
        """Initialize shop assets."""
        shop_assets = get_shop_asset_manager()
        shop_assets.init()
        self._floor_surface = shop_assets.create_shop_floor_surface(SHOP_GRID, TILE_SIZE)

    def _set_object(self, kind: str) -> None:
        self.selected_object = kind

    def on_enter(self) -> None:
        self._build_buttons()
        if self.current_tab == "manage":
            self._refresh_shelves()

    def start_day(self) -> None:
        if self.day_running:
            return
        self.app.apply_end_of_day_orders()
        self.day_running = True
        self.day_timer = 0.0
        self.customers.clear()
        self.spawned = 0
        count = daily_customer_count(self.app.state.day, self.app.rng)
        self.customer_schedule = [i * (self.day_duration / max(1, count)) for i in range(count)]
        self.app.state.last_summary = self.app.state.last_summary.__class__()

    def end_day(self) -> None:
        self.day_running = False
        self.app.state.last_summary.profit = self.app.state.last_summary.revenue
        self.app.state.day += 1
        self.app.save_game()

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_target = None
            self._resize_target = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hit_drag_handle(event.pos):
                return
        for btn in self.tab_buttons:
            btn.handle_event(event)
        for button in self.buttons:
            button.handle_event(event)
        if self.current_tab == "manage":
            self.shelf_list.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                key = self._select_shelf_at_pos(event.pos)
                if key:
                    self.selected_shelf_key = key
        if self.current_tab != "shop":
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            tile = self._tile_at_pos(event.pos)
            if tile:
                self.app.state.shop_layout.place(self.selected_object, tile)

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.app.screen.get_size() != self._last_screen_size:
            self._layout()
            self._build_buttons()
        if self._drag_target or self._resize_target:
            self._apply_drag_resize()
        for tb in self.tab_buttons:
            tb.update(dt)
        for button in self.buttons:
            button.update(dt)
        if self.day_running:
            self._update_day(dt)
        if self.current_tab == "packs" and self.revealed_cards and self.reveal_index < len(self.revealed_cards):
            self.reveal_index += 1

    def _update_day(self, dt: float) -> None:
        self.day_timer += dt
        while self.spawned < len(self.customer_schedule) and self.day_timer >= self.customer_schedule[self.spawned]:
            self._spawn_customer()
            self.spawned += 1
        for customer in self.customers:
            if customer.done:
                continue
            self._move_customer(customer, dt)
        if self.spawned >= len(self.customer_schedule) and all(c.done for c in self.customers):
            self.end_day()

    def _spawn_customer(self) -> None:
        entrance = pygame.Vector2(1.5 * TILE_SIZE, (SHOP_GRID[1] - 1) * TILE_SIZE)
        shelves = self.app.state.shop_layout.shelf_tiles()
        if not shelves:
            return
        shelf = self.app.rng.choice(shelves)
        target = pygame.Vector2((shelf[0] + 0.5) * TILE_SIZE, (shelf[1] + 0.5) * TILE_SIZE)
        # Assign a random customer sprite
        shop_assets = get_shop_asset_manager()
        sprite_id = shop_assets.get_random_customer_id(self.app.rng)
        self.customers.append(Customer(entrance, target, "to_shelf", sprite_id))
        self.app.state.last_summary.customers += 1

    def _find_object_tile(self, kind: str) -> tuple[int, int] | None:
        for obj in self.app.state.shop_layout.objects:
            if obj.kind == kind:
                return obj.tile
        return None

    def _move_customer(self, customer: Customer, dt: float) -> None:
        speed = 80.0
        direction = customer.target - customer.pos
        if direction.length() > 1:
            customer.pos += direction.normalize() * speed * dt
            return
        if customer.state == "to_shelf":
            counter = self._find_object_tile("counter") or (10, 7)
            customer.target = pygame.Vector2((counter[0] + 0.5) * TILE_SIZE, (counter[1] + 0.5) * TILE_SIZE)
            customer.state = "to_counter"
            customer.purchase = self._choose_shelf_purchase()
        elif customer.state == "to_counter":
            if customer.purchase:
                self._process_purchase(customer.purchase)
            exit_pos = pygame.Vector2(1.5 * TILE_SIZE, (SHOP_GRID[1] - 0.5) * TILE_SIZE)
            customer.target = exit_pos
            customer.state = "exit"
        elif customer.state == "exit":
            customer.done = True

    def _choose_shelf_purchase(self) -> tuple[str, str] | None:
        layout = self.app.state.shop_layout
        available: list[tuple[str, str]] = []
        for key, stock in layout.shelf_stocks.items():
            if stock.qty > 0 and stock.product != "empty":
                available.append((key, stock.product))
        if not available:
            return None
        products = [prod for _, prod in available]
        chosen = choose_purchase(self.app.state.prices, products, self.app.rng)
        if chosen == "none":
            return None
        candidates = [item for item in available if item[1] == chosen]
        return self.app.rng.choice(candidates)

    def _process_purchase(self, purchase: tuple[str, str]) -> None:
        shelf_key, product = purchase
        prices = self.app.state.prices
        stock = self.app.state.shop_layout.shelf_stocks.get(shelf_key)
        if not stock or stock.qty <= 0:
            return
        if product == "booster":
            price = prices.booster
        elif product == "deck":
            price = prices.deck
        elif product.startswith("single_"):
            rarity = product.replace("single_", "")
            price = getattr(prices, f"single_{rarity}")
        else:
            return
        stock.qty -= 1
        self.app.state.money += price
        self.app.state.last_summary.revenue += price
        self.app.state.last_summary.units_sold += 1

    def _tile_at_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        x, y = pos
        y_off = self._shop_y_offset
        if y < y_off:
            return None
        y = y - y_off
        if x > SHOP_GRID[0] * TILE_SIZE or y > SHOP_GRID[1] * TILE_SIZE:
            return None
        return (x // TILE_SIZE, y // TILE_SIZE)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self._draw_grid(surface)
        self._draw_objects(surface)
        self._draw_customers(surface)
        self.panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        for tb in self.tab_buttons:
            tb.draw(surface, self.theme)
        self._draw_status(surface)
        if self.current_tab == "packs":
            self._draw_packs(surface)
        if self.current_tab == "manage":
            self._draw_manage(surface)

    def _draw_grid(self, surface: pygame.Surface) -> None:
        y_off = self._shop_y_offset
        if self._floor_surface:
            surface.blit(self._floor_surface, (0, y_off))
        else:
            for x in range(SHOP_GRID[0]):
                for y in range(SHOP_GRID[1]):
                    rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE + y_off, TILE_SIZE, TILE_SIZE)
                    pygame.draw.rect(surface, (40, 42, 50), rect)
                    pygame.draw.rect(surface, (30, 32, 38), rect, 1)

    def _draw_objects(self, surface: pygame.Surface) -> None:
        shop_assets = get_shop_asset_manager()
        y_off = self._shop_y_offset
        for obj in self.app.state.shop_layout.objects:
            rect = pygame.Rect(obj.tile[0] * TILE_SIZE, obj.tile[1] * TILE_SIZE + y_off, TILE_SIZE, TILE_SIZE)
            
            # Try to get furniture sprite
            sprite = shop_assets.get_furniture_sprite(obj.kind, (TILE_SIZE, TILE_SIZE))
            
            if sprite:
                surface.blit(sprite, rect.topleft)
            else:
                # Fallback to colored rectangles
                if obj.kind == "shelf":
                    color = (120, 90, 60)
                elif obj.kind == "counter":
                    color = (70, 120, 160)
                else:
                    color = (160, 100, 140)
                pygame.draw.rect(surface, color, rect)
                label = self.theme.font_small.render(obj.kind[0].upper(), True, self.theme.colors.text)
                surface.blit(label, label.get_rect(center=rect.center))
            
            # Draw stock info for shelves
            if obj.kind == "shelf":
                key = self.app.state.shop_layout._key(obj.tile)
                stock = self.app.state.shop_layout.shelf_stocks.get(key)
                if self.selected_shelf_key == key and self.current_tab == "manage":
                    pygame.draw.rect(surface, self.theme.colors.accent, rect, 2)
                if stock and stock.product != "empty":
                    # Draw stock indicator
                    text = self.theme.font_small.render(f"{stock.qty}", True, self.theme.colors.text)
                    # Position at bottom-right of tile
                    text_rect = text.get_rect(bottomright=(rect.right - 2, rect.bottom - 2))
                    # Add background for readability
                    bg_rect = text_rect.inflate(4, 2)
                    pygame.draw.rect(surface, (20, 22, 28), bg_rect)
                    surface.blit(text, text_rect)

    def _draw_customers(self, surface: pygame.Surface) -> None:
        shop_assets = get_shop_asset_manager()
        customer_size = 40
        y_off = self._shop_y_offset
        for customer in self.customers:
            if customer.done:
                continue
            sprite = shop_assets.get_customer_sprite(customer.sprite_id, (customer_size, customer_size))
            if sprite:
                sprite_x = int(customer.pos.x - customer_size // 2)
                sprite_y = int(customer.pos.y - customer_size + 8 + y_off)
                surface.blit(sprite, (sprite_x, sprite_y))
            else:
                rect = pygame.Rect(customer.pos.x - 10, customer.pos.y - 10 + y_off, 20, 20)
                pygame.draw.rect(surface, (200, 200, 120), rect)

    def _draw_status(self, surface: pygame.Surface) -> None:
        y_off = self._shop_y_offset
        text = self.theme.font.render(
            f"Day {self.app.state.day} | Money ${self.app.state.money}", True, self.theme.colors.text
        )
        surface.blit(text, (20, SHOP_GRID[1] * TILE_SIZE + y_off + 8))
        status_y = SHOP_GRID[1] * TILE_SIZE + y_off + 34
        if self.day_running:
            timer_text = self.theme.font_small.render(
                f"Day progress: {int(self.day_timer)}s/{int(self.day_duration)}s", True, self.theme.colors.muted
            )
            surface.blit(timer_text, (20, status_y))
        else:
            summary = self.app.state.last_summary
            summary_text = self.theme.font_small.render(
                f"+${summary.revenue} | {summary.units_sold} sold | {summary.customers} customers",
                True, self.theme.colors.muted,
            )
            surface.blit(summary_text, (20, status_y))

    def _draw_packs(self, surface: pygame.Surface) -> None:
        asset_mgr = get_asset_manager()
        y = SHOP_GRID[1] * TILE_SIZE + self._shop_y_offset + 60
        for idx, card_id in enumerate(self.revealed_cards):
            rect = pygame.Rect(20 + idx * 130, y, 120, 160)
            if idx < self.reveal_index:
                card = CARD_INDEX[card_id]
                bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
                surface.blit(bg, rect.topleft)
                sprite = asset_mgr.get_card_sprite(card_id, (64, 64))
                if sprite:
                    surface.blit(sprite, (rect.x + 28, rect.y + 15))
                pygame.draw.rect(surface, getattr(self.theme.colors, f"card_{card.rarity}"), rect, 2)
                name = self.theme.font_small.render(card.name[:10], True, self.theme.colors.text)
                surface.blit(name, (rect.x + 5, rect.y + 85))

    def _select_shelf_at_pos(self, pos: tuple[int, int]) -> str | None:
        y_off = self._shop_y_offset
        for obj in self.app.state.shop_layout.objects:
            if obj.kind != "shelf":
                continue
            rect = pygame.Rect(
                obj.tile[0] * TILE_SIZE,
                obj.tile[1] * TILE_SIZE + y_off,
                TILE_SIZE,
                TILE_SIZE,
            )
            if rect.collidepoint(pos):
                return self.app.state.shop_layout._key(obj.tile)
        return None

    def _hit_drag_handle(self, pos: tuple[int, int]) -> bool:
        if self._start_drag_or_resize(self.panel.rect, "panel", pos):
            return True
        if self.current_tab == "manage" and self._start_drag_or_resize(self.shelf_list.rect, "list", pos):
            return True
        return False

    def _start_drag_or_resize(self, rect: pygame.Rect, target: str, pos: tuple[int, int]) -> bool:
        x, y = pos
        resize_zone = pygame.Rect(rect.right - 14, rect.bottom - 14, 14, 14)
        header_zone = pygame.Rect(rect.x, rect.y, rect.width, 24)
        if resize_zone.collidepoint(pos):
            self._resize_target = target
            self._resize_start = pygame.Vector2(x, y)
            self._resize_origin = pygame.Vector2(rect.width, rect.height)
            return True
        if header_zone.collidepoint(pos):
            self._drag_target = target
            self._drag_offset = pygame.Vector2(x - rect.x, y - rect.y)
            return True
        return False

    def _apply_drag_resize(self) -> None:
        mouse = pygame.Vector2(pygame.mouse.get_pos())
        width, height = self.app.screen.get_size()
        if self._drag_target:
            rect = self.panel.rect if self._drag_target == "panel" else self.shelf_list.rect
            rect.x = int(mouse.x - self._drag_offset.x)
            rect.y = int(mouse.y - self._drag_offset.y)
            rect = self._clamp_rect(rect, width, height)
            if self._drag_target == "panel":
                self.panel = Panel(rect, "Controls")
                self._build_buttons()
            else:
                self.shelf_list.rect = rect
        if self._resize_target:
            rect = self.panel.rect if self._resize_target == "panel" else self.shelf_list.rect
            delta = mouse - self._resize_start
            rect.width = int(self._resize_origin.x + delta.x)
            rect.height = int(self._resize_origin.y + delta.y)
            rect = self._clamp_rect(rect, width, height)
            if self._resize_target == "panel":
                self.panel = Panel(rect, "Controls")
                self._build_buttons()
            else:
                self.shelf_list.rect = rect

    
    def _draw_manage(self, surface: pygame.Surface) -> None:
        # Shelf list
        title = self.theme.font_small.render("Shelf Stock", True, self.theme.colors.text)
        surface.blit(title, (self.shelf_list.rect.x, self.shelf_list.rect.y - 22))
        pygame.draw.rect(surface, self.theme.colors.border, self.shelf_list.rect, 2)
        self.shelf_list.draw(surface, self.theme)
        # Selected product + inventory
        product = self.products[self.product_index]
        prod_text = self.theme.font_small.render(f"Product: {product}", True, self.theme.colors.text)
        surface.blit(prod_text, (self.panel.rect.x + 20, self.panel.rect.bottom + 8))
        selected = self.selected_shelf_key or "None"
        sel_text = self.theme.font_small.render(f"Selected shelf: {selected}", True, self.theme.colors.muted)
        surface.blit(sel_text, (self.panel.rect.x + 20, self.panel.rect.bottom + 26))
        inv = self.app.state.inventory
        inv_lines = [
            f"Boosters: {inv.booster_packs}",
            f"Decks: {inv.decks}",
        ] + [f"{r.title()}: {inv.singles.get(r, 0)}" for r in RARITIES]
        y = self.panel.rect.bottom + 48
        for line in inv_lines:
            text = self.theme.font_small.render(line, True, self.theme.colors.muted)
            surface.blit(text, (self.panel.rect.x + 20, y))
            y += 18
