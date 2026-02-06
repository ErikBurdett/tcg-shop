from __future__ import annotations

"""
Verify asset dimensions + alpha rules.

Source of truth: ASSET_MANIFEST.md (Replacement targets section).
"""

import os
import re
import sys
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ASSET_MANIFEST.md"


def _load_expected() -> list[tuple[Path, int, int, bool]]:
    if not MANIFEST.exists():
        raise FileNotFoundError(str(MANIFEST))

    text = MANIFEST.read_text(encoding="utf-8")
    # Parse the first markdown table after the "Replacement targets" header.
    m = re.search(r"##\s+Replacement targets\s*\(generated in this run\)\s*([\s\S]+?)\n##\s", text)
    if not m:
        raise RuntimeError("Could not find 'Replacement targets (generated in this run)' section in ASSET_MANIFEST.md")
    section = m.group(1)

    expected: list[tuple[Path, int, int, bool]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # | `path` | 48×48 | true |
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 3:
            continue
        if not (cols[0].startswith("`") and cols[0].endswith("`")):
            continue
        path = cols[0].strip("`")
        size = cols[1]
        alpha = cols[2].lower()
        if "×" not in size:
            continue
        w_s, h_s = size.split("×", 1)
        w = int(w_s)
        h = int(h_s)
        has_alpha = alpha in ("true", "yes", "1", "✅")
        expected.append((ROOT / path, w, h, has_alpha))
    if not expected:
        raise RuntimeError("No expected assets parsed from Replacement targets table.")
    return expected


def _has_alpha(surf: pygame.Surface) -> bool:
    masks = surf.get_masks()
    flags = surf.get_flags()
    return bool(flags & pygame.SRCALPHA) or (len(masks) >= 4 and masks[3] != 0)


def main() -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))

    expected = _load_expected()
    failures: list[str] = []

    for path, ew, eh, ealpha in expected:
        if not path.exists():
            failures.append(f"missing: {path}")
            continue
        try:
            surf = pygame.image.load(str(path))
        except Exception as e:
            failures.append(f"load-failed: {path} ({e})")
            continue
        w, h = surf.get_size()
        if (w, h) != (ew, eh):
            failures.append(f"size: {path} expected {ew}×{eh}, got {w}×{h}")
        a = _has_alpha(surf)
        if a != ealpha:
            failures.append(f"alpha: {path} expected {ealpha}, got {a}")

    if failures:
        print("ASSET VERIFICATION FAILED")
        for f in failures:
            print("-", f)
        return 1

    print("ASSET VERIFICATION OK")
    print(f"Checked {len(expected)} assets from ASSET_MANIFEST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

