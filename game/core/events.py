from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict


EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Simple pub/sub event bus."""

    def __init__(self) -> None:
        self._listeners: DefaultDict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event: str, handler: EventHandler) -> None:
        self._listeners[event].append(handler)

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        if payload is None:
            payload = {}
        for handler in list(self._listeners.get(event, [])):
            handler(payload)
