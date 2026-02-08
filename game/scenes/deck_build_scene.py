from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel, ScrollList, ScrollItem, Tooltip
from game.cards.card_defs import CARD_INDEX


class DeckBuildScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.collection_panel = Panel(pygame.Rect(40, 80, 520, 560), "Collection")
        self.deck_panel = Panel(pygame.Rect(600, 80, 520, 560), "Deck")
        self.buttons: list[Button] = []
        self.collection_list = ScrollList(pygame.Rect(60, 140, 480, 420), [])
        self.deck_list = ScrollList(pygame.Rect(620, 140, 480, 420), [])
        self.selected_collection: str | None = None
        self.selected_deck: str | None = None
        self.filter_rarity: str | None = None
        self.tooltip = Tooltip()
        self._build_buttons()
        self._refresh_lists()

    def _build_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(60, 100, 90, 30), "All", lambda: self._set_filter(None)),
            Button(pygame.Rect(160, 100, 90, 30), "Common", lambda: self._set_filter("common")),
            Button(pygame.Rect(260, 100, 90, 30), "Uncommon", lambda: self._set_filter("uncommon")),
            Button(pygame.Rect(360, 100, 90, 30), "Rare+", lambda: self._set_filter("rare")),
            Button(pygame.Rect(620, 100, 90, 30), "Add", self._add_selected),
            Button(pygame.Rect(720, 100, 90, 30), "Remove", self._remove_selected),
        ]
        tips = {
            "All": "Show all cards in your collection.",
            "Common": "Filter collection to common cards only.",
            "Uncommon": "Filter collection to uncommon cards only.",
            "Rare+": "Filter collection to rare/epic/legendary cards.",
            "Add": "Add the selected collection card to your deck (if allowed).",
            "Remove": "Remove the selected deck card.",
        }
        for b in self.buttons:
            b.tooltip = tips.get(b.text)

    def _set_filter(self, rarity: str | None) -> None:
        self.filter_rarity = rarity
        self._refresh_lists()

    def _refresh_lists(self) -> None:
        collection_items = []
        entries = self.app.state.collection.entries(None if self.filter_rarity != "rare" else None)
        for entry in entries:
            card = CARD_INDEX[entry.card_id]
            if self.filter_rarity and self.filter_rarity != "rare" and card.rarity != self.filter_rarity:
                continue
            if self.filter_rarity == "rare" and card.rarity not in {"rare", "epic", "legendary"}:
                continue
            label = f"{card.name} ({card.rarity}) x{entry.qty}"
            collection_items.append(ScrollItem(entry.card_id, label, entry))
        self.collection_list.items = collection_items
        self.collection_list.on_select = self._select_collection
        deck_items = []
        for card_id, qty in self.app.state.deck.summary():
            card = CARD_INDEX[card_id]
            label = f"{card.name} x{qty}"
            deck_items.append(ScrollItem(card_id, label, card))
        self.deck_list.items = deck_items
        self.deck_list.on_select = self._select_deck

    def _select_collection(self, item: ScrollItem) -> None:
        self.selected_collection = item.key

    def _select_deck(self, item: ScrollItem) -> None:
        self.selected_deck = item.key

    def _add_selected(self) -> None:
        if not self.selected_collection:
            return
        if self.app.state.collection.get(self.selected_collection) <= self.app.state.deck.cards.get(self.selected_collection, 0):
            return
        if self.app.state.deck.add(self.selected_collection):
            self._refresh_lists()

    def _remove_selected(self) -> None:
        if not self.selected_deck:
            return
        if self.app.state.deck.remove(self.selected_deck):
            self._refresh_lists()

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        for button in self.buttons:
            button.handle_event(event)
        self.collection_list.handle_event(event)
        self.deck_list.handle_event(event)

    def _extra_tooltip_text(self, pos: tuple[int, int]) -> str | None:
        idx = self.collection_list._index_at_pos(pos)
        if idx is not None:
            card_id = self.collection_list.items[idx].key
            card = CARD_INDEX[card_id]
            return f"{card.name} ({card.rarity.title()}) Cost {card.cost}"
        idx = self.deck_list._index_at_pos(pos)
        if idx is not None:
            card_id = self.deck_list.items[idx].key
            card = CARD_INDEX[card_id]
            return f"{card.name} {card.attack}/{card.health}"
        return None

    def update(self, dt: float) -> None:
        super().update(dt)
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.collection_panel.draw(surface, self.theme)
        self.deck_panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        self.collection_list.draw(surface, self.theme)
        self.deck_list.draw(surface, self.theme)
        deck_count = self.app.state.deck.total()
        status = "Ready" if self.app.state.deck.is_valid() else "Need 20 cards"
        text = self.theme.font_small.render(f"Deck: {deck_count}/20 - {status}", True, self.theme.colors.text)
        surface.blit(text, (620, 570))
        self.draw_overlays(surface)

    # Tooltip handling is provided via Scene._extra_tooltip_text.
