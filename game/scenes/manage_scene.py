from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel, ScrollList, ScrollItem
from game.sim.inventory import InventoryOrder, RARITIES


class ManageScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.pricing_panel = Panel(pygame.Rect(40, 80, 420, 340), "Pricing")
        self.reorder_panel = Panel(pygame.Rect(500, 80, 420, 340), "Reorder Stock")
        self.shelf_panel = Panel(pygame.Rect(40, 440, 880, 220), "Shelf Stocking")
        self.buttons: list[Button] = []
        self.shelf_list = ScrollList(pygame.Rect(60, 480, 420, 160), [])
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
        self._build_buttons()
        self._refresh_shelves()

    def _build_buttons(self) -> None:
        self.buttons.clear()
        px = self.pricing_panel.rect.x + 20
        py = self.pricing_panel.rect.y + 50
        for idx, (label, attr) in enumerate(
            [
                ("Booster", "booster"),
                ("Deck", "deck"),
                ("Common", "single_common"),
                ("Uncommon", "single_uncommon"),
                ("Rare", "single_rare"),
                ("Epic", "single_epic"),
                ("Legendary", "single_legendary"),
            ]
        ):
            self.buttons.append(
                Button(pygame.Rect(px + 220, py + idx * 36, 28, 28), "-", lambda a=attr: self._adjust_price(a, -1))
            )
            self.buttons.append(
                Button(pygame.Rect(px + 260, py + idx * 36, 28, 28), "+", lambda a=attr: self._adjust_price(a, 1))
            )
        rx = self.reorder_panel.rect.x + 20
        ry = self.reorder_panel.rect.y + 50
        self.buttons.append(Button(pygame.Rect(rx, ry, 280, 32), "Order 5 Boosters ($20)", self._order_boosters))
        self.buttons.append(Button(pygame.Rect(rx, ry + 40, 280, 32), "Order 3 Decks ($30)", self._order_decks))
        for idx, rarity in enumerate(RARITIES):
            self.buttons.append(
                Button(
                    pygame.Rect(rx, ry + 88 + idx * 34, 280, 30),
                    f"Order 5 {rarity.title()} Singles (${5 + idx * 2})",
                    lambda r=rarity, c=5 + idx * 2: self._order_singles(r, c),
                )
            )
        sx = self.shelf_panel.rect.x + 520
        sy = self.shelf_panel.rect.y + 50
        self.buttons.extend(
            [
                Button(pygame.Rect(sx, sy, 160, 30), "Prev Product", self._prev_product),
                Button(pygame.Rect(sx + 180, sy, 160, 30), "Next Product", self._next_product),
                Button(pygame.Rect(sx, sy + 50, 160, 30), "Stock 1", lambda: self._stock_shelf(1)),
                Button(pygame.Rect(sx + 180, sy + 50, 160, 30), "Stock 5", lambda: self._stock_shelf(5)),
                Button(pygame.Rect(sx, sy + 90, 160, 30), "Fill Shelf", self._fill_shelf),
            ]
        )

    def _adjust_price(self, attr: str, delta: int) -> None:
        current = getattr(self.app.state.prices, attr)
        current = max(1, current + delta)
        setattr(self.app.state.prices, attr, current)

    def _order_boosters(self) -> None:
        cost = 20
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(5, 0, {}, cost, self.app.state.day + 1))

    def _order_decks(self) -> None:
        cost = 30
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(0, 3, {}, cost, self.app.state.day + 1))

    def _order_singles(self, rarity: str, cost: int) -> None:
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(0, 0, {rarity: 5}, cost, self.app.state.day + 1))

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

    def on_enter(self) -> None:
        self._refresh_shelves()

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        for button in self.buttons:
            button.handle_event(event)
        self.shelf_list.handle_event(event)

    def update(self, dt: float) -> None:
        super().update(dt)
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.pricing_panel.draw(surface, self.theme)
        self.reorder_panel.draw(surface, self.theme)
        self.shelf_panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        self._draw_pricing(surface)
        self._draw_inventory(surface)
        self.shelf_list.draw(surface, self.theme)
        self._draw_shelf_status(surface)

    def _draw_pricing(self, surface: pygame.Surface) -> None:
        px = self.pricing_panel.rect.x + 20
        py = self.pricing_panel.rect.y + 50
        prices = self.app.state.prices
        lines = [
            ("Booster", prices.booster),
            ("Deck", prices.deck),
            ("Common", prices.single_common),
            ("Uncommon", prices.single_uncommon),
            ("Rare", prices.single_rare),
            ("Epic", prices.single_epic),
            ("Legendary", prices.single_legendary),
        ]
        for idx, (label, value) in enumerate(lines):
            text = self.theme.font_small.render(f"{label}: ${value}", True, self.theme.colors.text)
            surface.blit(text, (px, py + idx * 36))

    def _draw_inventory(self, surface: pygame.Surface) -> None:
        inv = self.app.state.inventory
        x = self.reorder_panel.rect.x + 320
        y = self.reorder_panel.rect.y + 50
        lines = [f"Boosters: {inv.booster_packs}", f"Decks: {inv.decks}"]
        for rarity in RARITIES:
            lines.append(f"{rarity.title()}: {inv.singles.get(rarity, 0)}")
        for line in lines:
            text = self.theme.font_small.render(line, True, self.theme.colors.text)
            surface.blit(text, (x, y))
            y += 20

    def _draw_shelf_status(self, surface: pygame.Surface) -> None:
        product = self.products[self.product_index]
        label = self.theme.font_small.render(f"Selected product: {product}", True, self.theme.colors.text)
        surface.blit(label, (self.shelf_panel.rect.x + 520, self.shelf_panel.rect.y + 20))
