from __future__ import annotations

import pygame


class InputMap:
    """Maps keys to named actions."""

    def __init__(self) -> None:
        self.bindings = {
            "back": pygame.K_ESCAPE,
            "debug": pygame.K_F3,
            "end_turn": pygame.K_SPACE,
            "console": pygame.K_BACKQUOTE,
        }

    def is_action(self, event: pygame.event.Event, action: str) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        return event.key == self.bindings.get(action)
