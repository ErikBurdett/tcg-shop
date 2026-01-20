from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import random

from game.cards.card_defs import CARD_INDEX, CardDef


@dataclass
class Minion:
    card_id: str
    attack: int
    health: int
    can_attack: bool = False

    @classmethod
    def from_card(cls, card: CardDef) -> "Minion":
        return cls(card.card_id, card.attack, card.health, can_attack=False)


class BattleState:
    def __init__(self, player_deck: list[str], ai_deck: list[str], rng: random.Random) -> None:
        self.rng = rng
        self.player_deck = list(player_deck)
        self.ai_deck = list(ai_deck)
        self.player_hand: list[str] = []
        self.ai_hand: list[str] = []
        self.player_board: list[Optional[Minion]] = [None] * 5
        self.ai_board: list[Optional[Minion]] = [None] * 5
        self.player_hp = 20
        self.ai_hp = 20
        self.player_mana = 0
        self.ai_mana = 0
        self.player_max_mana = 0
        self.ai_max_mana = 0
        self.active_player = "player"
        self.turn = 1

    def start(self) -> None:
        self.rng.shuffle(self.player_deck)
        self.rng.shuffle(self.ai_deck)
        for _ in range(3):
            self.draw("player")
            self.draw("ai")
        self._start_turn("player")

    def _start_turn(self, who: str) -> None:
        if who == "player":
            self.player_max_mana = min(10, self.player_max_mana + 1)
            self.player_mana = self.player_max_mana
            self._refresh_board(self.player_board)
        else:
            self.ai_max_mana = min(10, self.ai_max_mana + 1)
            self.ai_mana = self.ai_max_mana
            self._refresh_board(self.ai_board)
        self.draw(who)

    def _refresh_board(self, board: list[Optional[Minion]]) -> None:
        for minion in board:
            if minion:
                minion.can_attack = True

    def draw(self, who: str) -> None:
        deck = self.player_deck if who == "player" else self.ai_deck
        hand = self.player_hand if who == "player" else self.ai_hand
        if deck:
            hand.append(deck.pop())

    def play_card(self, who: str, hand_index: int) -> bool:
        hand = self.player_hand if who == "player" else self.ai_hand
        board = self.player_board if who == "player" else self.ai_board
        mana = self.player_mana if who == "player" else self.ai_mana
        if hand_index < 0 or hand_index >= len(hand):
            return False
        card = CARD_INDEX[hand[hand_index]]
        if mana < card.cost:
            return False
        slot = self._first_open_slot(board)
        if slot is None:
            return False
        minion = Minion.from_card(card)
        board[slot] = minion
        hand.pop(hand_index)
        if who == "player":
            self.player_mana -= card.cost
        else:
            self.ai_mana -= card.cost
        return True

    def _first_open_slot(self, board: list[Optional[Minion]]) -> int | None:
        for idx, minion in enumerate(board):
            if minion is None:
                return idx
        return None

    def attack(self, attacker_idx: int, target_idx: int | None) -> None:
        if self.active_player != "player":
            return
        attacker = self.player_board[attacker_idx]
        if not attacker or not attacker.can_attack:
            return
        if target_idx is None:
            if any(self.ai_board):
                return
            self.ai_hp -= attacker.attack
        else:
            target = self.ai_board[target_idx]
            if not target:
                return
            target.health -= attacker.attack
            attacker.health -= target.attack
            if target.health <= 0:
                self.ai_board[target_idx] = None
            if attacker.health <= 0:
                self.player_board[attacker_idx] = None
        attacker.can_attack = False

    def end_turn(self) -> None:
        if self.active_player == "player":
            self.active_player = "ai"
            self._start_turn("ai")
            self.ai_take_turn()
            self.active_player = "player"
            self.turn += 1
            self._start_turn("player")

    def ai_take_turn(self) -> None:
        played = True
        while played:
            played = False
            playable = [
                (idx, CARD_INDEX[card_id])
                for idx, card_id in enumerate(self.ai_hand)
                if CARD_INDEX[card_id].cost <= self.ai_mana
            ]
            playable.sort(key=lambda item: item[1].cost)
            if playable:
                idx, _ = playable[0]
                played = self.play_card("ai", idx)
        for idx, minion in enumerate(self.ai_board):
            if not minion or not minion.can_attack:
                continue
            target_idx = self._ai_choose_target(minion)
            if target_idx is None:
                self.player_hp -= minion.attack
            else:
                target = self.player_board[target_idx]
                if target:
                    target.health -= minion.attack
                    minion.health -= target.attack
                    if target.health <= 0:
                        self.player_board[target_idx] = None
                    if minion.health <= 0:
                        self.ai_board[idx] = None
            if minion:
                minion.can_attack = False

    def _ai_choose_target(self, minion: Minion) -> int | None:
        if not any(self.player_board):
            return None
        lethal_targets = [
            idx
            for idx, target in enumerate(self.player_board)
            if target and target.health <= minion.attack
        ]
        if lethal_targets:
            return lethal_targets[0]
        favorable = [
            idx
            for idx, target in enumerate(self.player_board)
            if target and minion.attack >= target.attack
        ]
        if favorable:
            return favorable[0]
        for idx, target in enumerate(self.player_board):
            if target:
                return idx
        return None

    def winner(self) -> str | None:
        if self.player_hp <= 0:
            return "ai"
        if self.ai_hp <= 0:
            return "player"
        return None
