from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from game.config import SAVE_DIR, SAVE_FILE


class SaveManager:
    """Handles saving/loading game state."""

    def __init__(self) -> None:
        self.save_path = self._get_save_path()

    def _get_save_path(self) -> str:
        root = os.path.expanduser("~")
        folder = os.path.join(root, SAVE_DIR)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, SAVE_FILE)

    def exists(self) -> bool:
        return os.path.exists(self.save_path)

    def save(self, data: dict[str, Any]) -> None:
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> dict[str, Any] | None:
        if not self.exists():
            return None
        with open(self.save_path, "r", encoding="utf-8") as f:
            return json.load(f)


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
