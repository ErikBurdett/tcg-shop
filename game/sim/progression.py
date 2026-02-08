from __future__ import annotations

from dataclasses import dataclass


MAX_LEVEL = 2000


def xp_to_next(level: int) -> int:
    """XP required to go from `level` to `level+1`.

    Properties:
    - Monotonic increasing for levels 1..(MAX_LEVEL-1)
    - Returns 0 at MAX_LEVEL (cannot level further)
    """
    if level < 1:
        level = 1
    if level >= MAX_LEVEL:
        return 0
    # A simple, monotonic curve that grows roughly quadratically but stays in a safe int range.
    # At level 2000, per-level XP is ~440k and cumulative XP is ~O(1e8-1e9).
    return 100 + 20 * level + (level * level) // 10


def skill_points_for_level(level: int) -> int:
    """Skill points granted upon reaching `level` (after a level-up)."""
    if level <= 1:
        return 0
    return 1


@dataclass
class LevelUpResult:
    gained_levels: int = 0
    gained_skill_points: int = 0


@dataclass
class PlayerProgression:
    """Pure state for player progression."""

    level: int = 1
    xp: int = 0
    skill_points: int = 0

    def add_xp(self, amount: int) -> LevelUpResult:
        """Add XP and apply multi-level-up if thresholds are crossed."""
        if amount <= 0:
            return LevelUpResult()
        if self.level >= MAX_LEVEL:
            return LevelUpResult()
        self.xp += int(amount)
        res = LevelUpResult()
        while self.level < MAX_LEVEL:
            need = xp_to_next(self.level)
            if need <= 0 or self.xp < need:
                break
            self.xp -= need
            self.level += 1
            sp = skill_points_for_level(self.level)
            self.skill_points += sp
            res.gained_levels += 1
            res.gained_skill_points += sp
        # Clamp if we reached cap.
        if self.level >= MAX_LEVEL:
            self.level = MAX_LEVEL
            self.xp = 0
        return res

    def progress_frac(self) -> float:
        """Return current level progress as 0..1."""
        need = xp_to_next(self.level)
        if need <= 0:
            return 1.0
        return max(0.0, min(1.0, self.xp / float(need)))

    def to_dict(self) -> dict[str, int]:
        return {"level": int(self.level), "xp": int(self.xp), "skill_points": int(self.skill_points)}

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "PlayerProgression":
        if not data:
            return cls()
        level = int(data.get("level", 1))  # type: ignore[arg-type]
        xp = int(data.get("xp", 0))  # type: ignore[arg-type]
        sp = int(data.get("skill_points", 0))  # type: ignore[arg-type]
        level = max(1, min(MAX_LEVEL, level))
        xp = max(0, xp)
        sp = max(0, sp)
        # If someone loaded a capped save with leftover xp, normalize.
        if level >= MAX_LEVEL:
            xp = 0
        return cls(level=level, xp=xp, skill_points=sp)

