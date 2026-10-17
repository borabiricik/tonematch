"""Backups of GT-1 user patches as BTS-importable .tsl files."""

from __future__ import annotations

import time
from pathlib import Path

from ...config import PROJECT_ROOT
from .client import GT1Client, slot_label
from .patch import Patch, write_tsl

BACKUP_ROOT = PROJECT_ROOT / "backups"  # small JSON, inside the (OneDrive-synced) project on purpose


def backup_slots(g: GT1Client, slots: list[int], tag: str, progress=None) -> Path:
    patches: list[Patch] = []
    for s in slots:
        p = g.read_patch(s)
        p.meta["note"] = f"backup of {slot_label(s)}"
        patches.append(p)
        if progress:
            progress(s, p)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = BACKUP_ROOT / f"{stamp}_{tag}.tsl"
    write_tsl(path, patches, liveset_name=f"GT-1 backup {tag} {stamp}")
    return path


def backup_all(g: GT1Client, progress=None) -> Path:
    return backup_slots(g, list(range(99)), "all_U01-U99", progress)
