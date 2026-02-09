from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel
from game.cards.pack import open_booster
from game.cards.card_defs import CARD_INDEX
from game.assets import get_asset_manager
from game.ui.effects import draw_glow_border
from game.sim.staff_xp import award_staff_xp_total


class PackOpenScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.panel = Panel(pygame.Rect(40, 80, 1200, 560), "Pack Opening")
        self.buttons: list[Button] = []
        self.revealed_cards: list[str] = []
        self.reveal_index = 0
        self.reveal_timer = 0.0
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(60, 620, 160, 36), "Open Pack", self.open_pack),
            Button(pygame.Rect(230, 620, 160, 36), "Reveal All", self.reveal_all),
        ]
        self.buttons[0].tooltip = "Open a booster pack (consumes 1 from inventory)."
        self.buttons[1].tooltip = "Reveal all cards in the current pack."

    def open_pack(self) -> None:
        if self.app.state.inventory.booster_packs <= 0:
            return
        self.app.state.inventory.booster_packs -= 1
        r = award_staff_xp_total(self.app.state.shopkeeper_xp, "pack_open", 1)
        if r.gained_xp > 0:
            self.app.state.shopkeeper_xp = int(r.new_xp)
            self.toasts.push(f"+{r.gained_xp} Staff XP")
            if r.leveled_up:
                self.toasts.push(f"Staff level up! Lv {r.new_level}")
        self.revealed_cards = open_booster(self.app.rng)
        for card_id in self.revealed_cards:
            self.app.state.collection.add(card_id, 1)
        self.reveal_index = 0
        self.reveal_timer = 0.0

    def reveal_all(self) -> None:
        self.reveal_index = len(self.revealed_cards)

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        for button in self.buttons:
            button.handle_event(event)

    def _extra_tooltip_text(self, pos: tuple[int, int]) -> str | None:
        start_x = 100
        y = 160
        for idx, card_id in enumerate(self.revealed_cards[: self.reveal_index]):
            rect = pygame.Rect(start_x + idx * 200, y, 160, 220)
            if rect.collidepoint(pos):
                card = CARD_INDEX[card_id]
                return f"{card.name} ({card.rarity.title()}) Cost {card.cost}"
        return None

    def update(self, dt: float) -> None:
        super().update(dt)
        for button in self.buttons:
            button.update(dt)
        if self.revealed_cards and self.reveal_index < len(self.revealed_cards):
            self.reveal_timer += dt
            if self.reveal_timer >= 0.4:
                self.reveal_timer = 0.0
                self.reveal_index += 1

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        self._draw_cards(surface)
        self.draw_overlays(surface)

    def _draw_cards(self, surface: pygame.Surface) -> None:
        start_x = 100
        y = 160
        asset_mgr = get_asset_manager()
        
        for idx, card_id in enumerate(self.revealed_cards):
            rect = pygame.Rect(start_x + idx * 200, y, 160, 220)
            if idx < self.reveal_index:
                card = CARD_INDEX[card_id]
                
                # Draw card background with dark fantasy gradient
                bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
                surface.blit(bg, rect.topleft)
                
                # Draw card sprite centered in upper portion
                sprite = asset_mgr.get_card_sprite(card_id, (96, 96))
                if sprite:
                    sprite_x = rect.x + (rect.width - 96) // 2
                    sprite_y = rect.y + 30
                    surface.blit(sprite, (sprite_x, sprite_y))
                
                # Draw rarity border
                rarity_color = self._rarity_color(card.rarity)
                draw_glow_border(surface, rect, rarity_color, border_width=3, glow_radius=5, glow_alpha=90)
                
                # Draw card name at top
                id_text = self.theme.font_small.render(card.card_id.upper(), True, self.theme.colors.muted)
                surface.blit(id_text, (rect.x + 8, rect.y + 6))
                name_text = self.theme.font_small.render(card.name, True, self.theme.colors.text)
                name_rect = name_text.get_rect(centerx=rect.centerx, top=rect.y + 20)
                surface.blit(name_text, name_rect)
                
                # Draw description and stats
                desc = (card.description[:30] + "...") if len(card.description) > 30 else card.description
                desc_text = self.theme.font_small.render(desc, True, self.theme.colors.muted)
                desc_rect = desc_text.get_rect(centerx=rect.centerx, bottom=rect.bottom - 28)
                surface.blit(desc_text, desc_rect)
                stats = self.theme.font_small.render(
                    f"{card.cost} / {card.attack} / {card.health}", True, self.theme.colors.text
                )
                stats_rect = stats.get_rect(centerx=rect.centerx, bottom=rect.bottom - 8)
                surface.blit(stats, stats_rect)
                
                # Draw rarity text
                rarity_text = self.theme.font_small.render(card.rarity.title(), True, rarity_color)
                rarity_rect = rarity_text.get_rect(centerx=rect.centerx, bottom=rect.bottom - 28)
                surface.blit(rarity_text, rarity_rect)
            else:
                # Unrevealed card - show card back
                pygame.draw.rect(surface, self.theme.colors.panel_alt, rect)
                pygame.draw.rect(surface, self.theme.colors.border, rect, 2)
                
                # Draw card back pattern
                for i in range(5):
                    inner_rect = rect.inflate(-10 - i * 8, -10 - i * 8)
                    pygame.draw.rect(surface, (50 + i * 5, 55 + i * 5, 60 + i * 5), inner_rect, 1)
                
                label = self.theme.font_small.render("?", True, self.theme.colors.muted)
                surface.blit(label, label.get_rect(center=rect.center))

    # Tooltip handling is provided via Scene._extra_tooltip_text.

    def _rarity_color(self, rarity: str) -> tuple[int, int, int]:
        colors = self.theme.colors
        return {
            "common": colors.card_common,
            "uncommon": colors.card_uncommon,
            "rare": colors.card_rare,
            "epic": colors.card_epic,
            "legendary": colors.card_legendary,
        }[rarity]
