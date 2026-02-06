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
from game.ui.effects import draw_glow_border
from game.ui.layout import anchor_rect

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
        # Hide legacy scene nav; use custom unified tabs instead.
        self.show_top_bar = False
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
        # UI and shop viewport offsets (shop area is centered within available space)
        self._ui_top = self._top_bar_height + 16
        self._shop_y_offset = self._ui_top
        self._shop_x_offset = 0
        self.tile_px = TILE_SIZE
        self._floor_tile_px = TILE_SIZE
        self._last_screen_size = self.app.screen.get_size()
        self.shop_panel = Panel(pygame.Rect(0, 0, 640, 520), "Shop")
        self.order_panel = Panel(pygame.Rect(0, 0, 280, 240), "Ordering")
        self.stock_panel = Panel(pygame.Rect(0, 0, 280, 280), "Stocking")
        self.inventory_panel = Panel(pygame.Rect(0, 0, 280, 240), "Inventory")
        self.book_panel = Panel(pygame.Rect(0, 0, 540, 520), "Card Book")
        self.deck_panel = Panel(pygame.Rect(0, 0, 320, 420), "Deck")
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
        self.card_book_scroll = 0
        self.selected_card_id: str | None = None
        # Manage "List Selected Card" menu state (card book overlay)
        self.manage_card_book_open = False
        # Unified menu modal
        self.menu_open = False
        self.menu_panel = Panel(anchor_rect(self.app.screen, (420, 260), "center"), "Menu")
        self.menu_buttons: list[Button] = []
        self.market_rarity_index = 0
        self.buttons: list[Button] = []
        self._floor_surface: pygame.Surface | None = None
        self._layout_initialized = False
        self._drag_target: str | None = None
        self._drag_offset = pygame.Vector2()
        self._resize_target: str | None = None
        self._resize_start = pygame.Vector2()
        self._resize_origin = pygame.Vector2()
        # Drag latency stats (mouse vs window position) for debug overlay.
        self._drag_latency_sum = 0.0
        self._drag_latency_max = 0.0
        self._drag_latency_frames = 0
        self._last_drag_latency_avg = 0.0
        self._last_drag_latency_max = 0.0
        # Shop window caching during drag/resize (snappy interaction).
        self._shop_drag_snapshot: pygame.Surface | None = None
        self._shop_snapshot_pending = False
        self._shop_resize_preview: pygame.Surface | None = None
        self._shop_resize_preview_size = (0, 0)
        self._shop_resize_preview_time = 0.0
        self._layout()
        self._build_buttons()
        self._init_assets()

    def debug_lines(self) -> list[str]:
        if self._drag_target:
            avg = (self._drag_latency_sum / self._drag_latency_frames) if self._drag_latency_frames else 0.0
            return [f"Drag({self._drag_target}) latency: avg {avg:0.2f}px | max {self._drag_latency_max:0.2f}px"]
        if self._last_drag_latency_frames_ok():
            return [
                f"Last drag latency: avg {self._last_drag_latency_avg:0.2f}px | max {self._last_drag_latency_max:0.2f}px"
            ]
        return []

    def _last_drag_latency_frames_ok(self) -> bool:
        return self._last_drag_latency_max > 0.0 or self._last_drag_latency_avg > 0.0

    def _shop_inner_rect(self) -> pygame.Rect:
        # Keep consistent with drag header zone height (24) and panel border padding.
        rect = self.shop_panel.rect
        return pygame.Rect(rect.x + 6, rect.y + 28, max(1, rect.width - 12), max(1, rect.height - 34))

    def _update_shop_viewport(self, *, rescale: bool) -> None:
        """Update tile size and grid origin based on shop_panel size/position."""
        inner = self._shop_inner_rect()
        old_tile = self.tile_px
        if rescale:
            ideal = int(min(inner.width / SHOP_GRID[0], inner.height / SHOP_GRID[1]))
            self.tile_px = max(24, min(ideal, 84))
        grid_w = SHOP_GRID[0] * self.tile_px
        grid_h = SHOP_GRID[1] * self.tile_px
        self._shop_x_offset = inner.x + max(0, (inner.width - grid_w) // 2)
        self._shop_y_offset = inner.y + max(0, (inner.height - grid_h) // 2)

        if rescale and old_tile and self.tile_px != old_tile and self.customers:
            scale = self.tile_px / old_tile
            for c in self.customers:
                c.pos *= scale
                c.target *= scale

        if rescale and self._floor_tile_px != self.tile_px:
            shop_assets = get_shop_asset_manager()
            shop_assets.init()
            self._floor_surface = shop_assets.create_shop_floor_surface(SHOP_GRID, self.tile_px)
            self._floor_tile_px = self.tile_px

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        base_top = self._top_bar_height + 24
        self._ui_top = base_top
        panel_width = min(520, max(360, int(width * 0.26)))
        panel_height = min(360, max(220, int(height * 0.3)))
        if not self._layout_initialized:
            # Default arrangement (matches the intended "manage" layout screenshot):
            # - Ordering: top-right
            # - Stocking: bottom-right (tall enough for all controls)
            # - Inventory: bottom-left
            # - Shelf list: top-center-right (between shop and ordering)
            top_y = self._top_bar_height + self._panel_padding
            order_h = max(panel_height, 220)
            order_rect = pygame.Rect(width - panel_width - self._panel_padding, top_y, panel_width, order_h)

            stock_h = min(height - top_y - self._panel_padding, max(520, int(height * 0.48)))
            stock_rect = pygame.Rect(
                width - panel_width - self._panel_padding,
                height - stock_h - self._panel_padding,
                panel_width,
                stock_h,
            )

            inv_w = min(420, max(320, int(width * 0.26)))
            inv_h = min(320, max(240, int(height * 0.28)))
            inv_rect = pygame.Rect(self._panel_padding, height - inv_h - self._panel_padding, inv_w, inv_h)

            list_w = min(520, max(360, int(width * 0.34)))
            list_h = 150
            list_x = max(self._panel_padding, order_rect.x - list_w - self._panel_padding)
            list_rect = pygame.Rect(list_x, top_y + 12, list_w, list_h)
            # Shop viewport window fills the center play area by default.
            shop_left = self._panel_padding
            shop_top = top_y + self._panel_padding
            shop_right = min(list_rect.x, order_rect.x) - self._panel_padding
            shop_bottom = inv_rect.y - self._panel_padding
            shop_w = max(520, shop_right - shop_left)
            shop_h = max(420, shop_bottom - shop_top)
            shop_rect = pygame.Rect(shop_left, shop_top, shop_w, shop_h)
            book_rect = pygame.Rect(
                self._panel_padding,
                base_top + self._panel_padding,
                max(520, int(width * 0.45)),
                max(420, int(height * 0.55)),
            )
            deck_rect = pygame.Rect(
                book_rect.right + self._panel_padding,
                book_rect.y,
                max(260, int(width * 0.18)),
                max(320, int(height * 0.4)),
            )
        else:
            order_rect = self._clamp_rect(self.order_panel.rect.copy(), width, height)
            stock_rect = self._clamp_rect(self.stock_panel.rect.copy(), width, height)
            inv_rect = self._clamp_rect(self.inventory_panel.rect.copy(), width, height)
            list_rect = self.shelf_list.rect.copy()
            list_rect = self._clamp_rect(list_rect, width, height)
            book_rect = self._clamp_rect(self.book_panel.rect.copy(), width, height)
            deck_rect = self._clamp_rect(self.deck_panel.rect.copy(), width, height)
            shop_rect = self._clamp_rect(self.shop_panel.rect.copy(), width, height)
        self.order_panel = Panel(order_rect, "Ordering")
        self.stock_panel = Panel(stock_rect, "Stocking")
        self.inventory_panel = Panel(inv_rect, "Inventory")
        self.book_panel = Panel(book_rect, "Card Book")
        self.deck_panel = Panel(deck_rect, "Deck")
        self.shop_panel = Panel(shop_rect, "Shop")
        self.shelf_list = ScrollList(list_rect, self.shelf_list.items)
        # Center the unified menu modal on resize.
        self.menu_panel = Panel(anchor_rect(self.app.screen, (420, 260), "center"), "Menu")
        self._update_shop_viewport(rescale=True)
        self._last_screen_size = (width, height)
        self._layout_initialized = True

    def _clamp_rect(self, rect: pygame.Rect, width: int, height: int) -> pygame.Rect:
        rect.width = max(240, min(rect.width, width - 40))
        rect.height = max(140, min(rect.height, height - self._top_bar_height - 40))
        rect.x = max(8, min(rect.x, width - rect.width - 8))
        rect.y = max(self._top_bar_height + 8, min(rect.y, height - rect.height - 8))
        return rect

    def _clamp_rect_target(self, rect: pygame.Rect, width: int, height: int, target: str) -> pygame.Rect:
        # Ensure key manage panels are always large enough for their controls.
        min_w = 240
        min_h = 140
        if target == "stock":
            min_w = 360
            min_h = 520
        elif target == "order":
            min_w = 320
            min_h = 220
        elif target == "inventory":
            min_w = 300
            min_h = 220
        elif target == "shop":
            min_w = 560
            min_h = 420
        rect.width = max(min_w, min(rect.width, width - 40))
        rect.height = max(min_h, min(rect.height, height - self._top_bar_height - 40))
        rect.x = max(8, min(rect.x, width - rect.width - 8))
        rect.y = max(self._top_bar_height + 8, min(rect.y, height - rect.height - 8))
        return rect

    def _open_list_card_menu(self) -> None:
        self.manage_card_book_open = True
        self._build_buttons()

    def _close_list_card_menu(self) -> None:
        self.manage_card_book_open = False
        self._build_buttons()

    def _card_book_controls_height(self) -> int:
        # Extra space for card-market + list-to-shelf controls.
        if self.current_tab == "manage" and self.manage_card_book_open:
            return 64
        return 0

    def _card_book_content_rect(self) -> pygame.Rect:
        book_rect = self.book_panel.rect
        padding = 12
        controls_h = self._card_book_controls_height()
        top = book_rect.y + 36 + controls_h
        bottom_pad = 12
        height = max(80, book_rect.bottom - bottom_pad - top)
        return pygame.Rect(book_rect.x + padding, top, book_rect.width - padding * 2, height)

    def _relayout_buttons_only(self) -> None:
        """Fast path for dragging/resizing panels: update button rects without recreating Button objects."""
        bw = self.order_panel.rect.width - 40

        def set_rect_by_text(text: str, rect: pygame.Rect) -> None:
            for b in self.buttons:
                if b.text == text:
                    b.rect = rect
                    return

        if self.current_tab == "shop":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            set_rect_by_text("Shelf", pygame.Rect(x, y, bw, 30))
            set_rect_by_text("Counter", pygame.Rect(x, y + 36, bw, 30))
            set_rect_by_text("Poster", pygame.Rect(x, y + 72, bw, 30))
            return

        if self.current_tab == "packs":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            set_rect_by_text("Open Pack", pygame.Rect(x, y, bw, 34))
            set_rect_by_text("Reveal All", pygame.Rect(x, y + 46, bw, 30))
            return

        if self.current_tab == "battle":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            set_rect_by_text("Start Battle", pygame.Rect(x, y, bw, 34))
            return

        if self.current_tab == "deck":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            half = (bw - 10) // 2
            set_rect_by_text("Add to Deck", pygame.Rect(x, y, bw, 32))
            set_rect_by_text("Remove from Deck", pygame.Rect(x, y + 38, bw, 32))
            set_rect_by_text("Auto Fill", pygame.Rect(x, y + 76, bw, 32))
            set_rect_by_text("Clear Deck", pygame.Rect(x, y + 114, bw, 32))
            set_rect_by_text("Rarity -", pygame.Rect(x, y + 160, half, 28))
            set_rect_by_text("Rarity +", pygame.Rect(x + half + 10, y + 160, half, 28))
            for b in self.buttons:
                if b.text.startswith("Buy Random "):
                    b.rect = pygame.Rect(x, y + 194, bw, 30)
                    break
            return

        if self.current_tab == "manage":
            order_x = self.order_panel.rect.x + 20
            order_y = self.order_panel.rect.y + 40
            stock_x = self.stock_panel.rect.x + 20
            stock_y = self.stock_panel.rect.y + 40
            stock_w = self.stock_panel.rect.width - 40
            half = (stock_w - 10) // 2

            for b in self.buttons:
                if b.text.startswith("Order ") and "Boosters" in b.text:
                    b.rect = pygame.Rect(order_x, order_y, bw, 32)
                elif b.text.startswith("Order ") and "Decks" in b.text:
                    b.rect = pygame.Rect(order_x, order_y + 38, bw, 32)
                elif b.text.startswith("Order ") and "Singles" in b.text:
                    b.rect = pygame.Rect(order_x, order_y + 76, bw, 32)

            set_rect_by_text("Booster", pygame.Rect(stock_x, stock_y, half, 28))
            set_rect_by_text("Deck", pygame.Rect(stock_x + half + 10, stock_y, half, 28))
            set_rect_by_text("Common", pygame.Rect(stock_x, stock_y + 32, half, 28))
            set_rect_by_text("Uncommon", pygame.Rect(stock_x + half + 10, stock_y + 32, half, 28))
            set_rect_by_text("Rare", pygame.Rect(stock_x, stock_y + 64, half, 28))
            set_rect_by_text("Epic", pygame.Rect(stock_x + half + 10, stock_y + 64, half, 28))
            set_rect_by_text("Legendary", pygame.Rect(stock_x, stock_y + 96, half, 28))

            set_rect_by_text("Price -1", pygame.Rect(stock_x, stock_y + 132, half, 28))
            set_rect_by_text("Price +1", pygame.Rect(stock_x + half + 10, stock_y + 132, half, 28))
            set_rect_by_text("Price -5", pygame.Rect(stock_x, stock_y + 164, half, 28))
            set_rect_by_text("Price +5", pygame.Rect(stock_x + half + 10, stock_y + 164, half, 28))
            set_rect_by_text("Stock 1", pygame.Rect(stock_x, stock_y + 200, stock_w, 28))
            set_rect_by_text("Stock 5", pygame.Rect(stock_x, stock_y + 232, stock_w, 28))
            set_rect_by_text("Fill Shelf", pygame.Rect(stock_x, stock_y + 264, stock_w, 28))
            set_rect_by_text("List Selected Card", pygame.Rect(stock_x, stock_y + 296, stock_w, 28))
            set_rect_by_text("Prev Shelf", pygame.Rect(stock_x, stock_y + 328, stock_w, 28))
            set_rect_by_text("Next Shelf", pygame.Rect(stock_x, stock_y + 360, stock_w, 28))
            set_rect_by_text("Clear Selection", pygame.Rect(stock_x, stock_y + 392, stock_w, 28))

            if self.manage_card_book_open:
                book = self.book_panel.rect
                bx = book.x + 12
                by = book.y + 32
                bh = 28
                gap = 8
                set_rect_by_text("Close", pygame.Rect(book.right - 12 - 90, by, 90, bh))
                set_rect_by_text("List 1 to Shelf", pygame.Rect(bx, by, 200, bh))
                set_rect_by_text("Rarity -", pygame.Rect(bx, by + bh + gap, 90, bh))
                set_rect_by_text("Rarity +", pygame.Rect(bx + 90 + gap, by + bh + gap, 90, bh))
                for b in self.buttons:
                    if b.text.startswith("Buy Random "):
                        b.rect = pygame.Rect(bx + (90 + gap) * 2, by + bh + gap, book.width - 24 - (90 + gap) * 2, bh)
                        break
            return

    def _build_buttons(self) -> None:
        self._build_tab_btns()
        button_width = self.order_panel.rect.width - 40
        self.buttons = []
        if self.current_tab == "shop":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 30), "Shelf", lambda: self._set_object("shelf")),
                Button(pygame.Rect(x, y + 36, button_width, 30), "Counter", lambda: self._set_object("counter")),
                Button(pygame.Rect(x, y + 72, button_width, 30), "Poster", lambda: self._set_object("poster")),
            ]
        elif self.current_tab == "packs":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 34), "Open Pack", self._open_pack),
                Button(pygame.Rect(x, y + 46, button_width, 30), "Reveal All", self._reveal_all),
            ]
        elif self.current_tab == "manage":
            order_x = self.order_panel.rect.x + 20
            order_y = self.order_panel.rect.y + 40
            stock_x = self.stock_panel.rect.x + 20
            stock_y = self.stock_panel.rect.y + 40
            stock_width = self.stock_panel.rect.width - 40
            half = (stock_width - 10) // 2
            booster_qty = 12
            deck_qty = 4
            singles_qty = 10
            booster_cost = self._wholesale_cost("booster", booster_qty)
            deck_cost = self._wholesale_cost("deck", deck_qty)
            singles_product = self._selected_single_product()
            singles_rarity = singles_product.replace("single_", "")
            singles_cost = self._wholesale_cost(singles_product, singles_qty)
            self.buttons = [
                Button(
                    pygame.Rect(order_x, order_y, button_width, 32),
                    f"Order {booster_qty} Boosters (${booster_cost})",
                    self._order_boosters,
                ),
                Button(
                    pygame.Rect(order_x, order_y + 38, button_width, 32),
                    f"Order {deck_qty} Decks (${deck_cost})",
                    self._order_decks,
                ),
                Button(
                    pygame.Rect(order_x, order_y + 76, button_width, 32),
                    f"Order {singles_qty} {singles_rarity.title()} Singles (${singles_cost})",
                    self._order_singles_current,
                ),
                Button(pygame.Rect(stock_x, stock_y, half, 28), "Booster", lambda: self._set_product("booster")),
                Button(pygame.Rect(stock_x + half + 10, stock_y, half, 28), "Deck", lambda: self._set_product("deck")),
                Button(pygame.Rect(stock_x, stock_y + 32, half, 28), "Common", lambda: self._set_product("single_common")),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 32, half, 28), "Uncommon", lambda: self._set_product("single_uncommon")),
                Button(pygame.Rect(stock_x, stock_y + 64, half, 28), "Rare", lambda: self._set_product("single_rare")),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 64, half, 28), "Epic", lambda: self._set_product("single_epic")),
                Button(pygame.Rect(stock_x, stock_y + 96, half, 28), "Legendary", lambda: self._set_product("single_legendary")),
                Button(pygame.Rect(stock_x, stock_y + 132, half, 28), "Price -1", lambda: self._adjust_price(-1)),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 132, half, 28), "Price +1", lambda: self._adjust_price(1)),
                Button(pygame.Rect(stock_x, stock_y + 164, half, 28), "Price -5", lambda: self._adjust_price(-5)),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 164, half, 28), "Price +5", lambda: self._adjust_price(5)),
                Button(pygame.Rect(stock_x, stock_y + 200, stock_width, 28), "Stock 1", lambda: self._stock_shelf(1)),
                Button(pygame.Rect(stock_x, stock_y + 232, stock_width, 28), "Stock 5", lambda: self._stock_shelf(5)),
                Button(pygame.Rect(stock_x, stock_y + 264, stock_width, 28), "Fill Shelf", self._fill_shelf),
                Button(pygame.Rect(stock_x, stock_y + 296, stock_width, 28), "List Selected Card", self._open_list_card_menu),
                Button(pygame.Rect(stock_x, stock_y + 328, stock_width, 28), "Prev Shelf", lambda: self._select_adjacent_shelf(-1)),
                Button(pygame.Rect(stock_x, stock_y + 360, stock_width, 28), "Next Shelf", lambda: self._select_adjacent_shelf(1)),
                Button(pygame.Rect(stock_x, stock_y + 392, stock_width, 28), "Clear Selection", self._clear_shelf_selection),
            ]
            if self.manage_card_book_open:
                book = self.book_panel.rect
                bx = book.x + 12
                by = book.y + 32
                bh = 28
                gap = 8
                close_btn = Button(pygame.Rect(book.right - 12 - 90, by, 90, bh), "Close", self._close_list_card_menu)
                list_btn = Button(pygame.Rect(bx, by, 200, bh), "List 1 to Shelf", self._list_selected_card_to_shelf)
                list_btn.enabled = self._can_list_selected_card_to_shelf()
                r1y = by + bh + gap
                r_btn_w = 90
                rarity = RARITIES[self.market_rarity_index]
                buy_price = self._market_buy_price(rarity)
                rarity_minus = Button(pygame.Rect(bx, r1y, r_btn_w, bh), "Rarity -", self._prev_market_rarity)
                rarity_plus = Button(pygame.Rect(bx + r_btn_w + gap, r1y, r_btn_w, bh), "Rarity +", self._next_market_rarity)
                buy_btn = Button(
                    pygame.Rect(bx + (r_btn_w + gap) * 2, r1y, book.width - 24 - (r_btn_w + gap) * 2, bh),
                    f"Buy Random {rarity.title()} (${buy_price})",
                    self._buy_market_single,
                )
                self.buttons.extend([close_btn, list_btn, rarity_minus, rarity_plus, buy_btn])
            # If the shelf list overlaps controls, push it below the last stock control.
            stock_btns = [b for b in self.buttons if self.stock_panel.rect.collidepoint(b.rect.center)]
            if stock_btns:
                bottom = max(b.rect.bottom for b in stock_btns)
                desired_top = bottom + 18
                desired = pygame.Rect(
                    self.stock_panel.rect.x + 12,
                    desired_top,
                    self.stock_panel.rect.width - 24,
                    max(120, self.stock_panel.rect.bottom - desired_top - 12),
                )
                if any(b.rect.colliderect(self.shelf_list.rect) for b in stock_btns):
                    self.shelf_list.rect = desired
        elif self.current_tab == "deck":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            half = (button_width - 10) // 2
            rarity = RARITIES[self.market_rarity_index]
            buy_price = self._market_buy_price(rarity)
            self.buttons = [
                Button(pygame.Rect(x, y, button_width, 32), "Add to Deck", self._add_selected_card),
                Button(pygame.Rect(x, y + 38, button_width, 32), "Remove from Deck", self._remove_selected_card),
                Button(pygame.Rect(x, y + 76, button_width, 32), "Auto Fill", self._auto_fill_deck),
                Button(pygame.Rect(x, y + 114, button_width, 32), "Clear Deck", self._clear_deck),
                Button(pygame.Rect(x, y + 160, half, 28), "Rarity -", self._prev_market_rarity),
                Button(pygame.Rect(x + half + 10, y + 160, half, 28), "Rarity +", self._next_market_rarity),
                Button(
                    pygame.Rect(x, y + 194, button_width, 30),
                    f"Buy Random {rarity.title()} (${buy_price})",
                    self._buy_market_single,
                ),
            ]
        elif self.current_tab == "battle":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            btn = Button(pygame.Rect(x, y, button_width, 34), "Start Battle", self._start_battle)
            btn.enabled = self.app.state.deck.is_valid()
            self.buttons = [btn]

        # Unified "Menu" modal buttons (built last so they can be drawn/handled on top)
        self.menu_buttons = []
        if self.menu_open:
            rect = self.menu_panel.rect
            x = rect.x + 40
            y = rect.y + 60
            w = rect.width - 80
            h = 40
            gap = 12
            self.menu_buttons = [
                Button(pygame.Rect(x, y, w, h), "Save Game", self._menu_save),
                Button(pygame.Rect(x, y + (h + gap), w, h), "New Game", self._menu_new_game),
                Button(pygame.Rect(x, y + 2 * (h + gap), w, h), "Exit to Menu", self._menu_exit_to_menu),
                Button(pygame.Rect(x, y + 3 * (h + gap), w, h), "Close", self._menu_close),
            ]

    def _build_tab_btns(self) -> None:
        self.tab_buttons = []
        width, _ = self.app.screen.get_size()
        x0 = 20
        y0 = 8
        btn_w = 120
        btn_h = 32
        gap = 12
        # Wrap tabs to multiple rows if needed.
        tab_ids = list(self.tabs) + ["menu"]
        per_row = max(1, (width - x0 * 2) // (btn_w + gap))
        for i, tab in enumerate(tab_ids):
            row = i // per_row
            col = i % per_row
            rect = pygame.Rect(x0 + col * (btn_w + gap), y0 + row * (btn_h + 8), btn_w, btn_h)
            label = "Menu" if tab == "menu" else tab.title()
            self.tab_buttons.append(Button(rect, label, lambda t=tab: self._switch_tab(t)))

    def _switch_tab(self, tab: str) -> None:
        if tab == "menu":
            self.menu_open = not self.menu_open
            # Close other overlays when the menu is opened.
            if self.menu_open:
                self.manage_card_book_open = False
            self._build_buttons()
            return
        if tab != "manage":
            self.manage_card_book_open = False
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

    def _menu_save(self) -> None:
        self.app.save_game()
        self.menu_open = False
        self._build_buttons()

    def _menu_new_game(self) -> None:
        # This recreates scenes; no further UI work needed here.
        self.app.start_new_game()

    def _menu_exit_to_menu(self) -> None:
        self.menu_open = False
        self._build_buttons()
        self.app.switch_scene("menu")

    def _menu_close(self) -> None:
        self.menu_open = False
        self._build_buttons()

    def _set_product(self, product: str) -> None:
        if product in self.products:
            self.product_index = self.products.index(product)
            if self.current_tab == "manage":
                self._build_buttons()

    def _adjust_price(self, delta: int) -> None:
        product = self.products[self.product_index]
        price_attr = self._price_attr_for_product(product)
        if not price_attr:
            return
        current = getattr(self.app.state.prices, price_attr)
        setattr(self.app.state.prices, price_attr, max(1, current + delta))
        if self.current_tab == "manage":
            self._build_buttons()

    def _price_attr_for_product(self, product: str) -> str | None:
        if product == "booster":
            return "booster"
        if product == "deck":
            return "deck"
        if product.startswith("single_"):
            return product
        return None

    def _card_value(self, rarity: str) -> int:
        prices = self.app.state.prices
        return {
            "common": prices.single_common,
            "uncommon": prices.single_uncommon,
            "rare": prices.single_rare,
            "epic": prices.single_epic,
            "legendary": prices.single_legendary,
        }.get(rarity, prices.single_common)

    def _market_buy_price(self, rarity: str) -> int:
        return self._card_value(rarity)

    def _prev_market_rarity(self) -> None:
        self.market_rarity_index = (self.market_rarity_index - 1) % len(RARITIES)
        self._build_buttons()

    def _next_market_rarity(self) -> None:
        self.market_rarity_index = (self.market_rarity_index + 1) % len(RARITIES)
        self._build_buttons()

    def _buy_market_single(self) -> None:
        rarity = RARITIES[self.market_rarity_index]
        price = self._market_buy_price(rarity)
        if self.app.state.money < price:
            return
        pool = [cid for cid, c in CARD_INDEX.items() if c.rarity == rarity]
        if not pool:
            return
        self.app.state.money -= price
        card_id = self.app.rng.choice(pool)
        self.app.state.collection.add(card_id, 1)
        self.selected_card_id = card_id
        self._build_buttons()

    def _selected_single_product(self) -> str:
        product = self.products[self.product_index]
        if product.startswith("single_"):
            return product
        return "single_common"

    def _wholesale_cost(self, product: str, qty: int) -> int:
        prices = self.app.state.prices
        if product == "booster":
            retail = prices.booster
        elif product == "deck":
            retail = prices.deck
        elif product.startswith("single_"):
            retail = getattr(prices, product, prices.single_common)
        else:
            retail = 1
        return max(1, int(round(retail * 0.6 * qty)))

    def _add_selected_card(self) -> None:
        if not self.selected_card_id:
            return
        owned = self.app.state.collection.get(self.selected_card_id)
        in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
        if owned <= in_deck:
            return
        self.app.state.deck.add(self.selected_card_id)

    def _remove_selected_card(self) -> None:
        if not self.selected_card_id:
            return
        self.app.state.deck.remove(self.selected_card_id)

    def _auto_fill_deck(self) -> None:
        self.app.state.deck.quick_fill(self.app.state.collection)

    def _clear_deck(self) -> None:
        self.app.state.deck.cards.clear()

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
            listed = ""
            if getattr(stock, "cards", None):
                listed = " (listed)"
            label = f"Shelf ({x},{y}) - {stock.product} x{stock.qty}{listed}"
            items.append(ScrollItem(key, label, stock))
        self.shelf_list.items = items
        self.shelf_list.on_select = self._select_shelf

    def _select_shelf(self, item: ScrollItem) -> None:
        self.selected_shelf_key = item.key
        if self.current_tab == "manage":
            self._build_buttons()
        if self.current_tab == "manage":
            self._build_buttons()

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
        # If this shelf is holding specific listed cards, don't overwrite with bulk stock.
        if getattr(shelf, "cards", None) and shelf.cards:
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
        if hasattr(shelf, "cards"):
            shelf.cards.clear()
        shelf.qty += to_add
        self._refresh_shelves()

    def _can_list_selected_card_to_shelf(self) -> bool:
        if not self.selected_shelf_key or not self.selected_card_id:
            return False
        layout = self.app.state.shop_layout
        shelf = layout.shelf_stocks.get(self.selected_shelf_key)
        if not shelf:
            return False
        if shelf.qty >= shelf.max_qty:
            return False
        # Don't sell below what's committed in the battle deck.
        owned = self.app.state.collection.get(self.selected_card_id)
        in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
        if owned <= in_deck:
            return False
        card = CARD_INDEX[self.selected_card_id]
        product = f"single_{card.rarity}"
        # Only allow listing on empty shelves, or shelves already listing the same rarity.
        cards = getattr(shelf, "cards", [])
        if shelf.qty > 0 and not cards:
            return False
        if shelf.qty > 0 and shelf.product != product:
            return False
        return True

    def _list_selected_card_to_shelf(self) -> None:
        if not self._can_list_selected_card_to_shelf():
            return
        layout = self.app.state.shop_layout
        shelf = layout.shelf_stocks.get(self.selected_shelf_key)  # type: ignore[arg-type]
        if not shelf:
            return
        card_id = self.selected_card_id
        card = CARD_INDEX[card_id]
        product = f"single_{card.rarity}"
        if not hasattr(shelf, "cards"):
            return
        if not self.app.state.collection.remove(card_id, 1):
            return
        shelf.cards.append(card_id)
        shelf.product = product
        shelf.qty = len(shelf.cards)
        self._refresh_shelves()
        self._build_buttons()

    def _order_boosters(self) -> None:
        qty = 12
        cost = self._wholesale_cost("booster", qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(qty, 0, {}, cost, 0, self.app.state.time_seconds + 30.0)
        self.app.state.pending_orders.append(order)
        self._refresh_shelves()
        self._build_buttons()

    def _order_decks(self) -> None:
        qty = 4
        cost = self._wholesale_cost("deck", qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(0, qty, {}, cost, 0, self.app.state.time_seconds + 30.0)
        self.app.state.pending_orders.append(order)
        self._refresh_shelves()
        self._build_buttons()

    def _order_singles_current(self) -> None:
        product = self._selected_single_product()
        rarity = product.replace("single_", "")
        qty = 10
        cost = self._wholesale_cost(product, qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        order = InventoryOrder(0, 0, {rarity: qty}, cost, 0, self.app.state.time_seconds + 30.0)
        self.app.state.pending_orders.append(order)
        self._refresh_shelves()
        self._build_buttons()

    def _init_assets(self) -> None:
        """Initialize shop assets."""
        shop_assets = get_shop_asset_manager()
        shop_assets.init()
        self._update_shop_viewport(rescale=True)

    def _set_object(self, kind: str) -> None:
        self.selected_object = kind

    def on_enter(self) -> None:
        self._build_buttons()
        if self.current_tab == "manage":
            self._refresh_shelves()

    def start_day(self) -> None:
        if self.day_running:
            return
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
        # Menu modal captures input (except the unified top tabs).
        if self.menu_open:
            for btn in self.tab_buttons:
                btn.handle_event(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._menu_close()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self.menu_panel.rect.collidepoint(event.pos):
                    self._menu_close()
                    return
            for button in self.menu_buttons:
                button.handle_event(event)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            ended_drag = self._drag_target
            ended_resize = self._resize_target
            self._drag_target = None
            self._resize_target = None
            # Finalize drag latency stats.
            if ended_drag:
                avg = (self._drag_latency_sum / self._drag_latency_frames) if self._drag_latency_frames else 0.0
                self._last_drag_latency_avg = avg
                self._last_drag_latency_max = self._drag_latency_max
            self._drag_latency_sum = 0.0
            self._drag_latency_max = 0.0
            self._drag_latency_frames = 0
            if ended_resize == "shop":
                # Rescale/rebuild floor once at end of resizing.
                self._update_shop_viewport(rescale=True)
            elif ended_drag == "shop":
                # Ensure offsets are correct after drag.
                self._update_shop_viewport(rescale=False)
            return

        # Pointer capture: when dragging/resizing, don't propagate events to underlying UI.
        if self._drag_target or self._resize_target:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hit_drag_handle(event.pos):
                return
        for btn in self.tab_buttons:
            btn.handle_event(event)
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
                # If interacting with the shelf list, don't allow hidden/overlapping buttons to also fire.
                if getattr(event, "pos", None) and self.shelf_list.rect.collidepoint(event.pos):
                    self.shelf_list.handle_event(event)
                    return
                self.shelf_list.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    key = self._select_shelf_at_pos(event.pos)
                    if key:
                        self.selected_shelf_key = key
                        self._build_buttons()
        for button in self.buttons:
            button.handle_event(event)
        if self.current_tab == "deck":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_deck_click(event.pos)
            if event.type == pygame.MOUSEWHEEL:
                self._scroll_card_book(-event.y * 24)
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
        entrance = pygame.Vector2(1.5 * self.tile_px, (SHOP_GRID[1] - 1) * self.tile_px)
        shelves = self.app.state.shop_layout.shelf_tiles()
        if not shelves:
            return
        shelf = self.app.rng.choice(shelves)
        target = pygame.Vector2((shelf[0] + 0.5) * self.tile_px, (shelf[1] + 0.5) * self.tile_px)
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
            customer.target = pygame.Vector2((counter[0] + 0.5) * self.tile_px, (counter[1] + 0.5) * self.tile_px)
            customer.state = "to_counter"
            customer.purchase = self._choose_shelf_purchase()
        elif customer.state == "to_counter":
            if customer.purchase:
                self._process_purchase(customer.purchase)
            exit_pos = pygame.Vector2(1.5 * self.tile_px, (SHOP_GRID[1] - 0.5) * self.tile_px)
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
        if product.startswith("single_") and getattr(stock, "cards", None):
            if stock.cards:
                sold = self.app.rng.choice(stock.cards)
                stock.cards.remove(sold)
                stock.qty = len(stock.cards)
            else:
                stock.qty -= 1
        else:
            stock.qty -= 1
        if stock.qty <= 0:
            stock.qty = 0
            stock.product = "empty"
            if hasattr(stock, "cards"):
                stock.cards.clear()
        self.app.state.money += price
        self.app.state.last_summary.revenue += price
        self.app.state.last_summary.units_sold += 1

    def _tile_at_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        if not self._shop_inner_rect().collidepoint(pos):
            return None
        x, y = pos
        y_off = self._shop_y_offset
        y = y - y_off
        x = x - self._shop_x_offset
        if x < 0:
            return None
        if x > SHOP_GRID[0] * self.tile_px or y > SHOP_GRID[1] * self.tile_px:
            return None
        return (x // self.tile_px, y // self.tile_px)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        dragging_shop = self._drag_target == "shop" or self._resize_target == "shop"
        if dragging_shop and self._shop_drag_snapshot is not None:
            # Fast path: reuse cached shop surface while dragging/resizing.
            if self._resize_target == "shop":
                size = (self.shop_panel.rect.width, self.shop_panel.rect.height)
                now = self.app.state.time_seconds
                if size != self._shop_resize_preview_size and (now - self._shop_resize_preview_time) >= (1 / 20):
                    # Throttle preview rescale to reduce CPU while resizing.
                    self._shop_resize_preview = pygame.transform.scale(self._shop_drag_snapshot, size)
                    self._shop_resize_preview_size = size
                    self._shop_resize_preview_time = now
                preview = self._shop_resize_preview or self._shop_drag_snapshot
                surface.blit(preview, self.shop_panel.rect.topleft)
            else:
                surface.blit(self._shop_drag_snapshot, self.shop_panel.rect.topleft)
            # Outline to indicate live drag/resize.
            pygame.draw.rect(surface, self.theme.colors.accent, self.shop_panel.rect, 2)
        else:
            # Normal full render.
            self.shop_panel.draw(surface, self.theme)
            clip = surface.get_clip()
            surface.set_clip(self._shop_inner_rect())
            self._draw_grid(surface)
            self._draw_objects(surface)
            self._draw_customers(surface)
            self._draw_status(surface)
            surface.set_clip(clip)
            # Capture snapshot once when a shop drag/resize starts.
            if dragging_shop and self._shop_drag_snapshot is None:
                try:
                    self._shop_drag_snapshot = surface.subsurface(self.shop_panel.rect).copy()
                    self._shop_resize_preview = None
                    self._shop_resize_preview_size = (0, 0)
                    self._shop_resize_preview_time = 0.0
                except ValueError:
                    # If subsurface fails (edge cases), skip caching.
                    self._shop_drag_snapshot = None
            # Clear snapshot when not dragging.
            if not dragging_shop:
                self._shop_drag_snapshot = None
                self._shop_resize_preview = None
        self.order_panel.draw(surface, self.theme)
        if self.current_tab == "manage":
            self.stock_panel.draw(surface, self.theme)
            self.inventory_panel.draw(surface, self.theme)
            if self.manage_card_book_open:
                self.book_panel.draw(surface, self.theme)
        if self.current_tab == "deck":
            self.book_panel.draw(surface, self.theme)
            self.deck_panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        for tb in self.tab_buttons:
            tb.draw(surface, self.theme)
        if self.current_tab == "packs":
            self._draw_packs(surface)
        if self.current_tab == "manage":
            self._draw_manage(surface)
            if self.manage_card_book_open:
                self._draw_deck(surface)
        if self.current_tab == "deck":
            self._draw_deck(surface)
        if self.current_tab == "battle":
            self._draw_battle_info(surface)
        if self.menu_open:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            surface.blit(overlay, (0, 0))
            self.menu_panel.draw(surface, self.theme)
            for button in self.menu_buttons:
                button.draw(surface, self.theme)

    def _draw_grid(self, surface: pygame.Surface) -> None:
        y_off = self._shop_y_offset
        x_off = self._shop_x_offset
        if self._floor_surface:
            surface.blit(self._floor_surface, (x_off, y_off))
        else:
            for x in range(SHOP_GRID[0]):
                for y in range(SHOP_GRID[1]):
                    rect = pygame.Rect(
                        x * self.tile_px + x_off,
                        y * self.tile_px + y_off,
                        self.tile_px,
                        self.tile_px,
                    )
                    pygame.draw.rect(surface, (40, 42, 50), rect)
                    pygame.draw.rect(surface, (30, 32, 38), rect, 1)

    def _draw_objects(self, surface: pygame.Surface) -> None:
        shop_assets = get_shop_asset_manager()
        y_off = self._shop_y_offset
        x_off = self._shop_x_offset
        for obj in self.app.state.shop_layout.objects:
            rect = pygame.Rect(
                obj.tile[0] * self.tile_px + x_off,
                obj.tile[1] * self.tile_px + y_off,
                self.tile_px,
                self.tile_px,
            )
            
            # Try to get furniture sprite
            sprite = shop_assets.get_furniture_sprite(obj.kind, (self.tile_px, self.tile_px))
            
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
        customer_size = max(32, min(int(self.tile_px * 0.85), 64))
        y_off = self._shop_y_offset
        x_off = self._shop_x_offset
        for customer in self.customers:
            if customer.done:
                continue
            sprite = shop_assets.get_customer_sprite(customer.sprite_id, (customer_size, customer_size))
            if sprite:
                sprite_x = int(customer.pos.x - customer_size // 2 + x_off)
                sprite_y = int(customer.pos.y - customer_size + 8 + y_off)
                surface.blit(sprite, (sprite_x, sprite_y))
            else:
                rect = pygame.Rect(customer.pos.x - 10 + x_off, customer.pos.y - 10 + y_off, 20, 20)
                pygame.draw.rect(surface, (200, 200, 120), rect)

    def _draw_status(self, surface: pygame.Surface) -> None:
        rect = self.shop_panel.rect
        inner = self._shop_inner_rect()
        x_off = rect.x + 14
        # Bottom-left inside the shop window (avoid the header).
        y_base = max(inner.y + 6, rect.bottom - 66)
        text = self.theme.font.render(
            f"Day {self.app.state.day} | Money ${self.app.state.money}", True, self.theme.colors.text
        )
        surface.blit(text, (x_off, y_base))
        status_y = y_base + 26
        if self.day_running:
            timer_text = self.theme.font_small.render(
                f"Day progress: {int(self.day_timer)}s/{int(self.day_duration)}s", True, self.theme.colors.muted
            )
            surface.blit(timer_text, (x_off, status_y))
        else:
            summary = self.app.state.last_summary
            summary_text = self.theme.font_small.render(
                f"+${summary.revenue} | {summary.units_sold} sold | {summary.customers} customers",
                True, self.theme.colors.muted,
            )
            surface.blit(summary_text, (x_off, status_y))

    def _draw_packs(self, surface: pygame.Surface) -> None:
        asset_mgr = get_asset_manager()
        y = SHOP_GRID[1] * self.tile_px + self._shop_y_offset + 60
        for idx, card_id in enumerate(self.revealed_cards):
            rect = pygame.Rect(20 + idx * 130, y, 120, 160)
            if idx < self.reveal_index:
                card = CARD_INDEX[card_id]
                bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
                surface.blit(bg, rect.topleft)
                sprite = asset_mgr.get_card_sprite(card_id, (64, 64))
                if sprite:
                    surface.blit(sprite, (rect.x + 28, rect.y + 15))
                rarity_color = getattr(self.theme.colors, f"card_{card.rarity}")
                draw_glow_border(surface, rect, rarity_color, border_width=2, glow_radius=4, glow_alpha=80)
                id_text = self.theme.font_small.render(card.card_id.upper(), True, self.theme.colors.muted)
                surface.blit(id_text, (rect.x + 6, rect.y + 4))
                name = self.theme.font_small.render(card.name[:12], True, self.theme.colors.text)
                surface.blit(name, (rect.x + 6, rect.y + 20))
                desc = (card.description[:18] + "...") if len(card.description) > 18 else card.description
                desc_text = self.theme.font_small.render(desc, True, self.theme.colors.muted)
                surface.blit(desc_text, (rect.x + 6, rect.y + 100))
                stats = self.theme.font_small.render(
                    f"{card.cost}/{card.attack}/{card.health}", True, self.theme.colors.text
                )
                surface.blit(stats, (rect.x + 6, rect.bottom - 18))

    def _select_shelf_at_pos(self, pos: tuple[int, int]) -> str | None:
        if not self._shop_inner_rect().collidepoint(pos):
            return None
        y_off = self._shop_y_offset
        x_off = self._shop_x_offset
        for obj in self.app.state.shop_layout.objects:
            if obj.kind != "shelf":
                continue
            rect = pygame.Rect(
                obj.tile[0] * self.tile_px + x_off,
                obj.tile[1] * self.tile_px + y_off,
                self.tile_px,
                self.tile_px,
            )
            if rect.collidepoint(pos):
                return self.app.state.shop_layout._key(obj.tile)
        return None

    def _hit_drag_handle(self, pos: tuple[int, int]) -> bool:
        if self._start_drag_or_resize(self.order_panel.rect, "order", pos):
            return True
        if self.current_tab == "manage":
            if self._start_drag_or_resize(self.stock_panel.rect, "stock", pos):
                return True
            if self._start_drag_or_resize(self.inventory_panel.rect, "inventory", pos):
                return True
            if self._start_drag_or_resize(self.shelf_list.rect, "list", pos):
                return True
        if self.current_tab == "deck" or (self.current_tab == "manage" and self.manage_card_book_open):
            if self._start_drag_or_resize(self.book_panel.rect, "book", pos):
                return True
            if self.current_tab == "deck":
                if self._start_drag_or_resize(self.deck_panel.rect, "deck", pos):
                    return True
        if self._start_drag_or_resize(self.shop_panel.rect, "shop", pos):
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
            if self._drag_target == "order":
                rect = self.order_panel.rect
            elif self._drag_target == "stock":
                rect = self.stock_panel.rect
            elif self._drag_target == "inventory":
                rect = self.inventory_panel.rect
            elif self._drag_target == "book":
                rect = self.book_panel.rect
            elif self._drag_target == "deck":
                rect = self.deck_panel.rect
            elif self._drag_target == "shop":
                rect = self.shop_panel.rect
            else:
                rect = self.shelf_list.rect
            expected = pygame.Vector2(mouse.x - self._drag_offset.x, mouse.y - self._drag_offset.y)
            rect.x = int(expected.x)
            rect.y = int(expected.y)
            rect = self._clamp_rect_target(rect, width, height, self._drag_target)
            # Track drag latency (distance between expected and applied topleft).
            actual = pygame.Vector2(rect.x, rect.y)
            err = (actual - expected).length()
            self._drag_latency_sum += err
            self._drag_latency_max = max(self._drag_latency_max, err)
            self._drag_latency_frames += 1
            if self._drag_target == "order":
                self.order_panel.rect = rect
                self._relayout_buttons_only()
            elif self._drag_target == "stock":
                self.stock_panel.rect = rect
                self._relayout_buttons_only()
            elif self._drag_target == "inventory":
                self.inventory_panel.rect = rect
            elif self._drag_target == "book":
                self.book_panel.rect = rect
                self._relayout_buttons_only()
            elif self._drag_target == "deck":
                self.deck_panel.rect = rect
            elif self._drag_target == "shop":
                self.shop_panel.rect = rect
                self._update_shop_viewport(rescale=False)
            else:
                self.shelf_list.rect = rect
        if self._resize_target:
            if self._resize_target == "order":
                rect = self.order_panel.rect
            elif self._resize_target == "stock":
                rect = self.stock_panel.rect
            elif self._resize_target == "inventory":
                rect = self.inventory_panel.rect
            elif self._resize_target == "book":
                rect = self.book_panel.rect
            elif self._resize_target == "deck":
                rect = self.deck_panel.rect
            elif self._resize_target == "shop":
                rect = self.shop_panel.rect
            else:
                rect = self.shelf_list.rect
            delta = mouse - self._resize_start
            rect.width = int(self._resize_origin.x + delta.x)
            rect.height = int(self._resize_origin.y + delta.y)
            rect = self._clamp_rect_target(rect, width, height, self._resize_target)
            if self._resize_target == "order":
                self.order_panel.rect = rect
                self._relayout_buttons_only()
            elif self._resize_target == "stock":
                self.stock_panel.rect = rect
                self._relayout_buttons_only()
            elif self._resize_target == "inventory":
                self.inventory_panel.rect = rect
            elif self._resize_target == "book":
                self.book_panel.rect = rect
                self._relayout_buttons_only()
            elif self._resize_target == "deck":
                self.deck_panel.rect = rect
            elif self._resize_target == "shop":
                self.shop_panel.rect = rect
                self._update_shop_viewport(rescale=False)
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
        price_attr = self._price_attr_for_product(product)
        price_value = getattr(self.app.state.prices, price_attr) if price_attr else 0
        prod_text = self.theme.font_small.render(
            f"Product: {product} | Price: ${price_value}", True, self.theme.colors.text
        )
        surface.blit(prod_text, (self.stock_panel.rect.x + 20, self.stock_panel.rect.bottom + 8))
        selected = self.selected_shelf_key or "None"
        sel_text = self.theme.font_small.render(f"Selected shelf: {selected}", True, self.theme.colors.muted)
        surface.blit(sel_text, (self.stock_panel.rect.x + 20, self.stock_panel.rect.bottom + 26))
        if self.selected_card_id:
            c = CARD_INDEX[self.selected_card_id]
            owned = self.app.state.collection.get(self.selected_card_id)
            in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
            card_text = self.theme.font_small.render(
                f"Selected card: {c.name} ({c.card_id}) | Owned {owned} | In deck {in_deck}",
                True,
                self.theme.colors.muted,
            )
            surface.blit(card_text, (self.stock_panel.rect.x + 20, self.stock_panel.rect.bottom + 44))
        inv = self.app.state.inventory
        pending = sum(o.boosters + o.decks + sum(o.singles.values()) for o in self.app.state.pending_orders)
        inv_lines = [
            f"Boosters: {inv.booster_packs}",
            f"Decks: {inv.decks}",
            f"Pending items: {pending}",
        ] + [f"{r.title()}: {inv.singles.get(r, 0)}" for r in RARITIES]
        y = self.inventory_panel.rect.y + 36
        for line in inv_lines:
            text = self.theme.font_small.render(line, True, self.theme.colors.muted)
            surface.blit(text, (self.inventory_panel.rect.x + 20, y))
            y += 18

        # Selected shelf details
        if self.selected_shelf_key:
            stock = self.app.state.shop_layout.shelf_stocks.get(self.selected_shelf_key)
            if stock:
                y += 6
                hdr = self.theme.font_small.render("Selected shelf contents", True, self.theme.colors.text)
                surface.blit(hdr, (self.inventory_panel.rect.x + 20, y))
                y += 18
                prod_line = self.theme.font_small.render(
                    f"{stock.product} x{stock.qty}/{stock.max_qty}",
                    True,
                    self.theme.colors.muted,
                )
                surface.blit(prod_line, (self.inventory_panel.rect.x + 20, y))
                y += 18
                if getattr(stock, "cards", None):
                    if stock.cards:
                        counts: dict[str, int] = {}
                        for cid in stock.cards:
                            counts[cid] = counts.get(cid, 0) + 1
                        parts: list[str] = []
                        for cid, qty in sorted(counts.items(), key=lambda kv: CARD_INDEX[kv[0]].name)[:4]:
                            c = CARD_INDEX[cid]
                            parts.append(f"{c.name}({cid})x{qty}")
                        more = max(0, len(counts) - 4)
                        if more:
                            parts.append(f"+{more} more")
                        cards_line = self.theme.font_small.render("Cards: " + ", ".join(parts), True, self.theme.colors.muted)
                        surface.blit(cards_line, (self.inventory_panel.rect.x + 20, y))
                        y += 18
                    else:
                        cards_line = self.theme.font_small.render("Cards: (none listed)", True, self.theme.colors.muted)
                        surface.blit(cards_line, (self.inventory_panel.rect.x + 20, y))
                        y += 18

        # Pending order queue with ETA
        if self.app.state.pending_orders:
            y += 6
            hdr = self.theme.font_small.render("Incoming (ETA)", True, self.theme.colors.text)
            surface.blit(hdr, (self.inventory_panel.rect.x + 20, y))
            y += 18
            now = self.app.state.time_seconds
            for order in sorted(self.app.state.pending_orders, key=lambda o: o.deliver_at):
                eta = max(0, int(order.deliver_at - now))
                parts: list[str] = []
                if order.boosters:
                    parts.append(f"{order.boosters} boosters")
                if order.decks:
                    parts.append(f"{order.decks} decks")
                for r, amt in order.singles.items():
                    if amt:
                        parts.append(f"{amt} {r}")
                label = ", ".join(parts) if parts else "order"
                line = self.theme.font_small.render(f"{eta:>2}s - {label}", True, self.theme.colors.muted)
                surface.blit(line, (self.inventory_panel.rect.x + 20, y))
                y += 18

    def _draw_deck(self, surface: pygame.Surface) -> None:
        asset_mgr = get_asset_manager()
        # Card book
        row_height = 88
        content_rect = self._card_book_content_rect()
        entries = self.app.state.collection.entries(None)
        total_height = len(entries) * row_height
        max_scroll = max(0, total_height - content_rect.height)
        self.card_book_scroll = max(0, min(self.card_book_scroll, max_scroll))

        surface.set_clip(content_rect)
        start_idx = max(0, (self.card_book_scroll // row_height) - 1)
        visible = (content_rect.height // row_height) + 3
        end_idx = min(len(entries), start_idx + visible)
        y = content_rect.y - self.card_book_scroll + start_idx * row_height
        for entry in entries[start_idx:end_idx]:
            card = CARD_INDEX[entry.card_id]
            row_rect = pygame.Rect(content_rect.x, y, content_rect.width, row_height - 8)
            if row_rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(surface, self.theme.colors.panel_alt, row_rect)
            if self.selected_card_id == entry.card_id:
                pygame.draw.rect(surface, self.theme.colors.accent, row_rect, 2)
            # Card icon with rarity glow
            icon_rect = pygame.Rect(row_rect.x + 6, row_rect.y + 6, 56, 56)
            bg = asset_mgr.create_card_background(card.rarity, (icon_rect.width, icon_rect.height))
            surface.blit(bg, icon_rect.topleft)
            rarity_color = getattr(self.theme.colors, f"card_{card.rarity}")
            draw_glow_border(surface, icon_rect, rarity_color, border_width=2, glow_radius=3, glow_alpha=70)
            art = asset_mgr.get_card_sprite(entry.card_id, (48, 48))
            if art:
                surface.blit(art, (icon_rect.x + 4, icon_rect.y + 4))
            # Text info
            name = self.theme.font_small.render(f"{card.name} ({card.card_id})", True, self.theme.colors.text)
            surface.blit(name, (row_rect.x + 68, row_rect.y + 6))
            desc = (card.description[:60] + "...") if len(card.description) > 60 else card.description
            desc_text = self.theme.font_small.render(desc, True, self.theme.colors.muted)
            surface.blit(desc_text, (row_rect.x + 68, row_rect.y + 24))
            stats = self.theme.font_small.render(
                f"{card.rarity.title()} | Cost {card.cost} | {card.attack}/{card.health}",
                True,
                self.theme.colors.text,
            )
            surface.blit(stats, (row_rect.x + 68, row_rect.y + 42))
            value = self._card_value(card.rarity)
            qty_text = self.theme.font_small.render(
                f"Qty {entry.qty} | Value ${value}",
                True,
                self.theme.colors.muted,
            )
            surface.blit(qty_text, (row_rect.x + 68, row_rect.y + 60))
            y += row_height
        surface.set_clip(None)

        if self.current_tab != "deck":
            return

        # Deck list
        deck_rect = self.deck_panel.rect
        deck_title = self.theme.font_small.render(
            f"Deck ({self.app.state.deck.total()}/20)", True, self.theme.colors.text
        )
        surface.blit(deck_title, (deck_rect.x + 12, deck_rect.y + 12))
        y = deck_rect.y + 36
        for card_id, qty in self.app.state.deck.summary():
            card = CARD_INDEX[card_id]
            line = self.theme.font_small.render(f"{card.name} x{qty}", True, self.theme.colors.text)
            surface.blit(line, (deck_rect.x + 12, y))
            y += 18

    def _handle_deck_click(self, pos: tuple[int, int]) -> None:
        content_rect = self._card_book_content_rect()
        if content_rect.collidepoint(pos):
            row_height = 88
            idx = int((pos[1] - content_rect.y + self.card_book_scroll) // row_height)
            entries = self.app.state.collection.entries(None)
            if 0 <= idx < len(entries):
                self.selected_card_id = entries[idx].card_id
                self._build_buttons()
                return

    def _scroll_card_book(self, delta: int) -> None:
        content_height = self._card_book_content_rect().height
        total_height = len(self.app.state.collection.entries(None)) * 88
        max_scroll = max(0, total_height - content_height)
        self.card_book_scroll = max(0, min(self.card_book_scroll + delta, max_scroll))

    def _draw_battle_info(self, surface: pygame.Surface) -> None:
        info = [
            "Battle runs in a focused scene.",
            "Press ESC to return to the shop.",
            f"Deck size: {self.app.state.deck.total()}/20",
        ]
        y = self.order_panel.rect.bottom + 8
        for line in info:
            text = self.theme.font_small.render(line, True, self.theme.colors.muted)
            surface.blit(text, (self.order_panel.rect.x + 20, y))
            y += 18
