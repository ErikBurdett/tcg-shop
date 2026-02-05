from __future__ import annotations

import pygame

from game.core.scene import Scene
from game.ui.widgets import Button, Panel
from game.ui.layout import anchor_rect
from game.config import PROJECT_URL, RECENT_UPDATES
from game.core.save import SaveSlotInfo


class MenuScene(Scene):
    def __init__(self, app: "GameApp") -> None:
        super().__init__(app)
        self.show_top_bar = False
        self.buttons: list[Button] = []
        self.selected_slot = 1
        self.renaming = False
        self.name_input = ""
        self._last_screen_size = self.app.screen.get_size()
        self.saves_panel = Panel(anchor_rect(app.screen, (640, 520), "center"), None)
        self.side_panel = Panel(anchor_rect(app.screen, (420, 520), "topright"), None)
        self._layout()
        self._build_buttons()

    def _layout(self) -> None:
        sw, sh = self.app.screen.get_size()
        pad = 18
        title_h = 70
        saves_w = min(780, max(620, int(sw * 0.55)))
        side_w = min(520, max(380, int(sw * 0.32)))
        height = min(560, max(460, sh - title_h - pad * 2))
        x0 = (sw - (saves_w + pad + side_w)) // 2
        y0 = title_h
        self.saves_panel = Panel(pygame.Rect(x0, y0, saves_w, height), None)
        self.side_panel = Panel(pygame.Rect(x0 + saves_w + pad, y0, side_w, height), None)

    def _slot_infos(self) -> list[SaveSlotInfo]:
        return self.app.save.list_slots()

    def _build_buttons(self) -> None:
        self.buttons = []
        rect = self.saves_panel.rect
        pad = 18
        x = rect.x + pad
        y = rect.y + pad
        w = rect.width - pad * 2
        slot_h = 58
        gap = 12

        slots = self._slot_infos()
        for i, info in enumerate(slots):
            label = f"Slot {info.slot_id}: {info.name}"
            if info.exists and info.day is not None and info.money is not None:
                label += f"  (Day {info.day}, ${info.money})"
            elif not info.exists:
                label += "  (Empty)"
            btn = Button(pygame.Rect(x, y + i * (slot_h + gap), w, slot_h), label, lambda sid=info.slot_id: self._select_slot(sid))
            self.buttons.append(btn)

        ay = y + len(slots) * (slot_h + gap) + 10
        bw = (w - gap) // 2
        load_btn = Button(pygame.Rect(x, ay, bw, 44), "Load", self._load_selected)
        new_btn = Button(pygame.Rect(x + bw + gap, ay, bw, 44), "New Game", self._new_selected)
        ren_btn = Button(pygame.Rect(x, ay + 56, bw, 44), "Rename", self._toggle_rename)
        del_btn = Button(pygame.Rect(x + bw + gap, ay + 56, bw, 44), "Delete", self._delete_selected)
        exit_btn = Button(pygame.Rect(x, ay + 112, w, 44), "Exit", self._exit)
        self.buttons.extend([load_btn, new_btn, ren_btn, del_btn, exit_btn])

        # Enable/disable based on slot state
        exists = self.app.save.exists(self.selected_slot)
        load_btn.enabled = exists
        del_btn.enabled = exists

        # Rename UI hint uses the dev console font rendering; input handled in events.
        if self.renaming:
            # visually indicate rename mode by changing button text
            ren_btn.text = "Renaming..."

    def _select_slot(self, slot_id: int) -> None:
        self.selected_slot = slot_id
        self.renaming = False
        self.name_input = ""
        self._build_buttons()

    def _continue(self) -> None:
        self._load_selected()

    def _new_game(self) -> None:
        self._new_selected()

    def _load_selected(self) -> None:
        if self.app.save.exists(self.selected_slot):
            self.app.load_game_slot(self.selected_slot)
            self.app.switch_scene("shop")

    def _new_selected(self) -> None:
        self.app.active_slot = self.selected_slot
        self.app.start_new_game(save=True)

    def _toggle_rename(self) -> None:
        self.renaming = not self.renaming
        self.name_input = self.app.save.get_slot_name(self.selected_slot) if self.renaming else ""
        self._build_buttons()

    def _commit_rename(self) -> None:
        self.app.save.set_slot_name(self.selected_slot, self.name_input)
        self.renaming = False
        self.name_input = ""
        self._build_buttons()

    def _delete_selected(self) -> None:
        self.app.save.delete(self.selected_slot)
        self._build_buttons()

    def _exit(self) -> None:
        self.app.running = False

    def handle_event(self, event: pygame.event.Event) -> None:
        super().handle_event(event)
        if self.renaming and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.renaming = False
                self.name_input = ""
                self._build_buttons()
                return
            if event.key == pygame.K_RETURN:
                self._commit_rename()
                return
            if event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
                return
            if event.unicode and len(self.name_input) < 24:
                if event.unicode.isprintable():
                    self.name_input += event.unicode
                return
        for button in self.buttons:
            button.handle_event(event)

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.app.screen.get_size() != self._last_screen_size:
            self._last_screen_size = self.app.screen.get_size()
            self._layout()
            self._build_buttons()
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        # Title
        title = self.theme.font_title.render("Card Shop Idle", True, self.theme.colors.text)
        surface.blit(title, title.get_rect(centerx=surface.get_width() // 2, y=16))

        # Panels
        self.saves_panel.draw(surface, self.theme)
        self.side_panel.draw(surface, self.theme)

        # Saves panel header
        hdr = self.theme.font_large.render("Save Slots", True, self.theme.colors.text)
        surface.blit(hdr, (self.saves_panel.rect.x + 18, self.saves_panel.rect.y + 12))

        # Side panel content
        sx = self.side_panel.rect.x + 18
        sy = self.side_panel.rect.y + 16

        def wrap_lines(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
            """Simple word wrap for menu text."""
            words = text.split()
            if not words:
                return [""]
            lines: list[str] = []
            cur = words[0]
            for w in words[1:]:
                trial = f"{cur} {w}"
                if font.size(trial)[0] <= max_width:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines

        welcome = [
            "Welcome!",
            "This game is in early development.",
            "",
            "Project:",
            PROJECT_URL,
            "",
            "Tip: Select a slot, then Load/New Game.",
            "Rename lets you label slots.",
        ]
        for line in welcome:
            font = self.theme.font if line and line != PROJECT_URL else self.theme.font_small
            color = self.theme.colors.text if line and line != PROJECT_URL else self.theme.colors.muted
            text = font.render(line, True, color)
            surface.blit(text, (sx, sy))
            sy += 24 if font == self.theme.font else 18

        # Recent updates (commit-style notes)
        sy += 10
        hdr2 = self.theme.font_large.render("Recent updates", True, self.theme.colors.text)
        surface.blit(hdr2, (sx, sy))
        sy += 28

        max_w = self.side_panel.rect.width - 36
        for note in RECENT_UPDATES[:5]:
            bullet = f"- {note}"
            for wrapped in wrap_lines(bullet, self.theme.font_small, max_w):
                t = self.theme.font_small.render(wrapped, True, self.theme.colors.muted)
                surface.blit(t, (sx, sy))
                sy += 18

        # Rename field
        if self.renaming:
            rx = self.saves_panel.rect.x + 18
            ry = self.saves_panel.rect.bottom - 56
            label = self.theme.font_small.render("Slot name:", True, self.theme.colors.muted)
            surface.blit(label, (rx, ry))
            box = pygame.Rect(rx + 76, ry - 4, self.saves_panel.rect.width - 18 * 2 - 86, 28)
            pygame.draw.rect(surface, self.theme.colors.panel_alt, box)
            pygame.draw.rect(surface, self.theme.colors.border, box, 1)
            val = self.theme.font_small.render(self.name_input or "", True, self.theme.colors.text)
            surface.blit(val, (box.x + 8, box.y + 6))

        for button in self.buttons:
            button.draw(surface, self.theme)
