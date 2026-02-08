from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.cards.battle import BattleState
from game.cards.card_defs import CARD_INDEX
from game.ui.widgets import Button, Panel, Tooltip
from game.assets import get_asset_manager
from game.ui.effects import draw_glow_border
from game.sim.economy_rules import xp_from_battle_win
from game.sim.skill_tree import get_default_skill_tree


class BattleScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.panel = Panel(pygame.Rect(40, 80, 1200, 560), "Battle")
        self.tooltip = Tooltip()
        self.end_button = Button(pygame.Rect(1040, 620, 180, 36), "End Turn (Space)", self._end_turn)
        self.battle: BattleState | None = None
        self.selected_attacker: int | None = None

    def on_enter(self) -> None:
        if not self.app.state.deck.is_valid():
            self.battle = None
            return
        player_deck = self.app.state.deck.shuffled(self.app.rng)
        ai_deck = self.app.state.deck.shuffled(self.app.rng)
        self.battle = BattleState(player_deck, ai_deck, self.app.rng)
        self.battle.start()
        self.selected_attacker = None

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        self.end_button.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._end_turn()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.battle:
            self._handle_click(event.pos)
        if event.type == pygame.MOUSEMOTION and self.battle:
            self._update_tooltip(event.pos)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.end_button.update(dt)
        if self.battle:
            winner = self.battle.winner()
            if winner:
                self._finish_battle(winner)

    def _finish_battle(self, winner: str) -> None:
        if winner == "player":
            self.app.state.money += 15
            self.app.state.inventory.booster_packs += 1
            mods = self.app.state.skills.modifiers(get_default_skill_tree())
            self.app.state.progression.add_xp(xp_from_battle_win(mods))
        self.app.save_game()
        results_scene = self.app.scenes["results"]
        results_scene.set_result(winner == "player")
        self.app.switch_scene("results")

    def _end_turn(self) -> None:
        if self.battle:
            self.battle.end_turn()

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if not self.battle:
            return
        hand_rects = self._hand_rects()
        for idx, rect in enumerate(hand_rects):
            if rect.collidepoint(pos):
                self.battle.play_card("player", idx)
                return
        for idx, rect in enumerate(self._board_rects("player")):
            if rect.collidepoint(pos):
                self.selected_attacker = idx
                return
        for idx, rect in enumerate(self._board_rects("ai")):
            if rect.collidepoint(pos) and self.selected_attacker is not None:
                self.battle.attack(self.selected_attacker, idx)
                self.selected_attacker = None
                return
        if self._ai_face_rect().collidepoint(pos) and self.selected_attacker is not None:
            self.battle.attack(self.selected_attacker, None)
            self.selected_attacker = None

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.panel.draw(surface, self.theme)
        if not self.battle:
            text = self.theme.font.render("Build a 20-card deck to battle.", True, self.theme.colors.text)
            surface.blit(text, (60, 140))
            return
        self._draw_board(surface)
        self.end_button.draw(surface, self.theme)
        self.tooltip.draw(surface, self.theme)

    def _draw_board(self, surface: pygame.Surface) -> None:
        if not self.battle:
            return
        self._draw_player_info(surface)
        self._draw_hand(surface)
        self._draw_minions(surface, "player")
        self._draw_minions(surface, "ai")
        self._draw_face(surface, "player")
        self._draw_face(surface, "ai")

    def _draw_player_info(self, surface: pygame.Surface) -> None:
        b = self.battle
        text = self.theme.font_small.render(
            f"HP {b.player_hp} | Mana {b.player_mana}/{b.player_max_mana}", True, self.theme.colors.text
        )
        surface.blit(text, (60, 600))
        ai_text = self.theme.font_small.render(
            f"Enemy HP {b.ai_hp} | Mana {b.ai_mana}/{b.ai_max_mana}", True, self.theme.colors.text
        )
        surface.blit(ai_text, (60, 120))

    def _draw_hand(self, surface: pygame.Surface) -> None:
        if not self.battle:
            return
        asset_mgr = get_asset_manager()
        for idx, card_id in enumerate(self.battle.player_hand):
            rect = self._hand_rects()[idx]
            card = CARD_INDEX[card_id]
            
            # Draw card background with rarity gradient
            bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
            surface.blit(bg, rect.topleft)
            
            # Draw card sprite centered in upper portion
            sprite = asset_mgr.get_card_sprite(card_id, (48, 48))
            if sprite:
                sprite_x = rect.x + (rect.width - 48) // 2
                sprite_y = rect.y + 4
                surface.blit(sprite, (sprite_x, sprite_y))
            
            # Draw border with rarity color
            rarity_color = self._rarity_border_color(card.rarity)
            draw_glow_border(surface, rect, rarity_color, border_width=2, glow_radius=3, glow_alpha=70)
            # Draw id, name, description, stats
            id_text = self.theme.font_small.render(card.card_id.upper(), True, self.theme.colors.muted)
            surface.blit(id_text, (rect.x + 4, rect.y + 2))
            name_text = self.theme.font_small.render(card.name[:10], True, self.theme.colors.text)
            surface.blit(name_text, (rect.x + 4, rect.y + 14))
            desc = (card.description[:12] + "...") if len(card.description) > 12 else card.description
            desc_text = self.theme.font_small.render(desc, True, self.theme.colors.muted)
            surface.blit(desc_text, (rect.x + 4, rect.y + 28))
            stats = self.theme.font_small.render(f"{card.cost}/{card.attack}/{card.health}", True, self.theme.colors.text)
            surface.blit(stats, (rect.x + 4, rect.bottom - 18))

    def _draw_minions(self, surface: pygame.Surface, who: str) -> None:
        if not self.battle:
            return
        asset_mgr = get_asset_manager()
        board = self.battle.player_board if who == "player" else self.battle.ai_board
        for idx, rect in enumerate(self._board_rects(who)):
            minion = board[idx]
            pygame.draw.rect(surface, self.theme.colors.panel_alt, rect)
            pygame.draw.rect(surface, self.theme.colors.border, rect, 1)
            if minion:
                card = CARD_INDEX[minion.card_id]
                
                # Draw card background
                bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
                surface.blit(bg, rect.topleft)
                
                # Draw card sprite centered
                sprite = asset_mgr.get_card_sprite(minion.card_id, (56, 56))
                if sprite:
                    sprite_x = rect.x + (rect.width - 56) // 2
                    sprite_y = rect.y + 4
                    surface.blit(sprite, (sprite_x, sprite_y))
                
                # Draw border with rarity color
                rarity_color = self._rarity_border_color(card.rarity)
                draw_glow_border(surface, rect, rarity_color, border_width=2, glow_radius=3, glow_alpha=70)
                # Draw id, name, description, stats
                id_text = self.theme.font_small.render(card.card_id.upper(), True, self.theme.colors.muted)
                surface.blit(id_text, (rect.x + 4, rect.y + 2))
                name_text = self.theme.font_small.render(card.name[:10], True, self.theme.colors.text)
                surface.blit(name_text, (rect.x + 4, rect.y + 14))
                desc = (card.description[:12] + "...") if len(card.description) > 12 else card.description
                desc_text = self.theme.font_small.render(desc, True, self.theme.colors.muted)
                surface.blit(desc_text, (rect.x + 4, rect.y + 28))
                stats = self.theme.font_small.render(
                    f"{minion.attack}/{minion.health}", True, self.theme.colors.text
                )
                surface.blit(stats, (rect.x + 4, rect.bottom - 18))
            if who == "player" and self.selected_attacker == idx:
                pygame.draw.rect(surface, self.theme.colors.accent, rect, 3)

    def _draw_face(self, surface: pygame.Surface, who: str) -> None:
        rect = self._ai_face_rect() if who == "ai" else self._player_face_rect()
        pygame.draw.rect(surface, self.theme.colors.panel, rect)
        pygame.draw.rect(surface, self.theme.colors.border, rect, 1)
        text = "AI" if who == "ai" else "You"
        label = self.theme.font_small.render(text, True, self.theme.colors.text)
        surface.blit(label, label.get_rect(center=rect.center))

    def _hand_rects(self) -> list[pygame.Rect]:
        rects = []
        x = 60
        y = 640
        for _ in range(len(self.battle.player_hand) if self.battle else 0):
            rects.append(pygame.Rect(x, y, 120, 70))
            x += 130
        return rects

    def _board_rects(self, who: str) -> list[pygame.Rect]:
        rects = []
        x = 220
        y = 440 if who == "player" else 200
        for _ in range(5):
            rects.append(pygame.Rect(x, y, 120, 80))
            x += 130
        return rects

    def _player_face_rect(self) -> pygame.Rect:
        return pygame.Rect(60, 420, 120, 80)

    def _ai_face_rect(self) -> pygame.Rect:
        return pygame.Rect(60, 200, 120, 80)

    def _rarity_border_color(self, rarity: str) -> tuple[int, int, int]:
        """Get border color based on card rarity."""
        colors = self.theme.colors
        return {
            "common": colors.card_common,
            "uncommon": colors.card_uncommon,
            "rare": colors.card_rare,
            "epic": colors.card_epic,
            "legendary": colors.card_legendary,
        }.get(rarity, colors.border)

    def _update_tooltip(self, pos: tuple[int, int]) -> None:
        self.tooltip.hide()
        for idx, rect in enumerate(self._hand_rects()):
            if rect.collidepoint(pos):
                card = CARD_INDEX[self.battle.player_hand[idx]]
                self.tooltip.show(f"{card.rarity.title()} Cost {card.cost}", pos)
                return
        for idx, rect in enumerate(self._board_rects("player")):
            if rect.collidepoint(pos) and self.battle.player_board[idx]:
                minion = self.battle.player_board[idx]
                card = CARD_INDEX[minion.card_id]
                self.tooltip.show(f"{card.name} {minion.attack}/{minion.health}", pos)
                return
