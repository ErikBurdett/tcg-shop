from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import pygame


@dataclass(frozen=True)
class _TextKey:
    font_id: int
    text: str
    color: tuple[int, int, int]


class TextCache:
    """LRU cache for rendered text surfaces.

    Designed for UI: avoid per-frame `font.render(...)` calls for repeated labels.
    """

    def __init__(self, *, max_items: int = 1024) -> None:
        self.max_items = int(max_items)
        self._cache: "OrderedDict[_TextKey, pygame.Surface]" = OrderedDict()
        # Per-frame counters (only meaningful if someone calls begin_frame()).
        self.frame_hits: int = 0
        self.frame_misses: int = 0

    def begin_frame(self) -> None:
        self.frame_hits = 0
        self.frame_misses = 0

    def clear(self) -> None:
        self._cache.clear()

    def render(self, font: pygame.font.Font, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        key = _TextKey(id(font), str(text), tuple(color))
        surf = self._cache.get(key)
        if surf is not None:
            self.frame_hits += 1
            # Refresh LRU
            self._cache.move_to_end(key)
            return surf
        self.frame_misses += 1
        surf = font.render(key.text, True, key.color)
        self._cache[key] = surf
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_items:
            self._cache.popitem(last=False)
        return surf

