from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel


class ResultsScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.panel = Panel(pygame.Rect(380, 180, 520, 320), "Battle Results")
        self.buttons = [
            Button(pygame.Rect(420, 400, 180, 36), "Back to Menu", self._to_menu),
            Button(pygame.Rect(620, 400, 180, 36), "Battle Again", self._to_battle),
        ]
        self.buttons[0].tooltip = "Return to the main menu."
        self.buttons[1].tooltip = "Start another battle immediately."
        self.win = False

    def set_result(self, win: bool) -> None:
        self.win = win

    def _to_menu(self) -> None:
        self.app.switch_scene("menu")

    def _to_battle(self) -> None:
        self.app.switch_scene("battle")

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        for button in self.buttons:
            button.handle_event(event)

    def update(self, dt: float) -> None:
        super().update(dt)
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        text = "Victory!" if self.win else "Defeat"
        reward = "+$15 and 1 pack" if self.win else "No reward"
        title = self.theme.font_large.render(text, True, self.theme.colors.text)
        surface.blit(title, (self.panel.rect.x + 40, self.panel.rect.y + 60))
        sub = self.theme.font.render(reward, True, self.theme.colors.muted)
        surface.blit(sub, (self.panel.rect.x + 40, self.panel.rect.y + 120))
        self.draw_overlays(surface)
