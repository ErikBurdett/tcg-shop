from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel, ScrollList, ScrollItem
from game.sim.inventory import InventoryOrder, RARITIES
from game.sim.economy_rules import effective_sale_price
from game.sim.skill_tree import get_default_skill_tree
from game.cards.card_defs import CARD_INDEX


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
        mode_btn = Button(
            pygame.Rect(px, self.pricing_panel.rect.y + 14, 300, 30),
            f"Pricing Mode: {'Markup %' if self.app.state.pricing.mode == 'markup' else 'Absolute'}",
            self._toggle_pricing_mode,
        )
        mode_btn.tooltip = "Toggle retail pricing mode. Wholesale ordering costs and market prices are unaffected."
        self.buttons.append(mode_btn)
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
            minus = Button(pygame.Rect(px + 220, py + idx * 36, 28, 28), "-", lambda a=attr: self._adjust_price(a, -1))
            plus = Button(pygame.Rect(px + 260, py + idx * 36, 28, 28), "+", lambda a=attr: self._adjust_price(a, 1))
            if self.app.state.pricing.mode == "markup":
                minus.tooltip = f"Decrease {label} markup by 1% (retail only)."
                plus.tooltip = f"Increase {label} markup by 1% (retail only)."
            else:
                minus.tooltip = f"Decrease {label} retail price by $1."
                plus.tooltip = f"Increase {label} retail price by $1."
            self.buttons.extend([minus, plus])
        rx = self.reorder_panel.rect.x + 20
        ry = self.reorder_panel.rect.y + 50
        booster_qty = 12
        deck_qty = 4
        booster_cost = self._wholesale_cost("booster", booster_qty)
        deck_cost = self._wholesale_cost("deck", deck_qty)
        self.buttons.append(
            Button(pygame.Rect(rx, ry, 280, 32), f"Order {booster_qty} Boosters (${booster_cost})", self._order_boosters)
        )
        self.buttons[-1].tooltip = "Order boosters (delivers after ~30 seconds)."
        self.buttons.append(
            Button(pygame.Rect(rx, ry + 40, 280, 32), f"Order {deck_qty} Decks (${deck_cost})", self._order_decks)
        )
        self.buttons[-1].tooltip = "Order decks (delivers after ~30 seconds)."
        for idx, rarity in enumerate(RARITIES):
            singles_qty = 10
            singles_cost = self._wholesale_cost(f"single_{rarity}", singles_qty)
            btn = Button(
                pygame.Rect(rx, ry + 88 + idx * 34, 280, 30),
                f"Order {singles_qty} {rarity.title()} Singles (${singles_cost})",
                lambda r=rarity: self._order_singles(r),
            )
            btn.tooltip = "Order singles by rarity (delivers after ~30 seconds)."
            self.buttons.append(btn)
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
        for b in self.buttons:
            if b.text == "Prev Product":
                b.tooltip = "Select previous product type for stocking."
            elif b.text == "Next Product":
                b.tooltip = "Select next product type for stocking."
            elif b.text == "Stock 1":
                b.tooltip = "Stock 1 unit to the selected shelf."
            elif b.text == "Stock 5":
                b.tooltip = "Stock 5 units to the selected shelf."
            elif b.text == "Fill Shelf":
                b.tooltip = "Fill the selected shelf to capacity."

    def _adjust_price(self, attr: str, delta: int) -> None:
        if self.app.state.pricing.mode == "markup":
            cur = float(self.app.state.pricing.get_markup_pct(attr))
            self.app.state.pricing.set_markup_pct(attr, cur + (float(delta) / 100.0))
            self._build_buttons()
            return
        current = getattr(self.app.state.prices, attr)
        current = max(1, current + delta)
        setattr(self.app.state.prices, attr, current)

    def _toggle_pricing_mode(self) -> None:
        if self.app.state.pricing.mode == "absolute":
            self.app.state.pricing.mode = "markup"
        else:
            self.app.state.pricing.mode = "absolute"
        self._build_buttons()

    def _wholesale_cost(self, product: str, qty: int) -> int:
        from game.sim.pricing import wholesale_order_total

        total = wholesale_order_total(product, qty)
        return int(total or 0)

    def _order_boosters(self) -> None:
        qty = 12
        cost = self._wholesale_cost("booster", qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(qty, 0, {}, cost, 0, self.app.state.time_seconds + 30.0))

    def _order_decks(self) -> None:
        qty = 4
        cost = self._wholesale_cost("deck", qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(0, qty, {}, cost, 0, self.app.state.time_seconds + 30.0))

    def _order_singles(self, rarity: str) -> None:
        qty = 10
        cost = self._wholesale_cost(f"single_{rarity}", qty)
        if self.app.state.money < cost:
            return
        self.app.state.money -= cost
        self.app.state.pending_orders.append(InventoryOrder(0, 0, {rarity: qty}, cost, 0, self.app.state.time_seconds + 30.0))

    def _refresh_shelves(self) -> None:
        layout = self.app.state.shop_layout
        items: list[ScrollItem] = []
        prices = self.app.state.prices
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        for key, stock in layout.shelf_stocks.items():
            x, y = key.split(",")
            value = 0
            if stock.qty > 0 and getattr(stock, "cards", None):
                for cid in stock.cards:
                    card = CARD_INDEX.get(cid)
                    if not card:
                        continue
                    p = effective_sale_price(prices, f"single_{card.rarity}", mods, self.app.state.pricing)
                    if p:
                        value += int(p)
            elif stock.qty > 0:
                p = effective_sale_price(prices, stock.product, mods, self.app.state.pricing)
                if p:
                    value = int(p) * int(stock.qty)
            label = f"Shelf ({x},{y}) - {stock.product} x{stock.qty} | ${value}"
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
        self.draw_overlays(surface)

    def _draw_pricing(self, surface: pygame.Surface) -> None:
        px = self.pricing_panel.rect.x + 20
        py = self.pricing_panel.rect.y + 50
        prices = self.app.state.prices
        mods = self.app.state.skills.modifiers(get_default_skill_tree())
        from game.sim.pricing import retail_base_price, wholesale_unit_cost
        mode = self.app.state.pricing.mode
        lines = [
            ("Booster", "booster", int(prices.booster)),
            ("Deck", "deck", int(prices.deck)),
            ("Common", "single_common", int(prices.single_common)),
            ("Uncommon", "single_uncommon", int(prices.single_uncommon)),
            ("Rare", "single_rare", int(prices.single_rare)),
            ("Epic", "single_epic", int(prices.single_epic)),
            ("Legendary", "single_legendary", int(prices.single_legendary)),
        ]
        for idx, (label, product, base) in enumerate(lines):
            retail = retail_base_price(prices, self.app.state.pricing, product) or base
            eff = effective_sale_price(prices, product, mods, self.app.state.pricing) or retail
            w = wholesale_unit_cost(product) or 0
            if w > 0:
                margin = int(round(((retail - w) / float(w)) * 100.0))
                info = f"W${w} → R${retail} ({margin:+d}%) | sell ${eff}"
            else:
                info = f"R${retail} | sell ${eff}"
            abs_txt = f" (abs ${base})" if mode == "markup" else ""
            text = self.theme.font_small.render(f"{label}: {info}{abs_txt}", True, self.theme.colors.text)
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
