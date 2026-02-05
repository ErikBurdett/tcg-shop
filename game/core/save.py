from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from dataclasses import asdict
from typing import Any

from game.config import SAVE_DIR, SAVE_FILE, SAVE_META_FILE, SAVE_SLOTS, SAVE_SLOT_TEMPLATE


@dataclass
class SaveSlotInfo:
    slot_id: int
    name: str
    exists: bool
    saved_at: float | None = None
    day: int | None = None
    money: int | None = None


class SaveManager:
    """Handles saving/loading game state."""

    def __init__(self) -> None:
        self.save_folder = self._get_save_folder()
        self.legacy_save_path = os.path.join(self.save_folder, SAVE_FILE)
        self.meta_path = os.path.join(self.save_folder, SAVE_META_FILE)
        self._migrate_legacy_to_slot1()

    def _get_save_folder(self) -> str:
        root = os.path.expanduser("~")
        folder = os.path.join(root, SAVE_DIR)
        os.makedirs(folder, exist_ok=True)
        return folder

    def _slot_path(self, slot_id: int) -> str:
        slot_id = max(1, min(int(slot_id), SAVE_SLOTS))
        return os.path.join(self.save_folder, SAVE_SLOT_TEMPLATE.format(slot=slot_id))

    def _load_meta(self) -> dict[str, str]:
        if not os.path.exists(self.meta_path):
            return {}
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            return {}
        return {}

    def _save_meta(self, meta: dict[str, str]) -> None:
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def get_slot_name(self, slot_id: int) -> str:
        meta = self._load_meta()
        return meta.get(str(slot_id), f"Slot {slot_id}")

    def set_slot_name(self, slot_id: int, name: str) -> None:
        slot_id = max(1, min(int(slot_id), SAVE_SLOTS))
        name = (name or "").strip()[:24] or f"Slot {slot_id}"
        meta = self._load_meta()
        meta[str(slot_id)] = name
        self._save_meta(meta)
        # If a save exists, update the embedded slot_name too.
        path = self._slot_path(slot_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data["slot_name"] = name
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception:
                pass

    def list_slots(self) -> list[SaveSlotInfo]:
        meta = self._load_meta()
        slots: list[SaveSlotInfo] = []
        for slot_id in range(1, SAVE_SLOTS + 1):
            path = self._slot_path(slot_id)
            name = meta.get(str(slot_id), f"Slot {slot_id}")
            if not os.path.exists(path):
                slots.append(SaveSlotInfo(slot_id=slot_id, name=name, exists=False))
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    name = meta.get(str(slot_id), str(data.get("slot_name") or name))
                    saved_at = float(data.get("saved_at")) if data.get("saved_at") is not None else None
                    day = int(data.get("day")) if data.get("day") is not None else None
                    money = int(data.get("money")) if data.get("money") is not None else None
                    slots.append(
                        SaveSlotInfo(
                            slot_id=slot_id,
                            name=name,
                            exists=True,
                            saved_at=saved_at,
                            day=day,
                            money=money,
                        )
                    )
                else:
                    slots.append(SaveSlotInfo(slot_id=slot_id, name=name, exists=True))
            except Exception:
                slots.append(SaveSlotInfo(slot_id=slot_id, name=name, exists=True))
        return slots

    def exists(self, slot_id: int) -> bool:
        return os.path.exists(self._slot_path(slot_id))

    def save(self, slot_id: int, data: dict[str, Any]) -> None:
        slot_id = max(1, min(int(slot_id), SAVE_SLOTS))
        payload = dict(data)
        payload["slot_name"] = self.get_slot_name(slot_id)
        payload["saved_at"] = time.time()
        with open(self._slot_path(slot_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self, slot_id: int) -> dict[str, Any] | None:
        if not self.exists(slot_id):
            return None
        with open(self._slot_path(slot_id), "r", encoding="utf-8") as f:
            return json.load(f)

    def delete(self, slot_id: int) -> None:
        path = self._slot_path(slot_id)
        if os.path.exists(path):
            os.remove(path)

    def _migrate_legacy_to_slot1(self) -> None:
        """If an old single-save exists, move it into slot 1."""
        slot1 = self._slot_path(1)
        if os.path.exists(slot1):
            return
        if not os.path.exists(self.legacy_save_path):
            return
        try:
            # Copy legacy -> slot1 with minimal metadata.
            with open(self.legacy_save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("slot_name", self.get_slot_name(1))
                data.setdefault("saved_at", time.time())
                with open(slot1, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            os.remove(self.legacy_save_path)
        except Exception:
            # If migration fails, leave legacy file in place.
            return


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
