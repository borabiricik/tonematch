"""Professionally made GT-1 patches (BTS presets + downloaded Tone Central livesets).

Used for two things only: per-preamp-type median knob/level settings (where the tone engine starts
from) and neutral templates (routing, assigns, levels). Patch names are never matched to songs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from statistics import median

from .config import BTS_APPDATA, BTS_INSTALL
from .device.gt1.patch import Patch


@dataclass
class KBEntry:
    id: str
    name: str
    collection: str
    category: str
    patch: Patch = field(repr=False)


@cache
def load_kb() -> list[KBEntry]:
    entries: list[KBEntry] = []
    files = [("BOSS GT-1 Presets", BTS_INSTALL / "_assets" / "data" / "gt_preset_patches.tsl")]
    files += [(p.stem, p) for p in sorted((BTS_APPDATA / "livesets").glob("*.tsl"))]
    for coll, path in files:
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = coll if coll == "BOSS GT-1 Presets" else (doc.get("liveSetData") or {}).get("name") or coll
        for i, e in enumerate(doc.get("patchList", [])):
            entries.append(KBEntry(
                id=f"{path.stem}#{i + 1}", name=(e.get("name") or "").strip(), collection=name,
                category=" / ".join(x for x in (e.get("category2"), e.get("category")) if x),
                patch=Patch(e.get("params", {}))))
    return entries


@cache
def type_stats() -> dict[str, dict[str, float]]:
    """Median knob values (display units) and levels (raw) per preamp type across the KB."""
    acc: dict[str, list[KBEntry]] = {}
    for e in load_kb():
        if e.patch.get_raw("preamp_a_on_off"):
            acc.setdefault(e.patch.get("preamp_a_type"), []).append(e)
    out = {}
    for t, es in acc.items():
        s = {k: float(median(e.patch.get(f"preamp_a_{k}") for e in es))
             for k in ("gain", "bass", "middle", "treble", "presence")}
        s["level_raw"] = median(e.patch.get_raw("preamp_a_level") for e in es)
        s["patch_level_raw"] = median(e.patch.get_raw("patch_level") for e in es)
        s["n"] = len(es)
        out[t] = s
    return out


@cache
def _level_fit() -> tuple[list[float], dict[str, float], float]:
    """Fit preamp LEVEL on BOSS' factory presets, which BOSS level-matched (all at PATCH LEVEL 100).

    level ~ base + type offset + a*(gain-50) + b*max(0, 45-gain) + OD terms. Type offsets are ridge-shrunk
    to 0 (few presets per type). Residual ~5 level steps on the 81 presets with the preamp on.
    """
    import numpy as np

    kb = [e.patch for e in load_kb() if e.collection == "BOSS GT-1 Presets" and e.patch.get_raw("preamp_a_on_off")]
    types = sorted({p.get("preamp_a_type") for p in kb})
    X = np.array([_level_features(p.get("preamp_a_gain"), bool(p.get_raw("od_ds_on_off")),
                                  p.get("od_ds_effect_level"), p.get("od_ds_drive")) for p in kb], float)
    T = np.array([[p.get("preamp_a_type") == t for t in types] for p in kb], float)
    y = np.array([p.get("preamp_a_level") for p in kb], float)
    A = np.hstack([X, T, np.ones((len(kb), 1))])
    R = np.diag([0.0] * X.shape[1] + [2.0] * len(types) + [0.0])
    w = np.linalg.solve(A.T @ A + R, A.T @ y)
    nx = X.shape[1]
    return list(w[:nx]), dict(zip(types, w[nx:-1])), float(w[-1])


def _level_features(gain: float, od_on: bool, od_level: float, od_drive: float) -> list[float]:
    o = 1.0 if od_on else 0.0
    return [gain - 50, max(0.0, 45 - gain), o, (od_level - 50) * o, (od_drive - 50) * o]


def matched_preamp_level(preamp_type: str, gain: float, od_on: bool = False, od_level: float = 50,
                         od_drive: float = 50) -> int:
    """Preamp LEVEL that puts this amp/gain/boost at the same loudness as BOSS' presets (PATCH LEVEL 100)."""
    coef, offs, base = _level_fit()
    v = base + offs.get(preamp_type, 0.0) + sum(c * f for c, f in zip(coef, _level_features(gain, od_on, od_level, od_drive)))
    return int(round(max(20.0, min(80.0, v))))
