"""End-to-end: source -> stems -> analysis -> recipe -> GT-1 patches (-> device slots)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .analysis import TrackAnalysis, analyze
from .config import PROJECT_ROOT
from .device.gt1.patch import Patch, write_tsl
from .ingest import ingest, track_dir
from .match import MatchResult, match_groups
from .separate import separate

log = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "output"
GROUP_ORDER = ["rhythm", "lead", "clean", "crunch"]
ANALYSIS_VERSION = 5  # bump when analysis.py changes so cached results are recomputed


@dataclass
class RunResult:
    track_id: str
    meta: dict
    analysis: TrackAnalysis
    matches: list[MatchResult]
    info: dict
    tsl_path: Path
    written: dict[str, str] = field(default_factory=dict)


def _load_or_analyze(d: Path, stems: dict, wav: Path) -> TrackAnalysis:
    from .analysis import GroupProfile, DelayEstimate, ReverbEstimate

    cache = d / "analysis.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        if raw.get("version") == ANALYSIS_VERSION:
            groups = {}
            for k, g in raw["groups"].items():
                g = dict(g)
                g["delay"] = DelayEstimate(**g["delay"])
                g["reverb"] = ReverbEstimate(**g["reverb"])
                g["segments"] = [tuple(s) for s in g["segments"]]
                groups[k] = GroupProfile(**g)
            return TrackAnalysis(raw["tempo"], raw["duration"], raw["guitar_presence"], groups, raw["windows"])
    ana = analyze(stems["guitar"], wav)
    out = ana.to_dict()
    out["version"] = ANALYSIS_VERSION
    cache.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    return ana


TUNING_VERSION = 1  # bump when tuning.py changes


def load_or_detect_tuning(d: Path, stems: dict, wav: Path):
    """Automatic detection, dev tools only (the app takes the tuning from the user)."""
    from .tuning import TuningEstimate, detect_tuning

    cache = d / "tuning.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        if raw.pop("version", None) == TUNING_VERSION:
            return TuningEstimate(**raw)
    est = detect_tuning(stems["guitar"], wav, stems.get("bass"))
    cache.write_text(json.dumps({**est.to_dict(), "version": TUNING_VERSION}, indent=1), encoding="utf-8")
    return est


def prepare(source: str) -> tuple[str, dict, TrackAnalysis]:
    tid, wav, meta = ingest(source)
    d = track_dir(tid)
    stems = separate(wav, d)
    return tid, meta, _load_or_analyze(d, stems, wav)


def run(source: str, slot: int | None, groups: list[str] | None = None,
        device: bool = True, progress=print, dual: bool = True, tuning=None, claude: bool = False) -> RunResult:
    """`tuning`: the song's tuning as given by the user (`tuning.parse_tuning`); None = E standard."""
    progress("1/4 indiriliyor / hazırlanıyor ...")
    tid, wav, meta = ingest(source)
    d = track_dir(tid)
    progress(f"    {meta.get('artist', '')} - {meta.get('title', '')}")
    progress("2/4 gitar ayrıştırılıyor (ilk seferde ~1-2 dk) ...")
    stems = separate(wav, d)
    progress("3/4 ton analizi ...")
    ana = _load_or_analyze(d, stems, wav)
    if tuning is None:
        from .tuning import E_STANDARD

        tuning = E_STANDARD  # no automatic detection (user decision): unnamed = E standard, no shifter
    found = [g for g in GROUP_ORDER if g in ana.groups]
    if not found:
        raise RuntimeError("no guitar parts found in this recording")
    chosen = [g for g in (groups or found) if g in ana.groups]
    if not chosen:
        raise RuntimeError(f"requested groups {groups} not found; available: {found}")

    output_select = None
    client = None
    if device:
        from .device.gt1.client import GT1Client

        client = GT1Client().open()
        if client.read_system("PREFERENCE: PREAMP"):
            log.warning("GT-1 PREFERENCE: PREAMP = SYSTEM -> the device ignores patch preamp settings!")
        output_select = client.read_patch().get_raw("output_select")

    try:
        progress("4/4 GT-1 eşleştirmesi ...")
        info: dict = {"tuning": tuning.to_dict() if tuning else None}
        matches = match_groups(meta, ana, chosen, output_select, dual=dual, tuning=tuning, claude=claude,
                               progress=progress, info=info)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{meta.get('artist', '')}_{meta.get('title', '')}").strip("_")[:60]
        tsl = OUTPUT_DIR / f"{safe or tid}.tsl"
        for m in matches:
            m.patch.meta["note"] = f"tonematch: {meta.get('title', '')} [{m.group}] - {m.recipe.get('why', '')}"[:300]
        write_tsl(tsl, [m.patch for m in matches], liveset_name=f"tonematch {meta.get('title', '')}"[:40])
        report = {"meta": meta, "info": {k: v for k, v in info.items()}, "tempo": ana.tempo,
                  "patches": {m.group: {"recipe": m.recipe, "base": m.base, "preamp_scores": m.scores,
                                        "patch": m.patch.summary()} for m in matches},
                  "groups": {g: ana.groups[g].to_dict() for g in chosen}}
        (d / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=float),
                                       encoding="utf-8")
        res = RunResult(tid, meta, ana, matches, info, tsl)
        if client is not None and slot is not None:
            from .device.gt1.backup import backup_slots
            from .device.gt1.client import slot_label

            slots = [slot + i for i in range(len(matches))]
            if slots[-1] > 98:
                raise RuntimeError("not enough user slots after the start slot (max U99)")
            bk = backup_slots(client, slots, f"before_{slot_label(slots[0])}-{slot_label(slots[-1])}")
            from .device.gt1 import slots as slot_cache

            for s, m in zip(slots, matches):
                client.store_patch(m.patch, s)
                res.written[m.group] = slot_label(s)
                slot_cache.remember_write(slot_label(s), m.patch)
            client.select_patch(slots[0])  # ready to play
            res.info["backup"] = str(bk)
        elif client is not None:
            client.write_temp(matches[0].patch)  # audition the first one without saving
            res.written[matches[0].group] = "edit buffer (not saved)"
        return res
    finally:
        if client is not None:
            client.close()


def patches_of(res: RunResult) -> list[Patch]:
    return [m.patch for m in res.matches]
