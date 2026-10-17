"""Last known content of the 99 user slots, so the app can show it instantly.

Refreshed by `gt1 list` / `gt1 status` (one small read per slot) and updated whenever tonematch writes a
slot itself. The device stays the truth: anything changed on the unit or in BTS shows after a refresh.
"""

from __future__ import annotations

import json
import time

from ...config import DATA_DIR
from .patch import Patch

CACHE = DATA_DIR / "gt1_slots.json"


def load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"updated": None, "slots": []}


def save(slots: list[dict]) -> None:
    CACHE.write_text(json.dumps({"updated": time.time(), "slots": slots}, ensure_ascii=False, indent=1), encoding="utf-8")


def remember_write(slot_label: str, patch: Patch) -> None:
    """tonematch just wrote `patch` to `slot_label` (U01..U99)."""
    data = load()
    if not data["slots"]:
        return
    for s in data["slots"]:
        if s["slot"] == slot_label:
            s.update(name=patch.name.ljust(16), amp=str(patch.get("preamp_a_type")), gain=patch.get("preamp_a_gain"))
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
