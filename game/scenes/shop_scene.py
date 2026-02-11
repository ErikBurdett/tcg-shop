from __future__ import annotations

from dataclasses import dataclass
import math

import pygame

from game.config import (
    SHOP_GRID,
    TILE_SIZE,
    DAY_DURATION_SECONDS,
    NIGHT_DURATION_SECONDS,
    CUSTOMER_BROWSE_TIME_RANGE,
    CUSTOMER_PAY_TIME_RANGE,
    CUSTOMER_SPAWN_RETRY_DELAY,
    CUSTOMER_SPEED_TILES_PER_S,
    MAX_CUSTOMERS_ACTIVE,
    MAX_CUSTOMERS_SPAWNED_PER_DAY,
    MAX_CUSTOMER_SPAWNS_PER_FRAME,
)
from game.core.scene import Scene
from game.sim.economy import customer_spawn_interval, choose_purchase
from game.sim.economy_rules import effective_sale_price, xp_from_sale
from game.sim.economy_rules import xp_from_sell
from game.sim.skill_tree import get_default_skill_tree
from game.sim.economy_rules import fixture_cost
from game.sim.skill_tree import SkillNodeDef
from game.sim.progression import xp_to_next
from game.ui.widgets import Button, Panel, ScrollList, ScrollItem
from game.sim.inventory import RARITIES, InventoryOrder
from game.cards.card_defs import CARD_INDEX
from game.cards.pack import open_booster
from game.assets import get_asset_manager
from game.assets.shop import get_shop_asset_manager
from game.ui.effects import draw_glow_border
from game.ui.layout import anchor_rect
from game.sim.actors import Staff, notify_shelf_change, update_staff
from game.config import Prices
from game.sim.skill_tree import Modifiers
from game.sim.packs_catalog import PACK_TYPES, pack_count
from game.sim.staff_xp import StaffXpEventType, award_staff_xp_total
from game.sim.forecast import RestockSuggestion, compute_restock_suggestions, top_stockout_shelves

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
    wait_s: float = 0.0


class ShopScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        # Hide legacy scene nav; use custom unified tabs instead.
        self.show_top_bar = False
        self.top_buttons.clear()
        # Day/Night cycle (can be paused/resumed)
        self.cycle_active = False
        self.cycle_paused = False
        self.cycle_phase: str = "day"  # "day" | "night"
        self.phase_timer = 0.0
        self.day_duration = float(DAY_DURATION_SECONDS)
        self.night_duration = float(NIGHT_DURATION_SECONDS)
        self.day_transition_timer = 0.0  # fade-out tint when night -> day
        self._autosaved_this_night = False
        self.customers: list[Customer] = []
        self.customer_schedule: list[float] = []
        self.spawned = 0
        self.selected_object = "shelf"
        self.current_tab = "shop"
        self.tabs = ["shop", "packs", "sell", "deck", "manage", "stats", "skills", "battle"]
        self.tab_buttons: list[Button] = []
        self.mobile_nav_open = False
        self._mobile_breakpoint = 980
        self.revealed_cards: list[str] = []
        self.reveal_index = 0
        # Pack opening animation state (Packs tab)
        self._pack_open_queue: int = 0
        self._pack_anim_stage: str = "idle"  # idle|shake|flash|reveal|done
        self._pack_anim_stage_t: float = 0.0
        self._pack_anim_reveal_t: float = 0.0
        self._pack_anim_revealed: int = 0
        self._pack_anim_cooldown: float = 0.0  # prevents starting multiple packs in one frame when skipping
        self._pack_surf: pygame.Surface | None = None
        self._pack_flash_surf: pygame.Surface | None = None
        self._pack_card_back: pygame.Surface | None = None
        self._pack_card_faces: list[pygame.Surface] = []
        self._pack_slots_alpha: int = 0
        # Packs tab state
        self.pack_list = ScrollList(pygame.Rect(0, 0, 100, 100), [])
        self.selected_pack_id: str = "booster"
        self._pack_counts_snapshot: dict[str, int] = {}
        self._pack_row_text: dict[str, str] = {}
        self._pack_row_surf: dict[str, pygame.Surface] = {}
        # Sell tab state
        self.sell_mode: str = "items"  # "items" | "cards"
        self.sell_item: str = "booster"  # "booster" | "deck"
        self.sell_rarity_index: int = 0
        self._sell_pending: dict[str, object] | None = None
        self._sell_receipt_lines: list[str] = []
        # Forecast/analytics UI cache (throttled).
        self._forecast_next_update_t: float = 0.0
        self._forecast_suggestions: list[RestockSuggestion] = []
        self._forecast_stockouts: list[tuple[str, int]] = []
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
        self.skills_panel = Panel(pygame.Rect(0, 0, 720, 560), "Skills")
        self.stats_panel = Panel(pygame.Rect(0, 0, 820, 560), "Analytics")
        self.shelf_list = ScrollList(pygame.Rect(0, 0, 100, 100), [])
        self._shelf_value_cache: dict[str, int] = {}
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
        # Staff actor (auto-restock) + render cache for level label.
        self.staff = Staff(pos=(10.5, 7.5))
        self._staff_level_cached = -1
        self._staff_level_text: pygame.Surface | None = None
        self._staff_blocked_tiles: set[tuple[int, int]] = set()
        self._staff_blocked_count = -1
        self._staff_xp_toast_accum = 0
        self._staff_xp_toast_timer = 0.0
        # Skills UI state (UI-only; not saved).
        self._skills_pan = pygame.Vector2(0, 0)
        self._skills_panning = False
        self._skills_pan_last = pygame.Vector2(0, 0)
        self._skills_node_size = (168, 56)
        tree = get_default_skill_tree()
        # Precompute edges (prereq -> node) for drawing.
        self._skills_edges: list[tuple[str, str]] = []
        for sid, node in tree.nodes.items():
            for pr in node.prereqs:
                self._skills_edges.append((pr.skill_id, sid))
        self._skills_nodes: list[SkillNodeDef] = list(tree.nodes.values())
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
        if self.cycle_active:
            remain = (self.day_duration - self.phase_timer) if self.cycle_phase == "day" else (self.night_duration - self.phase_timer)
            state = "PAUSED" if self.cycle_paused else "RUN"
            return [f"Cycle: {self.cycle_phase.upper()} ({state}) | {max(0.0, remain):0.1f}s left"]
        return []

    def _build_day_buttons(self) -> None:
        """ShopScene owns its own shell controls; suppress legacy global day buttons."""
        self.day_buttons = []

    def _sync_day_buttons(self) -> None:
        return

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
            skills_rect = pygame.Rect(
                self._panel_padding,
                base_top + self._panel_padding,
                max(720, int(width * 0.62)),
                max(520, int(height * 0.62)),
            )
            stats_rect = pygame.Rect(
                self._panel_padding,
                base_top + self._panel_padding,
                max(820, int(width * 0.70)),
                max(520, int(height * 0.62)),
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
            skills_rect = self._clamp_rect(self.skills_panel.rect.copy(), width, height)
            stats_rect = self._clamp_rect(self.stats_panel.rect.copy(), width, height)
        self.order_panel = Panel(order_rect, "Ordering")
        self.stock_panel = Panel(stock_rect, "Stocking")
        self.inventory_panel = Panel(inv_rect, "Inventory")
        self.book_panel = Panel(book_rect, "Card Book")
        self.deck_panel = Panel(deck_rect, "Deck")
        self.shop_panel = Panel(shop_rect, "Shop")
        self.skills_panel = Panel(skills_rect, "Skills")
        self.stats_panel = Panel(stats_rect, "Analytics")
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
        elif target == "skills":
            min_w = 600
            min_h = 420
        elif target == "stats":
            min_w = 620
            min_h = 420
        rect.width = max(min_w, min(rect.width, width - 40))
        rect.height = max(min_h, min(rect.height, height - self._top_bar_height - 40))
        rect.x = max(8, min(rect.x, width - rect.width - 8))
        rect.y = max(self._top_bar_height + 8, min(rect.y, height - rect.height - 8))
        return rect

    def _tooltip_sources(self) -> list[Button]:
        out: list[Button] = []
        out.extend(self.day_buttons)
        out.extend(self.tab_buttons)
        out.extend(self.buttons)
        if self.menu_open:
            out.extend(self.menu_buttons)
        return out

    def _tooltip_bounds(self, pos: tuple[int, int]) -> pygame.Rect | None:
        # If the tooltip is coming from inside the shop viewport, clamp within that viewport.
        try:
            inner = self._shop_inner_rect()
            if inner.collidepoint(pos):
                return inner
        except Exception:
            return None
        return None

    def _skills_content_rect(self) -> pygame.Rect:
        r = self.skills_panel.rect
        return pygame.Rect(r.x + 12, r.y + 36, r.width - 24, r.height - 48)

    def _skill_at_pos(self, pos: tuple[int, int]) -> str | None:
        if not self.skills_panel.rect.collidepoint(pos):
            return None
        content = self._skills_content_rect()
        if not content.collidepoint(pos):
            return None
        local = pygame.Vector2(pos[0] - content.x, pos[1] - content.y) - self._skills_pan
        w, h = self._skills_node_size
        for node in self._skills_nodes:
            nx, ny = node.pos
            rect = pygame.Rect(int(nx - w // 2), int(ny - h // 2), w, h)
            if rect.collidepoint((int(local.x), int(local.y))):
                return node.skill_id
        return None

    def _extra_tooltip_text(self, pos: tuple[int, int]) -> str | None:
        for rect, label, value in self._top_info_rects():
            if rect.collidepoint(pos):
                if label == "Money":
                    return "Current cash on hand. Used for orders, fixtures, and market buys."
                if label == "Day":
                    return "Current in-game day. Daily summaries and trends are keyed by this value."
                if label == "Cycle":
                    return "Day/Night simulation state. Pause to manage inventory without time pressure."
                if label == "XP":
                    return "Shopkeeper progression. Gain XP from sales and battles to unlock skill points."
                if label == "Staff":
                    return "Staff auto-restock progression. Levels improve utility over time."
                return f"{label}: {value}"

        if self.current_tab == "shop":
            tile = self._tile_at_pos(pos)
            if tile:
                obj = self.app.state.shop_layout.object_at(tile)
                if obj and obj.kind == "shelf":
                    key = self.app.state.shop_layout._key(tile)
                    stock = self.app.state.shop_layout.shelf_stocks.get(key)
                    if stock:
                        return f"Shelf {key}: {stock.product} {stock.qty}/{stock.max_qty}"
                if obj:
                    return f"{obj.kind.title()} at {tile}"
                return f"Empty tile {tile} (click to place {self.selected_object})"
        if self.current_tab == "skills":
            sid = self._skill_at_pos(pos)
            if not sid:
                return None
            tree = get_default_skill_tree()
            node = tree.nodes[sid]
            r = self.app.state.skills.rank(sid)
            ok, reason = self.app.state.skills.can_rank_up(tree, sid, self.app.state.progression)
            prereq_txt = ""
            if node.prereqs:
                prereq_txt = " Prereqs: " + ", ".join(
                    f"{tree.nodes[p.skill_id].name} {p.rank}" for p in node.prereqs
                )
            effect_txt = ""
            if node.mods_per_rank.sell_price_pct:
                effect_txt += f" Sell +{node.mods_per_rank.sell_price_pct*100:.1f}%/rank."
            if node.mods_per_rank.sales_xp_pct:
                effect_txt += f" Sales XP +{node.mods_per_rank.sales_xp_pct*100:.1f}%/rank."
            if node.mods_per_rank.battle_xp_pct:
                effect_txt += f" Battle XP +{node.mods_per_rank.battle_xp_pct*100:.1f}%/rank."
            if node.mods_per_rank.fixture_discount_pct:
                effect_txt += f" Fixtures -{node.mods_per_rank.fixture_discount_pct*100:.1f}%/rank."
            status = "Click to rank up." if ok else reason
            return f"{node.name} ({r}/{node.max_rank}) L{node.level_req}+.{prereq_txt}{effect_txt} {status}"
        return None

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

        def set_rect_by_prefix(prefix: str, rect: pygame.Rect, *, contains: str | None = None) -> None:
            for b in self.buttons:
                if b.text.startswith(prefix) and (contains is None or contains in b.text):
                    b.rect = rect
                    return

        if self.current_tab == "shop":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            # Text includes counts/costs; match by prefix.
            set_rect_by_prefix("Place Shelf", pygame.Rect(x, y, bw, 30))
            set_rect_by_prefix("Place Counter", pygame.Rect(x, y + 36, bw, 30))
            set_rect_by_prefix("Place Poster", pygame.Rect(x, y + 72, bw, 30))
            set_rect_by_prefix("Buy Shelf", pygame.Rect(x, y + 118, bw, 30))
            set_rect_by_prefix("Buy Counter", pygame.Rect(x, y + 154, bw, 30))
            set_rect_by_prefix("Buy Poster", pygame.Rect(x, y + 190, bw, 30))
            return

        if self.current_tab == "packs":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            set_rect_by_text("Open Pack", pygame.Rect(x, y, bw, 34))
            set_rect_by_text("Open x5", pygame.Rect(x, y + 46, bw, 30))
            set_rect_by_text("Reveal All", pygame.Rect(x, y + 82, bw, 30))
            # Pack list occupies remaining space in order panel.
            top = y + 140
            self.pack_list.rect = pygame.Rect(x, top, bw, max(40, self.order_panel.rect.bottom - top - 18))
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

        if self.current_tab == "sell":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            half = (bw - 10) // 2
            set_rect_by_text("Sell Items", pygame.Rect(x, y, half, 30))
            set_rect_by_text("Sell Cards", pygame.Rect(x + half + 10, y, half, 30))
            # The rest are dynamic; just lay out by prefix.
            for b in self.buttons:
                if b.text.startswith("Item:"):
                    b.rect = pygame.Rect(x, y + 40, bw, 30)
                elif b.text.startswith("Rarity -"):
                    b.rect = pygame.Rect(x, y + 40, half, 30)
                elif b.text.startswith("Rarity +"):
                    b.rect = pygame.Rect(x + half + 10, y + 40, half, 30)
                elif b.text.startswith("Sell x1"):
                    b.rect = pygame.Rect(x, y + 80, bw, 32)
                elif b.text.startswith("Sell x5"):
                    b.rect = pygame.Rect(x, y + 118, bw, 32)
                elif b.text == "Sell All":
                    b.rect = pygame.Rect(x, y + 156, bw, 32)
                elif b.text.startswith("Sell Random"):
                    # two buttons stacked
                    if b.text.endswith("x1"):
                        b.rect = pygame.Rect(x, y + 80, bw, 32)
                    else:
                        b.rect = pygame.Rect(x, y + 118, bw, 32)
                elif b.text.startswith("Sell Selected x1"):
                    b.rect = pygame.Rect(x, y + 166, bw, 32)
                elif b.text.startswith("Sell Selected x5"):
                    b.rect = pygame.Rect(x, y + 204, bw, 32)
                elif b.text.startswith("Sell Selected All"):
                    b.rect = pygame.Rect(x, y + 242, bw, 32)
                elif b.text == "Cancel":
                    by = self.order_panel.rect.bottom - 58
                    b.rect = pygame.Rect(x, by, half, 34)
                elif b.text == "Confirm":
                    by = self.order_panel.rect.bottom - 58
                    b.rect = pygame.Rect(x + half + 10, by, half, 34)
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

            for b in self.buttons:
                if b.text.startswith("Pricing Mode:"):
                    b.rect = pygame.Rect(stock_x, stock_y + 116, stock_w, 28)
                    break

            set_rect_by_text("Price -1", pygame.Rect(stock_x, stock_y + 148, half, 28))
            set_rect_by_text("Price +1", pygame.Rect(stock_x + half + 10, stock_y + 148, half, 28))
            set_rect_by_text("Price -5", pygame.Rect(stock_x, stock_y + 180, half, 28))
            set_rect_by_text("Price +5", pygame.Rect(stock_x + half + 10, stock_y + 180, half, 28))
            set_rect_by_text("Stock 1", pygame.Rect(stock_x, stock_y + 216, stock_w, 28))
            set_rect_by_text("Stock 5", pygame.Rect(stock_x, stock_y + 248, stock_w, 28))
            set_rect_by_text("Fill Shelf", pygame.Rect(stock_x, stock_y + 280, stock_w, 28))
            set_rect_by_text("List Selected Card", pygame.Rect(stock_x, stock_y + 312, stock_w, 28))
            set_rect_by_text("Prev Shelf", pygame.Rect(stock_x, stock_y + 344, stock_w, 28))
            set_rect_by_text("Next Shelf", pygame.Rect(stock_x, stock_y + 376, stock_w, 28))
            set_rect_by_text("Clear Selection", pygame.Rect(stock_x, stock_y + 408, stock_w, 28))

            # Suggested order buttons live in the inventory panel.
            sx = self.inventory_panel.rect.x + 20
            sy = self.inventory_panel.rect.bottom - 120
            idx = 0
            for b in self.buttons:
                if b.text.startswith("Order Suggested:"):
                    b.rect = pygame.Rect(sx, sy + idx * 36, self.inventory_panel.rect.width - 40, 32)
                    idx += 1

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
            inv = self.app.state.fixtures
            mods = self.app.state.skills.modifiers(get_default_skill_tree())
            shelf_cost = fixture_cost("shelf", mods) or 0
            counter_cost = fixture_cost("counter", mods) or 0
            poster_cost = fixture_cost("poster", mods) or 0
            place_shelf = Button(
                    pygame.Rect(x, y, button_width, 30),
                    f"Place Shelf (owned {inv.shelves})",
                    lambda: self._set_object("shelf"),
                )
            place_shelf.tooltip = "Select Shelf placement. Click a tile in the shop to place (requires owning a shelf)."
            place_counter = Button(
                    pygame.Rect(x, y + 36, button_width, 30),
                    f"Place Counter (owned {inv.counters})",
                    lambda: self._set_object("counter"),
                )
            place_counter.tooltip = "Select Counter placement. Counters are where customers check out."
            place_poster = Button(
                    pygame.Rect(x, y + 72, button_width, 30),
                    f"Place Poster (owned {inv.posters})",
                    lambda: self._set_object("poster"),
                )
            place_poster.tooltip = "Select Poster placement. Posters are decorative fixtures."
            buy_shelf = Button(
                    pygame.Rect(x, y + 118, button_width, 30),
                    f"Buy Shelf (+1) ${shelf_cost}",
                    lambda: self._buy_fixture("shelf"),
                )
            buy_shelf.tooltip = "Buy a shelf to place in the shop. Shelves hold inventory for customers."
            buy_counter = Button(
                    pygame.Rect(x, y + 154, button_width, 30),
                    f"Buy Counter (+1) ${counter_cost}",
                    lambda: self._buy_fixture("counter"),
                )
            buy_counter.tooltip = "Buy a counter to place in the shop."
            buy_poster = Button(
                    pygame.Rect(x, y + 190, button_width, 30),
                    f"Buy Poster (+1) ${poster_cost}",
                    lambda: self._buy_fixture("poster"),
                )
            buy_poster.tooltip = "Buy a poster to decorate the shop."
            self.buttons = [place_shelf, place_counter, place_poster, buy_shelf, buy_counter, buy_poster]
        elif self.current_tab == "packs":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            open1 = Button(pygame.Rect(x, y, button_width, 34), "Open Pack", lambda: self._queue_open_selected_packs(1))
            open5 = Button(pygame.Rect(x, y + 46, button_width, 30), "Open x5", lambda: self._queue_open_selected_packs(5))
            reveal = Button(pygame.Rect(x, y + 82, button_width, 30), "Reveal All", self._reveal_all)
            open1.tooltip = "Open 1 pack of the selected type."
            open5.tooltip = "Queue up to 5 pack openings of the selected type."
            reveal.tooltip = "Reveal all cards in the currently displayed pack (or hold Space)."
            # Pack list occupies remaining space in the order panel.
            top = y + 140
            self.pack_list.rect = pygame.Rect(x, top, button_width, max(40, self.order_panel.rect.bottom - top - 18))
            self.buttons = [open1, open5, reveal]
            self._refresh_pack_list()
            count = self._pack_count(self.selected_pack_id)
            open1.enabled = count > 0
            open5.enabled = count > 0
            reveal.enabled = bool(self.revealed_cards) and (self.reveal_index < len(self.revealed_cards) or self._pack_anim_active())
        elif self.current_tab == "sell":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            half = (button_width - 10) // 2
            mode_items = Button(pygame.Rect(x, y, half, 30), "Sell Items", lambda: self._set_sell_mode("items"))
            mode_cards = Button(pygame.Rect(x + half + 10, y, half, 30), "Sell Cards", lambda: self._set_sell_mode("cards"))
            mode_items.tooltip = "Sell sealed inventory (boosters/decks) back to the market."
            mode_cards.tooltip = "Sell cards from your collection back to the market."
            self.buttons = [mode_items, mode_cards]
            y2 = y + 40
            if self.sell_mode == "items":
                item_btn = Button(pygame.Rect(x, y2, button_width, 30), f"Item: {self.sell_item.title()}", self._toggle_sell_item)
                item_btn.tooltip = "Toggle between selling Boosters or Decks."
                self.buttons.append(item_btn)
                y3 = y2 + 40
                sell1 = Button(pygame.Rect(x, y3, button_width, 32), "Sell x1", lambda: self._queue_sell_items(1))
                sell5 = Button(pygame.Rect(x, y3 + 38, button_width, 32), "Sell x5", lambda: self._queue_sell_items(5))
                sellall = Button(pygame.Rect(x, y3 + 76, button_width, 32), "Sell All", self._queue_sell_items_all)
                self.buttons.extend([sell1, sell5, sellall])
            else:
                rarity = RARITIES[self.sell_rarity_index]
                rminus = Button(pygame.Rect(x, y2, half, 30), "Rarity -", self._sell_prev_rarity)
                rplus = Button(pygame.Rect(x + half + 10, y2, half, 30), "Rarity +", self._sell_next_rarity)
                rminus.tooltip = "Change rarity filter for random sell."
                rplus.tooltip = "Change rarity filter for random sell."
                self.buttons.extend([rminus, rplus])
                y3 = y2 + 40
                rand1 = Button(
                    pygame.Rect(x, y3, button_width, 32),
                    f"Sell Random {rarity.title()} x1",
                    lambda r=rarity: self._queue_sell_random_rarity(r, 1),
                )
                rand5 = Button(
                    pygame.Rect(x, y3 + 38, button_width, 32),
                    f"Sell Random {rarity.title()} x5",
                    lambda r=rarity: self._queue_sell_random_rarity(r, 5),
                )
                sel1 = Button(pygame.Rect(x, y3 + 86, button_width, 32), "Sell Selected x1", lambda: self._queue_sell_selected_card(1))
                sel5 = Button(pygame.Rect(x, y3 + 124, button_width, 32), "Sell Selected x5", lambda: self._queue_sell_selected_card(5))
                selall = Button(pygame.Rect(x, y3 + 162, button_width, 32), "Sell Selected All", self._queue_sell_selected_card_all)
                self.buttons.extend([rand1, rand5, sel1, sel5, selall])

            # Confirm/cancel row (only visible when a pending sell exists).
            if self._sell_pending:
                by = self.order_panel.rect.bottom - 58
                cancel_btn = Button(pygame.Rect(x, by, half, 34), "Cancel", self._cancel_sell_pending)
                confirm_btn = Button(pygame.Rect(x + half + 10, by, half, 34), "Confirm", self._confirm_sell_pending)
                cancel_btn.tooltip = "Cancel the pending sell."
                confirm_btn.tooltip = "Confirm the pending sell and apply changes."
                self.buttons.extend([cancel_btn, confirm_btn])

            # Enable/disable buttons based on availability.
            inv = self.app.state.inventory
            if self.sell_mode == "items":
                available = inv.booster_packs if self.sell_item == "booster" else inv.decks
                for b in self.buttons:
                    if b.text.startswith("Sell x") or b.text == "Sell All":
                        b.enabled = int(available) > 0 and not bool(self._sell_pending)
            else:
                rarity = RARITIES[self.sell_rarity_index]
                can_rand = any(
                    CARD_INDEX[cid].rarity == rarity and self.app.state.collection.get(cid) > self.app.state.deck.cards.get(cid, 0)
                    for cid in self.app.state.collection.cards.keys()
                )
                for b in self.buttons:
                    if b.text.startswith("Sell Random"):
                        b.enabled = can_rand and not bool(self._sell_pending)
                    if b.text.startswith("Sell Selected"):
                        b.enabled = bool(self.selected_card_id) and not bool(self._sell_pending) and self._can_sell_selected_card()
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
                Button(
                    pygame.Rect(stock_x, stock_y + 116, stock_width, 28),
                    f"Pricing Mode: {'Markup %' if self.app.state.pricing.mode == 'markup' else 'Absolute'}",
                    self._toggle_pricing_mode,
                ),
                Button(pygame.Rect(stock_x, stock_y, half, 28), "Booster", lambda: self._set_product("booster")),
                Button(pygame.Rect(stock_x + half + 10, stock_y, half, 28), "Deck", lambda: self._set_product("deck")),
                Button(pygame.Rect(stock_x, stock_y + 32, half, 28), "Common", lambda: self._set_product("single_common")),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 32, half, 28), "Uncommon", lambda: self._set_product("single_uncommon")),
                Button(pygame.Rect(stock_x, stock_y + 64, half, 28), "Rare", lambda: self._set_product("single_rare")),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 64, half, 28), "Epic", lambda: self._set_product("single_epic")),
                Button(pygame.Rect(stock_x, stock_y + 96, half, 28), "Legendary", lambda: self._set_product("single_legendary")),
                Button(pygame.Rect(stock_x, stock_y + 148, half, 28), "Price -1", lambda: self._adjust_price(-1)),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 148, half, 28), "Price +1", lambda: self._adjust_price(1)),
                Button(pygame.Rect(stock_x, stock_y + 180, half, 28), "Price -5", lambda: self._adjust_price(-5)),
                Button(pygame.Rect(stock_x + half + 10, stock_y + 180, half, 28), "Price +5", lambda: self._adjust_price(5)),
                Button(pygame.Rect(stock_x, stock_y + 216, stock_width, 28), "Stock 1", lambda: self._stock_shelf(1)),
                Button(pygame.Rect(stock_x, stock_y + 248, stock_width, 28), "Stock 5", lambda: self._stock_shelf(5)),
                Button(pygame.Rect(stock_x, stock_y + 280, stock_width, 28), "Fill Shelf", self._fill_shelf),
                Button(pygame.Rect(stock_x, stock_y + 312, stock_width, 28), "List Selected Card", self._open_list_card_menu),
                Button(pygame.Rect(stock_x, stock_y + 344, stock_width, 28), "Prev Shelf", lambda: self._select_adjacent_shelf(-1)),
                Button(pygame.Rect(stock_x, stock_y + 376, stock_width, 28), "Next Shelf", lambda: self._select_adjacent_shelf(1)),
                Button(pygame.Rect(stock_x, stock_y + 408, stock_width, 28), "Clear Selection", self._clear_shelf_selection),
            ]
            # Restock suggestions (throttled; uses analytics).
            sx = self.inventory_panel.rect.x + 20
            sy = self.inventory_panel.rect.bottom - 120
            for i, sug in enumerate(self._forecast_suggestions[:2]):
                q = int(sug.recommended_qty)
                if q <= 0:
                    continue
                cost = self._wholesale_cost(sug.product, q)
                btn = Button(
                    pygame.Rect(sx, sy + i * 36, self.inventory_panel.rect.width - 40, 32),
                    f"Order Suggested: {sug.product} x{q} (${cost})",
                    lambda p=sug.product, amt=q: self._order_suggested(p, amt),
                )
                btn.enabled = (self.app.state.money >= cost) and (not self.menu_open)
                btn.tooltip = f"Suggested reorder based on last 3 days sales: {sug.reason}. Current total stock: {sug.current_total_stock}."
                self.buttons.append(btn)
            for b in self.buttons:
                if b.text.startswith("Order "):
                    b.tooltip = "Place an order (delivers after ~30 seconds of real time)."
                elif b.text in {"Booster", "Deck", "Common", "Uncommon", "Rare", "Epic", "Legendary"}:
                    b.tooltip = "Choose which product you want to stock onto shelves."
                elif b.text.startswith("Pricing Mode:"):
                    b.tooltip = "Toggle between Absolute retail pricing and Markup % pricing. Wholesale ordering costs are unchanged."
                elif b.text.startswith("Price"):
                    if self.app.state.pricing.mode == "markup":
                        b.tooltip = "Adjust markup % for this product category (does NOT affect wholesale supplier costs)."
                    else:
                        b.tooltip = "Adjust absolute retail price (does NOT affect wholesale supplier costs)."
                elif b.text.startswith("Stock"):
                    b.tooltip = "Stock the selected shelf with the selected product, consuming your inventory."
                elif b.text == "Fill Shelf":
                    b.tooltip = "Fill the selected shelf to max capacity."
                elif b.text == "List Selected Card":
                    b.tooltip = "List a specific card from your collection onto the selected shelf."
                elif b.text in {"Prev Shelf", "Next Shelf"}:
                    b.tooltip = "Cycle through shelves to quickly manage stock."
                elif b.text == "Clear Selection":
                    b.tooltip = "Clear the current shelf selection."
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
                close_btn.tooltip = "Close the card listing overlay."
                list_btn.tooltip = "List one copy of the selected card onto the selected shelf."
                rarity_minus.tooltip = "Change the market rarity filter."
                rarity_plus.tooltip = "Change the market rarity filter."
                buy_btn.tooltip = "Buy one random card of the selected rarity from the market."
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
            tips = {
                "Add to Deck": "Add the selected card to your deck (max 2 copies).",
                "Remove from Deck": "Remove one copy of the selected card from your deck.",
                "Auto Fill": "Automatically fill the deck up to 20 cards from your collection.",
                "Clear Deck": "Remove all cards from the deck.",
                "Rarity -": "Change market rarity filter.",
                "Rarity +": "Change market rarity filter.",
            }
            for b in self.buttons:
                if b.text in tips:
                    b.tooltip = tips[b.text]
                if b.text.startswith("Buy Random "):
                    b.tooltip = "Buy one random card of the selected rarity."
        elif self.current_tab == "skills":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            reset = Button(pygame.Rect(x, y, button_width, 34), "Reset View", self._skills_reset_view)
            reset.tooltip = "Reset the skill tree view pan to the default position."
            self.buttons = [reset]
        elif self.current_tab == "battle":
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.y + 40
            btn = Button(pygame.Rect(x, y, button_width, 34), "Start Battle", self._start_battle)
            btn.enabled = self.app.state.deck.is_valid()
            btn.tooltip = "Start a battle using your current deck. Winning grants money, a pack, and XP."
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
            self.menu_buttons[0].tooltip = "Save the current game state to the active slot."
            self.menu_buttons[1].tooltip = "Start a fresh game in this slot."
            self.menu_buttons[2].tooltip = "Return to the main menu (save slots)."
            self.menu_buttons[3].tooltip = "Close this menu."

    def _toggle_mobile_nav(self) -> None:
        self.mobile_nav_open = not self.mobile_nav_open
        self._build_tab_btns()

    def _build_tab_btns(self) -> None:
        self.tab_buttons = []
        width, height = self.app.screen.get_size()
        x0 = 20
        btn_w = 120
        btn_h = 32
        gap = 12
        tab_ids = list(self.tabs) + ["menu"]
        mobile = width < self._mobile_breakpoint

        if mobile:
            nav_w = 156
            nav_y = height - 44
            nav_btn = Button(pygame.Rect(x0, nav_y, nav_w, btn_h), "☰ Menus", self._toggle_mobile_nav)
            nav_btn.tooltip = "Open or close gameplay menus (mobile layout)."
            self.tab_buttons.append(nav_btn)
            if not self.mobile_nav_open:
                return
            per_row = max(1, (width - x0 * 2) // (btn_w + gap))
            start_y = height - 44 - (btn_h + 8) * 2
            for i, tab in enumerate(tab_ids):
                row = i // per_row
                col = i % per_row
                rect = pygame.Rect(x0 + col * (btn_w + gap), start_y + row * (btn_h + 8), btn_w, btn_h)
                label = "Menu" if tab == "menu" else tab.title()
                b = Button(rect, label, lambda t=tab: self._switch_tab(t))
                b.tooltip = f"Open the {label} tab."
                self.tab_buttons.append(b)
            return

        self.mobile_nav_open = False
        total_w = len(tab_ids) * btn_w + max(0, len(tab_ids) - 1) * gap
        x = max(x0, (width - total_w) // 2)
        y = height - 44
        for i, tab in enumerate(tab_ids):
            rect = pygame.Rect(x + i * (btn_w + gap), y, btn_w, btn_h)
            label = "Menu" if tab == "menu" else tab.title()
            b = Button(rect, label, lambda t=tab: self._switch_tab(t))
            b.tooltip = f"Open the {label} tab."
            self.tab_buttons.append(b)


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
        if tab == "packs":
            self._refresh_pack_list()
        if tab == "manage":
            self._refresh_shelves()

    def _pack_count(self, pack_id: str) -> int:
        return pack_count(self.app.state.inventory, pack_id)

    def _award_staff_xp(self, event_type: StaffXpEventType, amount: int, *, product: str | None = None) -> None:
        """Award staff XP (persisted in shopkeeper_xp) and show lightweight UI feedback."""
        r = award_staff_xp_total(self.app.state.shopkeeper_xp, event_type, amount, product=product)
        if r.gained_xp <= 0:
            return
        # Persist + sync
        self.app.state.shopkeeper_xp = int(r.new_xp)
        self.staff.xp = int(r.new_xp)
        self.staff.level = int(r.new_level)

        # UI: throttle spam by accumulating (especially sales).
        if str(event_type) == "sale":
            self._staff_xp_toast_accum += int(r.gained_xp)
        else:
            self.toasts.push(f"+{r.gained_xp} Staff XP")

        if r.leveled_up:
            self.toasts.push(f"Staff level up! Lv {r.new_level}")

    def _update_forecast_cache(self) -> None:
        now = float(self.app.state.time_seconds)
        if now < float(self._forecast_next_update_t):
            return
        self._forecast_next_update_t = now + 1.0
        a = self.app.state.analytics
        self._forecast_suggestions = compute_restock_suggestions(
            a,
            day=int(self.app.state.day),
            inv=self.app.state.inventory,
            shelves=self.app.state.shop_layout.shelf_stocks,
            lead_time_seconds=30.0,
            window_days=3,
            max_suggestions=4,
        )
        self._forecast_stockouts = top_stockout_shelves(a, day=int(self.app.state.day), window_days=3, limit=5)
        # Keep buttons in sync (suggested order buttons are dynamic).
        if self.current_tab == "manage":
            self._build_buttons()

    def _order_suggested(self, product: str, qty: int) -> None:
        q = max(0, int(qty))
        if q <= 0:
            return
        cost = self._wholesale_cost(product, q)
        if cost <= 0:
            return
        if self.app.state.money < cost:
            self.toasts.push(f"Not enough money (${cost}).")
            return
        self.app.state.money -= cost
        singles: dict[str, int] = {}
        boosters = 0
        decks = 0
        if product == "booster":
            boosters = q
        elif product == "deck":
            decks = q
        elif product.startswith("single_"):
            r = product.replace("single_", "")
            singles[r] = q
        else:
            return
        order = InventoryOrder(boosters, decks, singles, cost, 0, self.app.state.time_seconds + 30.0)
        self.app.state.pending_orders.append(order)
        self.app.state.analytics.record_order_placed(day=int(self.app.state.day), t=float(self.app.state.time_seconds), product=product, qty=int(q))
        self.app.state.analytics.log(
            day=int(self.app.state.day), t=float(self.app.state.time_seconds), kind="order", message=f"Ordered suggested {product} x{q} (${cost})"
        )
        self.toasts.push(f"Ordered {product} x{q} (${cost}).")
        self._build_buttons()

    def _refresh_pack_list(self) -> None:
        # Rebuild list items and cache row surfaces only when a label/count changes.
        snap: dict[str, int] = {}
        items: list[ScrollItem] = []
        for p in PACK_TYPES:
            c = self._pack_count(p.pack_id)
            snap[p.pack_id] = c
            label = f"{p.name}  x{c}"
            items.append(ScrollItem(p.pack_id, label, p))
            if self._pack_row_text.get(p.pack_id) != label:
                self._pack_row_text[p.pack_id] = label
                self._pack_row_surf[p.pack_id] = self.theme.render_text(
                    self.theme.font_small, label, self.theme.colors.text
                )
        self._pack_counts_snapshot = snap
        self.pack_list.items = items
        self.pack_list.on_select = self._select_pack

        # Keep selection valid.
        if self.selected_pack_id not in snap and items:
            self.selected_pack_id = str(items[0].key)

    def _select_pack(self, item: ScrollItem) -> None:
        self.selected_pack_id = str(item.key)
        self._build_buttons()

    def _pack_anim_active(self) -> bool:
        return self._pack_anim_stage in {"shake", "flash", "reveal"}

    def _pack_busy(self) -> bool:
        # Busy when an animation is playing, or queued openings exist.
        # (Stage "done" is not busy: it just shows the last opened pack.)
        return self._pack_anim_active() or self._pack_open_queue > 0

    def _queue_open_selected_packs(self, count: int) -> None:
        """Queue pack openings; packs are opened one-by-one with animation for smoothness."""
        if self.selected_pack_id != "booster":
            self.toasts.push("That pack type isn't implemented yet.")
            return
        n = max(0, int(count))
        if n <= 0:
            return
        available = self._pack_count("booster")
        free = max(0, int(available) - int(self._pack_open_queue))
        if free <= 0:
            self.toasts.push("No packs available.")
            return
        n = min(n, free)
        self._pack_open_queue += n
        if self._pack_anim_stage in {"idle", "done"} and self._pack_anim_cooldown <= 0.0:
            self._start_next_pack_open()
        self._build_buttons()

    def _start_next_pack_open(self) -> None:
        if self._pack_open_queue <= 0:
            return
        if self.selected_pack_id != "booster":
            self._pack_open_queue = 0
            return
        if self._pack_count("booster") <= 0:
            self._pack_open_queue = 0
            self._build_buttons()
            return

        self._pack_open_queue -= 1
        self.app.state.inventory.booster_packs = max(0, int(self.app.state.inventory.booster_packs) - 1)

        cards = list(open_booster(self.app.rng))
        self.revealed_cards = list(cards)
        self.reveal_index = 0

        # Add to collection immediately (gameplay state), but render surfaces once for animation.
        for cid in cards:
            self.app.state.collection.add(cid, 1)
        self.app.state.analytics.record_pack_open(day=int(self.app.state.day), t=float(self.app.state.time_seconds), packs=1)
        self.app.state.analytics.log(
            day=int(self.app.state.day),
            t=float(self.app.state.time_seconds),
            kind="pack_open",
            message="Opened pack x1",
        )
        self._award_staff_xp("pack_open", 1)

        self._build_pack_anim_surfaces(cards)
        self._pack_anim_stage = "shake"
        self._pack_anim_stage_t = 0.0
        self._pack_anim_reveal_t = 0.0
        self._pack_anim_revealed = 0
        self._pack_slots_alpha = 0
        self._pack_anim_cooldown = 0.05
        self._refresh_pack_list()
        self._build_buttons()

    def _build_pack_anim_surfaces(self, cards: list[str]) -> None:
        """Pre-render all pack animation surfaces for smooth playback."""
        # Pack image surface.
        pack_w, pack_h = 180, 120
        pack = pygame.Surface((pack_w, pack_h), pygame.SRCALPHA)
        pack.fill(self.theme.colors.panel_alt)
        pygame.draw.rect(pack, self.theme.colors.border, pack.get_rect(), 2)
        pygame.draw.rect(pack, self.theme.colors.accent, pack.get_rect().inflate(-10, -10), 2)
        t1 = self.theme.render_text(self.theme.font, "Booster Pack", self.theme.colors.text)
        t2 = self.theme.render_text(self.theme.font_small, "Hold Space to skip", self.theme.colors.muted)
        pack.blit(t1, (10, 12))
        pack.blit(t2, (10, 50))
        self._pack_surf = pack

        flash = pygame.Surface((pack_w + 40, pack_h + 40), pygame.SRCALPHA)
        flash.fill((255, 255, 255, 255))
        self._pack_flash_surf = flash

        back = pygame.Surface((120, 160), pygame.SRCALPHA)
        back.fill(self.theme.colors.panel_alt)
        pygame.draw.rect(back, self.theme.colors.border, back.get_rect(), 2)
        q = self.theme.render_text(self.theme.font, "?", self.theme.colors.muted)
        back.blit(q, (back.get_width() // 2 - q.get_width() // 2, back.get_height() // 2 - q.get_height() // 2))
        self._pack_card_back = back

        asset_mgr = get_asset_manager()
        faces: list[pygame.Surface] = []
        for cid in list(cards)[:5]:
            card = CARD_INDEX[cid]
            face = pygame.Surface((120, 160), pygame.SRCALPHA)
            bg = asset_mgr.create_card_background(card.rarity, (120, 160))
            face.blit(bg, (0, 0))
            sprite = asset_mgr.get_card_sprite(cid, (64, 64))
            if sprite:
                face.blit(sprite, (28, 15))
            rarity_color = getattr(self.theme.colors, f"card_{card.rarity}")
            draw_glow_border(face, face.get_rect(), rarity_color, border_width=2, glow_radius=4, glow_alpha=80)
            name = self.theme.render_text(self.theme.font_small, card.name[:12], self.theme.colors.text)
            face.blit(name, (6, 4))
            faces.append(face)
        self._pack_card_faces = faces

    def _skip_pack_anim(self) -> None:
        """Instantly reveal the current pack (used for space-hold skip and Reveal All)."""
        if not self.revealed_cards:
            return
        self._pack_anim_stage = "done"
        self._pack_anim_stage_t = 0.0
        self._pack_anim_reveal_t = 0.0
        self._pack_anim_revealed = len(self.revealed_cards[:5])
        self.reveal_index = len(self.revealed_cards[:5])
        self._pack_slots_alpha = 255

    def _open_selected_packs(self, n: int) -> None:
        # Back-compat: older buttons call this. Route to the new queued animation flow.
        k = max(1, min(int(n), 10))
        self._queue_open_selected_packs(k)

    def _open_pack(self) -> None:
        # Legacy entry point (older UI); open selected.
        self._queue_open_selected_packs(1)

    def _reveal_all(self) -> None:
        self._skip_pack_anim()

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
        if getattr(self.app.state, "pricing", None) and self.app.state.pricing.mode == "markup":
            # In markup mode, reuse the price +/- buttons to adjust markup % (not wholesale).
            cur = float(self.app.state.pricing.get_markup_pct(price_attr))
            self.app.state.pricing.set_markup_pct(price_attr, cur + (float(delta) / 100.0))
        else:
            current = getattr(self.app.state.prices, price_attr)
            setattr(self.app.state.prices, price_attr, max(1, current + delta))
        if self.current_tab == "manage":
            self._build_buttons()

    def _toggle_pricing_mode(self) -> None:
        if self.app.state.pricing.mode == "absolute":
            self.app.state.pricing.mode = "markup"
            self.toasts.push("Pricing mode: Markup %")
        else:
            self.app.state.pricing.mode = "absolute"
            self.toasts.push("Pricing mode: Absolute")
        self._build_buttons()

    def _set_sell_mode(self, mode: str) -> None:
        if mode not in {"items", "cards"}:
            return
        self.sell_mode = mode
        self._sell_pending = None
        self._build_buttons()

    def _toggle_sell_item(self) -> None:
        self.sell_item = "deck" if self.sell_item == "booster" else "booster"
        self._sell_pending = None
        self._build_buttons()

    def _sell_prev_rarity(self) -> None:
        self.sell_rarity_index = (self.sell_rarity_index - 1) % len(RARITIES)
        self._sell_pending = None
        self._build_buttons()

    def _sell_next_rarity(self) -> None:
        self.sell_rarity_index = (self.sell_rarity_index + 1) % len(RARITIES)
        self._sell_pending = None
        self._build_buttons()

    def _can_sell_selected_card(self) -> bool:
        if not self.selected_card_id:
            return False
        owned = self.app.state.collection.get(self.selected_card_id)
        in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
        return owned > in_deck

    def _cancel_sell_pending(self) -> None:
        self._sell_pending = None
        self._build_buttons()

    def _queue_sell_items(self, qty: int) -> None:
        inv = self.app.state.inventory
        available = int(inv.booster_packs if self.sell_item == "booster" else inv.decks)
        q = max(0, min(int(qty), available))
        if q <= 0:
            return
        from game.sim.sellback import market_buy_price, sellback_total, sellback_unit_price

        market = market_buy_price(self.sell_item)
        unit = sellback_unit_price(market)
        total = sellback_total(market, q)
        self._sell_pending = {"type": "items", "key": self.sell_item, "qty": q, "unit": unit, "total": total}
        self._build_buttons()

    def _queue_sell_items_all(self) -> None:
        inv = self.app.state.inventory
        available = int(inv.booster_packs if self.sell_item == "booster" else inv.decks)
        self._queue_sell_items(available)

    def _queue_sell_selected_card(self, qty: int) -> None:
        if not self.selected_card_id or not self._can_sell_selected_card():
            return
        owned = self.app.state.collection.get(self.selected_card_id)
        in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
        from game.sim.sellback import market_buy_price, sellable_copies, sellback_total, sellback_unit_price

        sellable = sellable_copies(owned=owned, in_deck=in_deck)
        q = max(0, min(int(qty), sellable))
        if q <= 0:
            return
        rarity = CARD_INDEX[self.selected_card_id].rarity
        market = market_buy_price(rarity)
        unit = sellback_unit_price(market)
        total = sellback_total(market, q)
        self._sell_pending = {"type": "card", "card_id": self.selected_card_id, "qty": q, "unit": unit, "total": total}
        self._build_buttons()

    def _queue_sell_selected_card_all(self) -> None:
        if not self.selected_card_id:
            return
        owned = self.app.state.collection.get(self.selected_card_id)
        in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
        from game.sim.sellback import sellable_copies

        self._queue_sell_selected_card(sellable_copies(owned=owned, in_deck=in_deck))

    def _queue_sell_random_rarity(self, rarity: str, qty: int) -> None:
        q = max(0, int(qty))
        if q <= 0:
            return
        # Precompute how many sellable exist for this rarity.
        pool: list[str] = []
        for cid in self.app.state.collection.cards.keys():
            if CARD_INDEX[cid].rarity != rarity:
                continue
            owned = self.app.state.collection.get(cid)
            in_deck = self.app.state.deck.cards.get(cid, 0)
            if owned > in_deck:
                pool.append(cid)
        if not pool:
            return
        from game.sim.sellback import market_buy_price, sellback_total, sellback_unit_price

        market = market_buy_price(rarity)
        unit = sellback_unit_price(market)
        total = sellback_total(market, q)
        self._sell_pending = {"type": "random", "rarity": rarity, "qty": q, "unit": unit, "total": total}
        self._build_buttons()

    def _confirm_sell_pending(self) -> None:
        if not self._sell_pending:
            return
        t = str(self._sell_pending.get("type"))
        qty = int(self._sell_pending.get("qty", 0))
        unit = int(self._sell_pending.get("unit", 0))
        total = int(self._sell_pending.get("total", 0))
        if qty <= 0 or total <= 0:
            self._sell_pending = None
            self._build_buttons()
            return
        before_money = int(self.app.state.money)
        earned = 0
        lines: list[str] = []
        if t == "items":
            key = str(self._sell_pending.get("key"))
            inv = self.app.state.inventory
            available = int(inv.booster_packs if key == "booster" else inv.decks)
            q = min(qty, available)
            if q <= 0:
                self._sell_pending = None
                self._build_buttons()
                return
            if key == "booster":
                inv.booster_packs -= q
            else:
                inv.decks -= q
            earned = unit * q
            lines.append(f"Sold {q} {key}(s) @ ${unit} = ${earned}")
        elif t == "card":
            cid = str(self._sell_pending.get("card_id"))
            owned = self.app.state.collection.get(cid)
            in_deck = self.app.state.deck.cards.get(cid, 0)
            from game.sim.sellback import sellable_copies

            sellable = sellable_copies(owned=owned, in_deck=in_deck)
            q = min(qty, sellable)
            if q <= 0:
                self._sell_pending = None
                self._build_buttons()
                return
            if not self.app.state.collection.remove(cid, q):
                self._sell_pending = None
                self._build_buttons()
                return
            earned = unit * q
            card = CARD_INDEX[cid]
            lines.append(f"Sold {q}x {card.name} ({cid}) @ ${unit} = ${earned}")
        else:  # random by rarity
            rarity = str(self._sell_pending.get("rarity"))
            remaining = qty
            sold = 0
            # Sell one at a time to respect deck commitments per card.
            while remaining > 0:
                pool: list[str] = []
                for cid in self.app.state.collection.cards.keys():
                    if CARD_INDEX[cid].rarity != rarity:
                        continue
                    owned = self.app.state.collection.get(cid)
                    in_deck = self.app.state.deck.cards.get(cid, 0)
                    if owned > in_deck:
                        pool.append(cid)
                if not pool:
                    break
                cid = self.app.rng.choice(pool)
                if not self.app.state.collection.remove(cid, 1):
                    break
                sold += 1
                remaining -= 1
            if sold <= 0:
                self._sell_pending = None
                self._build_buttons()
                return
            earned = unit * sold
            lines.append(f"Sold {sold} random {rarity} cards @ ${unit} = ${earned}")

        self.app.state.money += int(earned)
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        gained_xp = xp_from_sell(int(earned), mods)
        if gained_xp > 0:
            res = self.app.state.progression.add_xp(gained_xp)
            if res.gained_levels > 0:
                self.toasts.push(f"Level up! Lv {self.app.state.progression.level} (+{res.gained_skill_points} SP)")
        self.app.state.analytics.record_sellback(day=int(self.app.state.day), t=float(self.app.state.time_seconds), revenue=int(earned))
        self.app.state.analytics.log(
            day=int(self.app.state.day),
            t=float(self.app.state.time_seconds),
            kind="sell",
            message=f"Sold back for ${int(earned)}",
        )
        lines.append(f"Earned: ${earned} | Money: ${before_money} → ${self.app.state.money}")
        lines.append(f"XP gained: {gained_xp}")
        self._sell_receipt_lines = lines
        self.toasts.push(f"Sold items for ${earned}.")
        self._sell_pending = None
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
        # "Value" is market value, not player-retail (player cannot change the market).
        from game.sim.pricing import market_buy_price_single

        return market_buy_price_single(rarity)

    def _market_buy_price(self, rarity: str) -> int:
        from game.sim.pricing import market_buy_price_single

        return market_buy_price_single(rarity)

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
        from game.sim.pricing import wholesale_order_total

        total = wholesale_order_total(product, qty)
        return int(total or 0)

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
        prices = self.app.state.prices
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        # Cache derived shelf values for the current pricing/modifiers.
        self._shelf_value_cache: dict[str, int] = {}
        items: list[ScrollItem] = []
        for key, stock in layout.shelf_stocks.items():
            x, y = key.split(",")
            listed = ""
            if getattr(stock, "cards", None):
                listed = " (listed)"
            value = self._shelf_total_value(stock, prices=prices, mods=mods)
            self._shelf_value_cache[key] = value
            label = f"Shelf ({x},{y}) - {stock.product} x{stock.qty}{listed} | ${value}"
            items.append(ScrollItem(key, label, stock))
        self.shelf_list.items = items
        self.shelf_list.on_select = self._select_shelf

    def _shelf_total_value(self, stock: "ShelfStock", *, prices: "Prices", mods: "Modifiers") -> int:
        """Compute total sell value for a shelf (uses effective sell prices + skills)."""
        if stock.qty <= 0:
            return 0
        # Listed cards: sum by each card's rarity pricing.
        if getattr(stock, "cards", None):
            total = 0
            for cid in stock.cards:
                card = CARD_INDEX.get(cid)
                if not card:
                    continue
                product = f"single_{card.rarity}"
                p = effective_sale_price(prices, product, mods, self.app.state.pricing)
                if p:
                    total += int(p)
            return int(total)
        # Bulk products
        p = effective_sale_price(prices, stock.product, mods, self.app.state.pricing)
        if not p:
            return 0
        return int(p) * int(stock.qty)

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
        self._award_staff_xp("restock", to_add, product=product)
        self.app.state.analytics.record_restock(day=int(self.app.state.day), t=float(self.app.state.time_seconds), product=product, qty=int(to_add))
        self.app.state.analytics.log(
            day=int(self.app.state.day),
            t=float(self.app.state.time_seconds),
            kind="restock",
            message=f"Manual restock {product} x{int(to_add)}",
        )
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
        self.app.state.analytics.record_order_placed(day=int(self.app.state.day), t=float(self.app.state.time_seconds), product="booster", qty=int(qty))
        self.app.state.analytics.log(day=int(self.app.state.day), t=float(self.app.state.time_seconds), kind="order", message=f"Ordered boosters x{int(qty)} (${int(cost)})")
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
        self.app.state.analytics.record_order_placed(day=int(self.app.state.day), t=float(self.app.state.time_seconds), product="deck", qty=int(qty))
        self.app.state.analytics.log(day=int(self.app.state.day), t=float(self.app.state.time_seconds), kind="order", message=f"Ordered decks x{int(qty)} (${int(cost)})")
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
        self.app.state.analytics.record_order_placed(day=int(self.app.state.day), t=float(self.app.state.time_seconds), product=f"single_{rarity}", qty=int(qty))
        self.app.state.analytics.log(day=int(self.app.state.day), t=float(self.app.state.time_seconds), kind="order", message=f"Ordered {rarity} singles x{int(qty)} (${int(cost)})")
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
        # Start new cycle, or resume if paused.
        if not self.cycle_active:
            self.cycle_active = True
            self.cycle_paused = False
            self.cycle_phase = "day"
            self.phase_timer = 0.0
            self.day_transition_timer = 0.0
            self._begin_day_phase(reset_summary=True)
            return
        if self.cycle_paused:
            self.cycle_paused = False
            return

    def end_day(self) -> None:
        # Legacy name: Stop button should PAUSE, not end.
        if self.cycle_active:
            self.cycle_paused = True

    def _begin_day_phase(self, *, reset_summary: bool) -> None:
        self.cycle_phase = "day"
        self.phase_timer = 0.0
        self._autosaved_this_night = False
        self.customers.clear()
        self.spawned = 0
        interval = float(customer_spawn_interval(self.app.state.day))
        # Build a schedule based on target interval and hard safety cap.
        max_spawns = max(0, int(MAX_CUSTOMERS_SPAWNED_PER_DAY))
        if max_spawns <= 0:
            self.customer_schedule = []
        else:
            # If the cap would cause spawns to finish early, slow the effective interval so visits
            # stay spread across the whole day.
            cap_interval = float(self.day_duration) / float(max_spawns + 1)
            effective = max(float(interval), float(cap_interval))
            sched: list[float] = []
            t = effective  # first customer doesn't spawn instantly
            while t < self.day_duration and len(sched) < max_spawns:
                sched.append(float(t))
                t += effective
            self.customer_schedule = sched
        if reset_summary:
            self.app.state.last_summary = self.app.state.last_summary.__class__()

    def _begin_night_phase(self) -> None:
        self.cycle_phase = "night"
        self.phase_timer = 0.0
        self._autosaved_this_night = False
        # Clear customers for night.
        self.customers.clear()
        self.spawned = 0
        self.customer_schedule = []
        # Autosave at the beginning of every night.
        self.app.state.last_summary.profit = self.app.state.last_summary.revenue
        if not self._autosaved_this_night:
            self.app.save_game()
            self._autosaved_this_night = True

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
        if self.current_tab == "packs":
            # Scroll/click only affects the hovered pack list (avoid wheel scrolling other panels).
            if event.type == pygame.MOUSEMOTION:
                self.pack_list.handle_event(event)
            if event.type == pygame.MOUSEWHEEL:
                if self.pack_list.rect.collidepoint(pygame.mouse.get_pos()):
                    self.pack_list.handle_event(event)
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.pack_list.rect.collidepoint(event.pos):
                    self.pack_list.handle_event(event)
                    return
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
        if self.current_tab == "sell":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_sell_click(event.pos)
            if event.type == pygame.MOUSEWHEEL:
                in_book = self.book_panel.rect.collidepoint(pygame.mouse.get_pos())
                if in_book:
                    self._scroll_card_book(-event.y * 24)
        if self.current_tab == "skills":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self._skills_content_rect().collidepoint(event.pos):
                    self._skills_panning = True
                    self._skills_pan_last = pygame.Vector2(event.pos)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                self._skills_panning = False
            if event.type == pygame.MOUSEMOTION and self._skills_panning:
                cur = pygame.Vector2(event.pos)
                delta = cur - self._skills_pan_last
                self._skills_pan += delta
                self._skills_pan_last = cur
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                sid = self._skill_at_pos(event.pos)
                if sid:
                    tree = get_default_skill_tree()
                    ok, reason = self.app.state.skills.can_rank_up(tree, sid, self.app.state.progression)
                    if not ok:
                        self.toasts.push(reason)
                    else:
                        if self.app.state.skills.rank_up(tree, sid, self.app.state.progression):
                            node = tree.nodes[sid]
                            r = self.app.state.skills.rank(sid)
                            self.toasts.push(f"Upgraded: {node.name} ({r}/{node.max_rank})")
                return
        if self.current_tab != "shop":
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            tile = self._tile_at_pos(event.pos)
            if tile:
                kind = self.selected_object
                # Give user-friendly errors for fixture placement rules.
                if kind in {"shelf", "counter", "poster"} and not self.app.state.fixtures.can_place(kind):
                    self.toasts.push(f"Buy a {kind} first.")
                    return
                placed = self.app.try_place_object(kind, tile)
                if placed:
                    self.toasts.push(f"Placed {kind}.")
                    if kind in {"shelf", "counter", "poster"}:
                        self._build_buttons()
                else:
                    self.toasts.push("Can't place there (occupied or out of bounds).")

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.app.screen.get_size() != self._last_screen_size:
            self._layout()
            self._build_buttons()
        # Keep staff actor XP in sync with persisted state even when the day isn't running,
        # so loads immediately reflect the correct actor stats.
        if self.staff.xp != self.app.state.shopkeeper_xp:
            self.staff.xp = int(self.app.state.shopkeeper_xp)
            self.staff.level = max(1, 1 + self.staff.xp // 100)
        if self._drag_target or self._resize_target:
            self._apply_drag_resize()
        for tb in self.tab_buttons:
            tb.update(dt)
        for button in self.buttons:
            button.update(dt)
        if self.cycle_active and not self.cycle_paused:
            self._update_cycle(dt)
        if self.current_tab == "packs":
            if any(self._pack_counts_snapshot.get(p.pack_id) != self._pack_count(p.pack_id) for p in PACK_TYPES):
                self._refresh_pack_list()
            # Drive the lightweight pack opening animation state machine.
            self._pack_anim_cooldown = max(0.0, float(self._pack_anim_cooldown) - float(dt))
            total = len(self.revealed_cards[:5])
            if self._pack_anim_active():
                keys = pygame.key.get_pressed()
                if keys[pygame.K_SPACE]:
                    self._skip_pack_anim()
                else:
                    # Stages: shake (0.3s) -> flash/slots (0.6s) -> reveal cards.
                    SHAKE_S = 0.3
                    FLASH_S = 0.6
                    CARD_DELAY_S = 0.12
                    self._pack_anim_stage_t += float(dt)
                    if self._pack_anim_stage == "shake":
                        if self._pack_anim_stage_t >= SHAKE_S:
                            self._pack_anim_stage = "flash"
                            self._pack_anim_stage_t = 0.0
                            self._pack_slots_alpha = 0
                    elif self._pack_anim_stage == "flash":
                        p = min(1.0, max(0.0, self._pack_anim_stage_t / FLASH_S))
                        self._pack_slots_alpha = int(255 * p)
                        if self._pack_anim_stage_t >= FLASH_S:
                            self._pack_anim_stage = "reveal"
                            self._pack_anim_stage_t = 0.0
                            self._pack_anim_reveal_t = 0.0
                            self._pack_slots_alpha = 255
                    elif self._pack_anim_stage == "reveal":
                        self._pack_anim_reveal_t += float(dt)
                        while self._pack_anim_reveal_t >= CARD_DELAY_S and self._pack_anim_revealed < total:
                            self._pack_anim_reveal_t -= CARD_DELAY_S
                            self._pack_anim_revealed += 1
                            self.reveal_index = self._pack_anim_revealed
                        if self._pack_anim_revealed >= total:
                            self._pack_anim_stage = "done"
                            self._pack_anim_stage_t = 0.0
            else:
                # Auto-start next queued pack (if any).
                if self._pack_open_queue > 0 and self._pack_anim_cooldown <= 0.0:
                    self._start_next_pack_open()
            # Keep pack button enabled states in sync without rebuilding UI.
            count = self._pack_count(self.selected_pack_id)
            for b in self.buttons:
                if b.text in {"Open Pack", "Open x5"}:
                    b.enabled = count > 0
                elif b.text == "Reveal All":
                    b.enabled = bool(self.revealed_cards) and (self._pack_anim_active() or self.reveal_index < len(self.revealed_cards[:5]))
        # Forecast cache update (throttled to 1 Hz max).
        if self.current_tab in {"manage", "stats"}:
            self._update_forecast_cache()
        # Flush aggregated staff XP toast (reduces spam for frequent events like sales).
        if self._staff_xp_toast_accum > 0:
            self._staff_xp_toast_timer += dt
            if self._staff_xp_toast_timer >= 0.75:
                self.toasts.push(f"+{self._staff_xp_toast_accum} Staff XP")
                self._staff_xp_toast_accum = 0
                self._staff_xp_toast_timer = 0.0
        else:
            self._staff_xp_toast_timer = 0.0

    def _update_cycle(self, dt: float) -> None:
        # Fade-out tint when a new day starts.
        if self.day_transition_timer > 0:
            self.day_transition_timer = max(0.0, self.day_transition_timer - dt)

        self.phase_timer += dt
        if self.cycle_phase == "day":
            self._update_day(dt)
            if self.phase_timer >= self.day_duration:
                self._begin_night_phase()
        else:
            # Night: no customers; just wait out the timer.
            if self.phase_timer >= self.night_duration:
                # Advance to next day.
                self.app.state.day += 1
                self.day_transition_timer = 2.0
                self._begin_day_phase(reset_summary=True)
                self.app.save_game()

    def _update_day(self, dt: float) -> None:
        # Move existing customers first (may reduce active count as they exit).
        active = 0
        for customer in self.customers:
            if customer.done:
                continue
            self._move_customer(customer, dt)
            if not customer.done:
                active += 1

        # Spawn pacing with caps and retry delay to avoid per-frame spawn attempts at cap.
        if self.spawned < len(self.customer_schedule) and self.phase_timer >= self.customer_schedule[self.spawned]:
            spawns = 0
            while (
                spawns < int(MAX_CUSTOMER_SPAWNS_PER_FRAME)
                and self.spawned < len(self.customer_schedule)
                and self.phase_timer >= self.customer_schedule[self.spawned]
            ):
                if active >= int(MAX_CUSTOMERS_ACTIVE):
                    # Push the next scheduled attempt forward slightly.
                    self.customer_schedule[self.spawned] = float(self.phase_timer + float(CUSTOMER_SPAWN_RETRY_DELAY))
                    break
                did = self._spawn_customer()
                if not did:
                    # Can't spawn right now (e.g., no shelves). Delay retry.
                    self.customer_schedule[self.spawned] = float(self.phase_timer + float(CUSTOMER_SPAWN_RETRY_DELAY))
                    break
                self.spawned += 1
                spawns += 1
                active += 1

        # Staff actor update (auto-restock) - scan throttled inside update_staff.
        # Compute blocked tiles cache only when shop objects count changes.
        obj_count = len(self.app.state.shop_layout.objects)
        if obj_count != self._staff_blocked_count:
            self._staff_blocked_tiles = {obj.tile for obj in self.app.state.shop_layout.objects}
            self._staff_blocked_count = obj_count
        # Sync persisted shopkeeper XP <-> staff actor (so load/save works reliably).
        if self.staff.xp != self.app.state.shopkeeper_xp:
            self.staff.xp = int(self.app.state.shopkeeper_xp)
        res = update_staff(
            self.staff,
            dt,
            grid=SHOP_GRID,
            blocked_tiles=self._staff_blocked_tiles,
            counter_tile=self._find_object_tile("counter") or (10, 7),
            shelf_stocks=self.app.state.shop_layout.shelf_stocks,
            inventory=self.app.state.inventory,
            collection=self.app.state.collection,
            deck=self.app.state.deck,
        )
        # Award staff XP for restocking only when items actually moved onto a shelf.
        if res.did_restock and res.items_moved > 0:
            self._award_staff_xp("restock", int(res.items_moved), product=res.product)
            if res.product:
                self.app.state.analytics.record_restock(
                    day=int(self.app.state.day),
                    t=float(self.app.state.time_seconds),
                    product=str(res.product),
                    qty=int(res.items_moved),
                )
                self.app.state.analytics.log(
                    day=int(self.app.state.day),
                    t=float(self.app.state.time_seconds),
                    kind="restock",
                    message=f"Staff restock {str(res.product)} x{int(res.items_moved)}",
                )
        if self.app.state.shopkeeper_xp != self.staff.xp:
            self.app.state.shopkeeper_xp = int(self.staff.xp)
        if res.did_restock and self.current_tab == "manage":
            self._refresh_shelves()
            self._build_buttons()

    def _spawn_customer(self) -> bool:
        entrance = pygame.Vector2(1.5 * self.tile_px, (SHOP_GRID[1] - 1) * self.tile_px)
        shelves = self.app.state.shop_layout.shelf_tiles()
        if not shelves:
            return False
        shelf = self.app.rng.choice(shelves)
        target = pygame.Vector2((shelf[0] + 0.5) * self.tile_px, (shelf[1] + 0.5) * self.tile_px)
        # Assign a random customer sprite
        shop_assets = get_shop_asset_manager()
        sprite_id = shop_assets.get_random_customer_id(self.app.rng)
        self.customers.append(Customer(entrance, target, "to_shelf", sprite_id))
        self.app.state.last_summary.customers += 1
        self.app.state.analytics.record_visitor(day=int(self.app.state.day), t=float(self.app.state.time_seconds))
        return True

    def _find_object_tile(self, kind: str) -> tuple[int, int] | None:
        for obj in self.app.state.shop_layout.objects:
            if obj.kind == kind:
                return obj.tile
        return None

    def _move_customer(self, customer: Customer, dt: float) -> None:
        # Wait (browse/pay) timers.
        if customer.wait_s > 0.0:
            customer.wait_s = max(0.0, customer.wait_s - dt)
            return

        speed = float(self.tile_px) * float(CUSTOMER_SPEED_TILES_PER_S)
        direction = customer.target - customer.pos
        if direction.length() > 1:
            customer.pos += direction.normalize() * speed * dt
            return
        if customer.state == "to_shelf":
            # Browse a bit before walking to the counter.
            customer.wait_s = float(self.app.rng.uniform(*CUSTOMER_BROWSE_TIME_RANGE))
            counter = self._find_object_tile("counter") or (10, 7)
            customer.target = pygame.Vector2((counter[0] + 0.5) * self.tile_px, (counter[1] + 0.5) * self.tile_px)
            customer.state = "to_counter"
            customer.purchase = self._choose_shelf_purchase()
        elif customer.state == "to_counter":
            # Pause briefly at counter (pays) before purchase is processed.
            customer.wait_s = float(self.app.rng.uniform(*CUSTOMER_PAY_TIME_RANGE))
            customer.state = "paying"
        elif customer.state == "paying":
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
        # Demand weighting should use the same retail base prices that drive actual sale price,
        # without mutating the player's stored absolute prices.
        if self.app.state.pricing.mode == "markup":
            from game.config import Prices
            from game.sim.pricing import retail_base_price

            base = self.app.state.prices
            demand = Prices(**base.__dict__)
            demand.booster = retail_base_price(base, self.app.state.pricing, "booster") or demand.booster
            demand.deck = retail_base_price(base, self.app.state.pricing, "deck") or demand.deck
            demand.single_common = retail_base_price(base, self.app.state.pricing, "single_common") or demand.single_common
            demand.single_uncommon = (
                retail_base_price(base, self.app.state.pricing, "single_uncommon") or demand.single_uncommon
            )
            demand.single_rare = retail_base_price(base, self.app.state.pricing, "single_rare") or demand.single_rare
            demand.single_epic = retail_base_price(base, self.app.state.pricing, "single_epic") or demand.single_epic
            demand.single_legendary = (
                retail_base_price(base, self.app.state.pricing, "single_legendary") or demand.single_legendary
            )
            chosen = choose_purchase(demand, products, self.app.rng)
        else:
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
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        price = effective_sale_price(prices, product, mods, self.app.state.pricing)
        if price is None:
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
        became_empty = stock.qty <= 0
        if stock.qty <= 0:
            stock.qty = 0
            # Keep the last product type so staff can restock it (customers only buy if qty>0 anyway).
            if hasattr(stock, "cards") and getattr(stock, "cards", None) is not None:
                # If this was a listed-cards shelf and it's now empty, treat it as a bulk singles shelf.
                stock.cards.clear()
        self.app.state.money += price
        self.app.state.last_summary.revenue += price
        self.app.state.last_summary.units_sold += 1
        self._award_staff_xp("sale", int(price), product=product)
        self.app.state.analytics.record_sale(
            day=int(self.app.state.day),
            t=float(self.app.state.time_seconds),
            product=str(product),
            revenue=int(price),
            shelf_key=str(shelf_key),
            became_empty=bool(became_empty),
        )
        self.app.state.analytics.log(
            day=int(self.app.state.day),
            t=float(self.app.state.time_seconds),
            kind="sale",
            message=f"Sold {product} for ${int(price)}",
        )
        res = self.app.state.progression.add_xp(xp_from_sale(price, mods))
        if res.gained_levels > 0:
            self.toasts.push(f"Level up! Lv {self.app.state.progression.level} (+{res.gained_skill_points} SP)")
        # Notify staff so they react immediately to stock being taken off shelves.
        notify_shelf_change(self.staff, shelf_key)

    def _buy_fixture(self, kind: str) -> None:
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        cost = fixture_cost(kind, mods) or 0
        if cost <= 0:
            self.toasts.push("Can't buy that fixture.")
            return
        if self.app.state.money < cost:
            self.toasts.push(f"Not enough money (${cost}).")
            return
        ok = self.app.try_buy_fixture(kind)
        if ok:
            self.toasts.push(f"Purchased {kind} (+1).")
            self._build_buttons()
        else:
            self.toasts.push("Purchase failed.")

    def _skills_reset_view(self) -> None:
        self._skills_pan.update(0, 0)

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
            self._draw_player(surface)
            # Night/transition tint (barely visible blue).
            if self.cycle_active:
                inner = self._shop_inner_rect()
                tint_alpha = 0
                if self.cycle_phase == "night":
                    tint_alpha = 28
                elif self.day_transition_timer > 0:
                    # Fade out over 2 seconds after night -> day.
                    t = max(0.0, min(1.0, self.day_transition_timer / 2.0))
                    tint_alpha = int(24 * t)
                if tint_alpha > 0:
                    tint = pygame.Surface((inner.width, inner.height), pygame.SRCALPHA)
                    tint.fill((60, 90, 160, tint_alpha))
                    surface.blit(tint, inner.topleft)
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
        if self.current_tab == "sell":
            self.book_panel.draw(surface, self.theme)
        if self.current_tab == "skills":
            self.skills_panel.draw(surface, self.theme)
        if self.current_tab == "stats":
            self.stats_panel.draw(surface, self.theme)
        self._draw_top_info_bar(surface)
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
        if self.current_tab == "skills":
            self._draw_skills(surface)
        if self.current_tab == "stats":
            self._draw_stats(surface)
        if self.current_tab == "battle":
            self._draw_battle_info(surface)
        if self.current_tab == "sell":
            self._draw_sell(surface)
        if self.menu_open:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            surface.blit(overlay, (0, 0))
            self.menu_panel.draw(surface, self.theme)
            for button in self.menu_buttons:
                button.draw(surface, self.theme)
        self.draw_overlays(surface)

    def _top_info_items(self) -> list[tuple[str, str]]:
        phase = "Day" if self.cycle_phase == "day" else "Night"
        cycle_state = "Paused" if self.cycle_paused else ("Running" if self.cycle_active else "Stopped")
        return [
            ("Money", f"${self.app.state.money}"),
            ("Day", str(self.app.state.day)),
            ("Cycle", f"{phase} · {cycle_state}"),
            ("XP", f"Lv {self.app.state.progression.level} · {self.app.state.progression.xp}/{xp_to_next(self.app.state.progression.level)}"),
            ("Staff", f"Lv {self.staff.level} · XP {self.staff.xp}"),
        ]

    def _top_info_rects(self) -> list[tuple[pygame.Rect, str, str]]:
        items = self._top_info_items()
        rects: list[tuple[pygame.Rect, str, str]] = []
        x = 20
        y = 8
        for label, value in items:
            w = max(120, min(320, 24 + self.theme.font_small.size(f"{label}: {value}")[0]))
            rect = pygame.Rect(x, y, w, 30)
            rects.append((rect, label, value))
            x += w + 10
        return rects

    def _draw_top_info_bar(self, surface: pygame.Surface) -> None:
        for rect, label, value in self._top_info_rects():
            pygame.draw.rect(surface, self.theme.colors.panel, rect, border_radius=6)
            pygame.draw.rect(surface, self.theme.colors.border, rect, 1, border_radius=6)
            text = self.theme.render_text(self.theme.font_small, f"{label}: {value}", self.theme.colors.text)
            surface.blit(text, (rect.x + 8, rect.y + 7))

    def _draw_sell(self, surface: pygame.Surface) -> None:
        """Sell flow UI: items (boosters/decks) or cards (collection)."""
        # Receipt summary (shown near bottom of order panel).
        if self._sell_pending:
            qty = int(self._sell_pending.get("qty", 0))
            unit = int(self._sell_pending.get("unit", 0))
            total = int(self._sell_pending.get("total", 0))
            desc = self.theme.render_text(
                self.theme.font_small,
                f"Pending: qty {qty} @ ${unit} = ${total}",
                self.theme.colors.muted,
            )
            surface.blit(desc, (self.order_panel.rect.x + 20, self.order_panel.rect.bottom - 88))
        if self._sell_receipt_lines:
            x = self.order_panel.rect.x + 20
            y = self.order_panel.rect.bottom - 140
            for line in self._sell_receipt_lines[:5]:
                t = self.theme.render_text(self.theme.font_small, line, self.theme.colors.muted)
                surface.blit(t, (x, y))
                y += 18

        # Card book list (for cards mode; still useful for reference in items mode).
        row_height = 88
        content_rect = self._card_book_content_rect()
        rarity_filter = None if self.sell_mode != "cards" else RARITIES[self.sell_rarity_index]
        entries = self.app.state.collection.entries(rarity_filter)
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
            owned = int(entry.qty)
            in_deck = int(self.app.state.deck.cards.get(entry.card_id, 0))
            sellable = max(0, owned - in_deck)
            row_rect = pygame.Rect(content_rect.x, y, content_rect.width, row_height - 8)
            if row_rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(surface, self.theme.colors.panel_alt, row_rect)
            if self.selected_card_id == entry.card_id:
                pygame.draw.rect(surface, self.theme.colors.accent, row_rect, 2)
            name = self.theme.render_text(self.theme.font_small, f"{card.name} ({card.card_id})", self.theme.colors.text)
            surface.blit(name, (row_rect.x + 8, row_rect.y + 6))
            from game.sim.sellback import market_buy_price, sellback_unit_price

            unit = sellback_unit_price(market_buy_price(card.rarity))
            meta = self.theme.render_text(
                self.theme.font_small,
                f"{card.rarity.title()} | Owned {owned} | In deck {in_deck} | Sellable {sellable} | Unit ${unit}",
                self.theme.colors.muted,
            )
            surface.blit(meta, (row_rect.x + 8, row_rect.y + 28))
            y += row_height
        surface.set_clip(None)

    def _draw_stats(self, surface: pygame.Surface) -> None:
        """Analytics: graphs + rolling event log."""
        rect = self.stats_panel.rect
        inner = pygame.Rect(rect.x + 12, rect.y + 36, rect.width - 24, rect.height - 48)
        pygame.draw.rect(surface, self.theme.colors.panel_alt, inner)
        pygame.draw.rect(surface, self.theme.colors.border, inner, 1)

        a = self.app.state.analytics
        day = int(self.app.state.day)
        # Last N days series.
        n = 14
        days = list(range(max(1, day - n + 1), day + 1))
        rev: list[int] = []
        vis: list[int] = []
        for d in days:
            m = a.days.get(d)
            rev.append(int(m.revenue) if m else 0)
            vis.append(int(m.visitors) if m else 0)
        units = []
        for d in days:
            m = a.days.get(d)
            if not m:
                units.append(0)
            else:
                units.append(sum(int(v) for v in m.units_sold.values()))

        def draw_series(box: pygame.Rect, values: list[int], *, color: tuple[int, int, int], label: str) -> None:
            if not values:
                return
            mx = max(values) if max(values) > 0 else 1
            pts: list[tuple[int, int]] = []
            for i, v in enumerate(values):
                x = box.x + int((i / max(1, (len(values) - 1))) * (box.width - 1))
                y = box.bottom - int((v / mx) * (box.height - 1))
                pts.append((x, y))
            if len(pts) >= 2:
                pygame.draw.lines(surface, color, False, pts, 2)
            pygame.draw.rect(surface, self.theme.colors.border, box, 1)
            t = self.theme.render_text(self.theme.font_small, f"{label} (max {mx})", self.theme.colors.muted)
            surface.blit(t, (box.x + 6, box.y + 4))

        left = pygame.Rect(inner.x + 8, inner.y + 8, int(inner.width * 0.62) - 12, inner.height - 16)
        right = pygame.Rect(left.right + 12, inner.y + 8, inner.right - left.right - 20, inner.height - 16)

        g1 = pygame.Rect(left.x, left.y, left.width, left.height // 3 - 6)
        g2 = pygame.Rect(left.x, g1.bottom + 10, left.width, left.height // 3 - 6)
        g3 = pygame.Rect(left.x, g2.bottom + 10, left.width, left.bottom - (g2.bottom + 10))
        draw_series(g1, rev, color=self.theme.colors.accent, label="Revenue/day")
        draw_series(g2, vis, color=self.theme.colors.good, label="Visitors/day")
        draw_series(g3, units, color=self.theme.colors.text, label="Units sold/day")

        # Derived stats
        cur = a.days.get(day, None)
        cur_vis = int(cur.visitors) if cur else 0
        cur_units = sum(int(v) for v in (cur.units_sold.values() if cur else []))
        per_cust = (cur_units / cur_vis) if cur_vis > 0 else 0.0
        lines = [
            f"Day {day}",
            f"Visitors: {cur_vis}",
            f"Units sold: {cur_units}",
            f"Units/customer: {per_cust:0.2f}",
            f"Pending orders: {len(self.app.state.pending_orders)}",
        ]
        y = right.y
        for line in lines:
            t = self.theme.render_text(self.theme.font_small, line, self.theme.colors.text)
            surface.blit(t, (right.x, y))
            y += 18

        y += 10
        hdr = self.theme.render_text(self.theme.font_small, "Recent events", self.theme.colors.text)
        surface.blit(hdr, (right.x, y))
        y += 18
        for e in a.event_log[-14:]:
            msg = f"D{e.day} {e.kind}: {e.message}"
            t = self.theme.render_text(self.theme.font_small, msg[:48], self.theme.colors.muted)
            surface.blit(t, (right.x, y))
            y += 18

    def _draw_skills(self, surface: pygame.Surface) -> None:
        tree = get_default_skill_tree()
        content = self._skills_content_rect()
        # Background
        pygame.draw.rect(surface, self.theme.colors.panel_alt, content)
        pygame.draw.rect(surface, self.theme.colors.border, content, 1)
        clip = surface.get_clip()
        surface.set_clip(content)
        # Simple grid
        gx = int(self._skills_pan.x) % 40
        gy = int(self._skills_pan.y) % 40
        for x in range(content.x - gx, content.right, 40):
            pygame.draw.line(surface, (35, 36, 44), (x, content.y), (x, content.bottom), 1)
        for y in range(content.y - gy, content.bottom, 40):
            pygame.draw.line(surface, (35, 36, 44), (content.x, y), (content.right, y), 1)

        # Draw edges
        node_by_id = tree.nodes
        for a, b in self._skills_edges:
            na = node_by_id[a]
            nb = node_by_id[b]
            ax, ay = na.pos
            bx, by = nb.pos
            p1 = (int(content.x + self._skills_pan.x + ax), int(content.y + self._skills_pan.y + ay))
            p2 = (int(content.x + self._skills_pan.x + bx), int(content.y + self._skills_pan.y + by))
            pygame.draw.line(surface, (70, 80, 95), p1, p2, 2)

        # Draw nodes
        w, h = self._skills_node_size
        prog = self.app.state.progression
        skills = self.app.state.skills
        for node in self._skills_nodes:
            nx, ny = node.pos
            rect = pygame.Rect(
                int(content.x + self._skills_pan.x + nx - w // 2),
                int(content.y + self._skills_pan.y + ny - h // 2),
                w,
                h,
            )
            r = skills.rank(node.skill_id)
            ok, _reason = skills.can_rank_up(tree, node.skill_id, prog)
            locked = (prog.level < node.level_req) or any(skills.rank(p.skill_id) < p.rank for p in node.prereqs)
            bg = self.theme.colors.panel if (r > 0) else self.theme.colors.panel_alt
            if locked:
                bg = (28, 30, 36)
            if ok:
                bg = self.theme.colors.accent_hover
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(surface, self.theme.colors.border, rect, 2, border_radius=8)
            name = self.theme.render_text(self.theme.font_small, node.name, self.theme.colors.text)
            surface.blit(name, (rect.x + 8, rect.y + 6))
            rr = self.theme.render_text(
                self.theme.font_small,
                f"{r}/{node.max_rank}  L{node.level_req}+",
                self.theme.colors.muted,
            )
            surface.blit(rr, (rect.x + 8, rect.y + 28))

        surface.set_clip(clip)
        # Header summary
        sx = self.skills_panel.rect.x + 12
        sy = self.skills_panel.rect.y + 8
        mods = skills.modifiers(tree)
        summary = f"Lv {prog.level}  XP {prog.xp}/{xp_to_next(prog.level)}  SP {prog.skill_points}  Sell +{mods.sell_price_pct*100:.1f}%"
        text = self.theme.render_text(self.theme.font_small, summary, self.theme.colors.muted)
        surface.blit(text, (sx, sy))

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
                label = self.theme.render_text(self.theme.font_small, obj.kind[0].upper(), self.theme.colors.text)
                surface.blit(label, label.get_rect(center=rect.center))
            
            # Draw stock info for shelves
            if obj.kind == "shelf":
                key = self.app.state.shop_layout._key(obj.tile)
                stock = self.app.state.shop_layout.shelf_stocks.get(key)
                if self.selected_shelf_key == key and self.current_tab == "manage":
                    pygame.draw.rect(surface, self.theme.colors.accent, rect, 2)
                if stock and stock.product != "empty":
                    # Draw stock indicator
                    text = self.theme.render_text(self.theme.font_small, f"{stock.qty}", self.theme.colors.text)
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

    def _draw_player(self, surface: pygame.Surface) -> None:
        """Draw staff actor + XP bar + level indicator (clipped to shop viewport)."""
        # Actor position is in tile-space; convert to world pixels then to screen.
        x_off = self._shop_x_offset
        y_off = self._shop_y_offset
        px = self.staff.pos[0] * self.tile_px + x_off
        py = self.staff.pos[1] * self.tile_px + y_off

        size = max(30, min(int(self.tile_px * 0.9), 60))
        shop_assets = get_shop_asset_manager()
        sprite = shop_assets.get_customer_sprite(0, (size, size))
        if sprite:
            sx = int(px - size // 2)
            sy = int(py - size + 8)
            surface.blit(sprite, (sx, sy))
        else:
            rect = pygame.Rect(int(px - 10), int(py - 18), 20, 20)
            pygame.draw.rect(surface, (160, 220, 255), rect)

        # XP + level indicator is the staff/shopkeeper progression (shopkeeper_xp).
        # Level formula matches game.sim.staff_xp.staff_level_from_xp (100 XP per level).
        xp_total = max(0, int(self.staff.xp))
        frac = float(xp_total % 100) / 100.0
        level = int(self.staff.level)
        bar_w = max(24, min(42, size))
        bar_h = 4
        bar_x = int(px - bar_w // 2)
        bar_y = int(py + 10)
        pygame.draw.rect(surface, (10, 12, 16), pygame.Rect(bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(surface, (40, 60, 90), pygame.Rect(bar_x, bar_y, bar_w, bar_h), 1)
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            pygame.draw.rect(surface, (90, 170, 255), pygame.Rect(bar_x, bar_y, fill_w, bar_h))

        if level != self._staff_level_cached or self._staff_level_text is None:
            self._staff_level_cached = level
            self._staff_level_text = self.theme.render_text(
                self.theme.font_small, f"S Lv {level}", self.theme.colors.muted
            )
        if self._staff_level_text:
            surface.blit(self._staff_level_text, (bar_x, bar_y + 6))

        # Optional debug: draw path/target while debug overlay is enabled.
        if getattr(self.app, "debug_overlay", False) and (self.staff.path or self.staff.target_tile):
            pts: list[tuple[int, int]] = []
            pts.append((int(px), int(py)))
            for t in self.staff.path:
                cx = int((t[0] + 0.5) * self.tile_px + x_off)
                cy = int((t[1] + 0.5) * self.tile_px + y_off)
                pts.append((cx, cy))
            if self.staff.target_tile:
                t = self.staff.target_tile
                cx = int((t[0] + 0.5) * self.tile_px + x_off)
                cy = int((t[1] + 0.5) * self.tile_px + y_off)
                pts.append((cx, cy))
            if len(pts) >= 2:
                pygame.draw.lines(surface, (90, 170, 255), False, pts, 2)

    def _draw_status(self, surface: pygame.Surface) -> None:
        rect = self.shop_panel.rect
        inner = self._shop_inner_rect()
        x_off = rect.x + 14
        # Bottom-left inside the shop window (avoid the header).
        y_base = max(inner.y + 6, rect.bottom - 66)
        text = self.theme.render_text(
            self.theme.font, f"Day {self.app.state.day} | Money ${self.app.state.money}", self.theme.colors.text
        )
        surface.blit(text, (x_off, y_base))
        status_y = y_base + 26
        if self.cycle_active:
            remain = (self.day_duration - self.phase_timer) if self.cycle_phase == "day" else (self.night_duration - self.phase_timer)
            phase = "Day" if self.cycle_phase == "day" else "Night"
            paused = " (Paused)" if self.cycle_paused else ""
            timer_text = self.theme.render_text(
                self.theme.font_small,
                f"{phase}{paused}: {max(0.0, remain):0.1f}s left",
                self.theme.colors.muted,
            )
            surface.blit(timer_text, (x_off, status_y))
        else:
            summary = self.app.state.last_summary
            summary_text = self.theme.render_text(
                self.theme.font_small,
                f"+${summary.revenue} | {summary.units_sold} sold | {summary.customers} customers",
                self.theme.colors.muted,
            )
            surface.blit(summary_text, (x_off, status_y))

    def _draw_packs(self, surface: pygame.Surface) -> None:
        # Pack list (scrollable, clipped).
        pygame.draw.rect(surface, self.theme.colors.panel_alt, self.pack_list.rect)
        pygame.draw.rect(surface, self.theme.colors.border, self.pack_list.rect, 1)
        header = self.theme.render_text(
            self.theme.font_small,
            f"Selected: {self.selected_pack_id}  Available: {self._pack_count(self.selected_pack_id)}",
            self.theme.colors.muted,
        )
        surface.blit(header, (self.pack_list.rect.x, self.pack_list.rect.y - 18))

        clip = surface.get_clip()
        surface.set_clip(self.pack_list.rect)
        ih = self.pack_list.item_height
        start = max(0, int(self.pack_list.scroll_offset) // max(1, ih))
        visible = (self.pack_list.rect.height // max(1, ih)) + 2
        end = min(len(self.pack_list.items), start + visible)
        y = self.pack_list.rect.y + start * ih - self.pack_list.scroll_offset
        for idx in range(start, end):
            item = self.pack_list.items[idx]
            item_rect = pygame.Rect(self.pack_list.rect.x, y, self.pack_list.rect.width, self.pack_list.item_height)
            if idx == self.pack_list.hover_index:
                pygame.draw.rect(surface, self.theme.colors.panel, item_rect)
            if str(item.key) == self.selected_pack_id:
                pygame.draw.rect(surface, self.theme.colors.accent_hover, item_rect, 2)
            surf = self._pack_row_surf.get(str(item.key))
            if surf:
                surface.blit(surf, (item_rect.x + 6, item_rect.y + 6))
            y += ih
        surface.set_clip(clip)

        # Pack opening animation + revealed cards preview (last opened pack).
        base_x = self.shop_panel.rect.x + 20
        base_y = max(self.shop_panel.rect.y + 40, self.shop_panel.rect.bottom - 190)
        rects = [pygame.Rect(base_x + i * 130, base_y, 120, 160) for i in range(5)]
        stage = self._pack_anim_stage
        # Stage 1 is the pack shake (no slots yet). After that, slots appear and cards reveal.
        show_slots = stage in {"flash", "reveal", "done"} or (stage == "idle" and bool(self.revealed_cards))
        backs_alpha = int(self._pack_slots_alpha) if stage == "flash" else 255
        back = self._pack_card_back
        if back is not None:
            back.set_alpha(backs_alpha)
        faces = self._pack_card_faces or []
        revealed = max(0, min(int(self.reveal_index), len(self.revealed_cards[:5])))

        for i, rect in enumerate(rects):
            if not show_slots:
                pygame.draw.rect(surface, self.theme.colors.panel_alt, rect)
                pygame.draw.rect(surface, self.theme.colors.border, rect, 2)
                continue
            if i < revealed and i < len(faces):
                surface.blit(faces[i], rect.topleft)
            elif back is not None:
                surface.blit(back, rect.topleft)
            else:
                pygame.draw.rect(surface, self.theme.colors.panel_alt, rect)
                pygame.draw.rect(surface, self.theme.colors.border, rect, 2)

        # Pack shake/flash animation drawn above the slots.
        if stage in {"shake", "flash"} and self._pack_surf is not None:
            pack = self._pack_surf
            px = rects[2].centerx - pack.get_width() // 2
            py = rects[0].y - pack.get_height() - 18
            # Clamp inside shop panel for smaller windows.
            px = max(self.shop_panel.rect.x + 12, min(px, self.shop_panel.rect.right - 12 - pack.get_width()))
            py = max(self.shop_panel.rect.y + 40, min(py, rects[0].y - pack.get_height() - 6))
            if stage == "shake":
                dx = int(math.sin(float(self._pack_anim_stage_t) * 35.0) * 6.0)
                dy = int(math.sin(float(self._pack_anim_stage_t) * 55.0) * 3.0)
                surface.blit(pack, (px + dx, py + dy))
            else:
                surface.blit(pack, (px, py))
                if self._pack_flash_surf is not None:
                    flash = self._pack_flash_surf
                    # Fade flash out over the flash stage duration (0.6s).
                    alpha = int(255 * max(0.0, min(1.0, 1.0 - (float(self._pack_anim_stage_t) / 0.6))))
                    flash.set_alpha(alpha)
                    fx = px + pack.get_width() // 2 - flash.get_width() // 2
                    fy = py + pack.get_height() // 2 - flash.get_height() // 2
                    surface.blit(flash, (fx, fy))

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
        # Hit-test from top-most to bottom-most (match draw stacking).
        if self.current_tab == "manage":
            if self.manage_card_book_open:
                if self._start_drag_or_resize(self.book_panel.rect, "book", pos):
                    return True
            if self._start_drag_or_resize(self.shelf_list.rect, "list", pos):
                return True
            if self._start_drag_or_resize(self.inventory_panel.rect, "inventory", pos):
                return True
            if self._start_drag_or_resize(self.stock_panel.rect, "stock", pos):
                return True
        if self.current_tab == "deck":
            if self._start_drag_or_resize(self.deck_panel.rect, "deck", pos):
                return True
            if self._start_drag_or_resize(self.book_panel.rect, "book", pos):
                return True
        if self.current_tab == "sell":
            if self._start_drag_or_resize(self.book_panel.rect, "book", pos):
                return True
        if self.current_tab == "skills":
            if self._start_drag_or_resize(self.skills_panel.rect, "skills", pos):
                return True
        if self.current_tab == "stats":
            if self._start_drag_or_resize(self.stats_panel.rect, "stats", pos):
                return True
        if self._start_drag_or_resize(self.order_panel.rect, "order", pos):
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
            elif self._drag_target == "skills":
                rect = self.skills_panel.rect
            elif self._drag_target == "stats":
                rect = self.stats_panel.rect
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
                self._relayout_buttons_only()
            elif self._drag_target == "book":
                self.book_panel.rect = rect
                self._relayout_buttons_only()
            elif self._drag_target == "deck":
                self.deck_panel.rect = rect
            elif self._drag_target == "skills":
                self.skills_panel.rect = rect
            elif self._drag_target == "stats":
                self.stats_panel.rect = rect
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
            elif self._resize_target == "skills":
                rect = self.skills_panel.rect
            elif self._resize_target == "stats":
                rect = self.stats_panel.rect
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
                self._relayout_buttons_only()
            elif self._resize_target == "book":
                self.book_panel.rect = rect
                self._relayout_buttons_only()
            elif self._resize_target == "deck":
                self.deck_panel.rect = rect
            elif self._resize_target == "skills":
                self.skills_panel.rect = rect
            elif self._resize_target == "stats":
                self.stats_panel.rect = rect
            elif self._resize_target == "shop":
                self.shop_panel.rect = rect
                self._update_shop_viewport(rescale=False)
            else:
                self.shelf_list.rect = rect

    
    def _draw_manage(self, surface: pygame.Surface) -> None:
        # Shelf list
        # If the card-book overlay is open, keep the manage view uncluttered.
        if self.manage_card_book_open:
            return
        title = self.theme.render_text(self.theme.font_small, "Shelf Stock", self.theme.colors.text)
        surface.blit(title, (self.shelf_list.rect.x, self.shelf_list.rect.y - 22))
        pygame.draw.rect(surface, self.theme.colors.border, self.shelf_list.rect, 2)
        self.shelf_list.draw(surface, self.theme)
        # Selected product + inventory
        product = self.products[self.product_index]
        price_attr = self._price_attr_for_product(product)
        price_value = getattr(self.app.state.prices, price_attr) if price_attr else 0
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        eff = effective_sale_price(self.app.state.prices, product, mods, self.app.state.pricing) or int(price_value)
        from game.sim.pricing import retail_base_price, wholesale_unit_cost

        base_retail = retail_base_price(self.app.state.prices, self.app.state.pricing, product) or int(price_value)
        w = wholesale_unit_cost(product) or 0
        if self.app.state.pricing.mode == "markup" and price_attr:
            mk = int(round(self.app.state.pricing.get_markup_pct(price_attr) * 100.0))
            mk_txt = f" | Markup {mk}%"
        else:
            mk_txt = ""
        if w > 0:
            margin_pct = int(round(((base_retail - w) / float(w)) * 100.0))
            margin_txt = f" | Wholesale ${w} | Retail ${base_retail} ({margin_pct:+d}%)"
        else:
            margin_txt = ""
        prod_text = self.theme.render_text(
            self.theme.font_small,
            f"Product: {product} | Mode {self.app.state.pricing.mode}{mk_txt} | Sell ${eff}{margin_txt}",
            self.theme.colors.text,
        )
        surface.blit(prod_text, (self.stock_panel.rect.x + 20, self.stock_panel.rect.bottom + 8))
        selected = self.selected_shelf_key or "None"
        sel_text = self.theme.render_text(self.theme.font_small, f"Selected shelf: {selected}", self.theme.colors.muted)
        surface.blit(sel_text, (self.stock_panel.rect.x + 20, self.stock_panel.rect.bottom + 26))
        if self.selected_card_id:
            c = CARD_INDEX[self.selected_card_id]
            owned = self.app.state.collection.get(self.selected_card_id)
            in_deck = self.app.state.deck.cards.get(self.selected_card_id, 0)
            card_text = self.theme.render_text(
                self.theme.font_small,
                f"Selected card: {c.name} ({c.card_id}) | Owned {owned} | In deck {in_deck}",
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
            text = self.theme.render_text(self.theme.font_small, line, self.theme.colors.muted)
            surface.blit(text, (self.inventory_panel.rect.x + 20, y))
            y += 18

        # Selected shelf details
        if self.selected_shelf_key:
            stock = self.app.state.shop_layout.shelf_stocks.get(self.selected_shelf_key)
            if stock:
                y += 6
                hdr = self.theme.render_text(self.theme.font_small, "Selected shelf contents", self.theme.colors.text)
                surface.blit(hdr, (self.inventory_panel.rect.x + 20, y))
                y += 18
                prod_line = self.theme.render_text(
                    self.theme.font_small,
                    f"{stock.product} x{stock.qty}/{stock.max_qty}",
                    self.theme.colors.muted,
                )
                surface.blit(prod_line, (self.inventory_panel.rect.x + 20, y))
                y += 18
                # Total shelf value using effective sell prices.
                prices = self.app.state.prices
                mods = self.app.state.skills.modifiers(get_default_skill_tree())
                value = self._shelf_total_value(stock, prices=prices, mods=mods)
                val_line = self.theme.render_text(
                    self.theme.font_small,
                    f"Total value: ${value}",
                    self.theme.colors.muted,
                )
                surface.blit(val_line, (self.inventory_panel.rect.x + 20, y))
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
                        cards_line = self.theme.render_text(
                            self.theme.font_small, "Cards: " + ", ".join(parts), self.theme.colors.muted
                        )
                        surface.blit(cards_line, (self.inventory_panel.rect.x + 20, y))
                        y += 18
                    else:
                        cards_line = self.theme.render_text(
                            self.theme.font_small, "Cards: (none listed)", self.theme.colors.muted
                        )
                        surface.blit(cards_line, (self.inventory_panel.rect.x + 20, y))
                        y += 18

        # Pending order queue with ETA
        if self.app.state.pending_orders:
            y += 6
            hdr = self.theme.render_text(self.theme.font_small, "Incoming (ETA)", self.theme.colors.text)
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
                line = self.theme.render_text(self.theme.font_small, f"{eta:>2}s - {label}", self.theme.colors.muted)
                surface.blit(line, (self.inventory_panel.rect.x + 20, y))
                y += 18

        # Restock Suggestions (throttled to 1 Hz).
        y += 6
        hdr = self.theme.render_text(self.theme.font_small, "Restock Suggestions", self.theme.colors.text)
        surface.blit(hdr, (self.inventory_panel.rect.x + 20, y))
        y += 18
        if not self._forecast_suggestions:
            none = self.theme.render_text(self.theme.font_small, "(no data yet)", self.theme.colors.muted)
            surface.blit(none, (self.inventory_panel.rect.x + 20, y))
            y += 18
        else:
            for sug in self._forecast_suggestions[:4]:
                line = self.theme.render_text(
                    self.theme.font_small,
                    f"{sug.product}: recommend {sug.recommended_qty} (stock {sug.current_total_stock}) | {sug.reason}",
                    self.theme.colors.muted,
                )
                surface.blit(line, (self.inventory_panel.rect.x + 20, y))
                y += 18

        if self._forecast_stockouts:
            y += 4
            hdr2 = self.theme.render_text(self.theme.font_small, "Stockout hot spots (last 3 days)", self.theme.colors.text)
            surface.blit(hdr2, (self.inventory_panel.rect.x + 20, y))
            y += 18
            for key, cnt in self._forecast_stockouts[:3]:
                surface.blit(
                    self.theme.render_text(self.theme.font_small, f"Shelf {key}: {cnt} stockouts", self.theme.colors.muted),
                    (self.inventory_panel.rect.x + 20, y),
                )
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
            name = self.theme.render_text(
                self.theme.font_small, f"{card.name} ({card.card_id})", self.theme.colors.text
            )
            surface.blit(name, (row_rect.x + 68, row_rect.y + 6))
            desc = (card.description[:60] + "...") if len(card.description) > 60 else card.description
            desc_text = self.theme.render_text(self.theme.font_small, desc, self.theme.colors.muted)
            surface.blit(desc_text, (row_rect.x + 68, row_rect.y + 24))
            stats = self.theme.render_text(
                self.theme.font_small,
                f"{card.rarity.title()} | Cost {card.cost} | {card.attack}/{card.health}",
                self.theme.colors.text,
            )
            surface.blit(stats, (row_rect.x + 68, row_rect.y + 42))
            value = self._card_value(card.rarity)
            qty_text = self.theme.render_text(
                self.theme.font_small, f"Qty {entry.qty} | Value ${value}", self.theme.colors.muted
            )
            surface.blit(qty_text, (row_rect.x + 68, row_rect.y + 60))
            y += row_height
        surface.set_clip(None)

        if self.current_tab != "deck":
            return

        # Deck list
        deck_rect = self.deck_panel.rect
        deck_title = self.theme.render_text(
            self.theme.font_small, f"Deck ({self.app.state.deck.total()}/20)", self.theme.colors.text
        )
        surface.blit(deck_title, (deck_rect.x + 12, deck_rect.y + 12))
        y = deck_rect.y + 36
        for card_id, qty in self.app.state.deck.summary():
            card = CARD_INDEX[card_id]
            line = self.theme.render_text(self.theme.font_small, f"{card.name} x{qty}", self.theme.colors.text)
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

    def _handle_sell_click(self, pos: tuple[int, int]) -> None:
        """Select a card row in the Sell tab (respects rarity filter)."""
        content_rect = self._card_book_content_rect()
        if not content_rect.collidepoint(pos):
            return
        row_height = 88
        idx = int((pos[1] - content_rect.y + self.card_book_scroll) // row_height)
        rarity_filter = None if self.sell_mode != "cards" else RARITIES[self.sell_rarity_index]
        entries = self.app.state.collection.entries(rarity_filter)
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
            text = self.theme.render_text(self.theme.font_small, line, self.theme.colors.muted)
            surface.blit(text, (self.order_panel.rect.x + 20, y))
            y += 18
