from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel
from game.ui.layout import anchor_rect


class MenuScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.buttons: list[Button] = []
        self.panel = Panel(anchor_rect(app.screen, (360, 260), "center"), "Main Menu")
        self._build_buttons()

    def _build_buttons(self) -> None:
        rect = self.panel.rect
        x = rect.x + 40
        y = rect.y + 60
        w = rect.width - 80
        h = 44
        self.buttons = [
            Button(pygame.Rect(x, y, w, h), "Continue", self._continue),
            Button(pygame.Rect(x, y + 60, w, h), "New Game", self._new_game),
            Button(pygame.Rect(x, y + 120, w, h), "Exit", self._exit),
        ]

    def _continue(self) -> None:
        if self.app.save.exists():
            self.app.load_game()
            self.app.switch_scene("shop")

    def _new_game(self) -> None:
        self.app.state = self.app._new_game_state()
        self.app.switch_scene("shop")

    def _exit(self) -> None:
        self.app.running = False

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        for button in self.buttons:
            button.enabled = self.app.save.exists() if button.text == "Continue" else True
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
        summary = self.app.state.last_summary
        text = self.theme.font_small.render(
            f"Last Day: +${summary.revenue} | Customers {summary.customers}", True, self.theme.colors.muted
        )
        surface.blit(text, (self.panel.rect.x + 40, self.panel.rect.bottom - 36))
