"""Machine-readable results for the desktop app (`--json`): one `@@RESULT {...}` / `@@ERROR {...}` line."""

from __future__ import annotations

import json
import sys

from .device.gt1.patch import Patch

RESULT, ERROR = "@@RESULT ", "@@ERROR "


def emit(prefix: str, payload) -> None:
    sys.stdout.write(prefix + json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def tone_view(p: Patch) -> dict:
    """What a guitarist looks at: amp model + knobs, boost, effects (display values)."""
    s = p.summary()
    fx = []
    if s["fx1_on_off"]:
        fx.append({"slot": "FX1", "name": str(s["fx1_fx_type"]),
                   "detail": f"{p.get('fx1_pitch_shifter_ps1pitch'):+d}" if s["fx1_fx_type"] == "PITCHSHIFTER" else ""})
    if s["fx2_on_off"]:
        fx.append({"slot": "FX2", "name": str(s["fx2_fx_type"]), "detail": ""})
    if s["delay_on_off"]:
        fx.append({"slot": "DELAY", "name": str(s["delay_type"]), "detail": f"{s['delay_delay_time']} ms"})
    if s["reverb_on_off"]:
        fx.append({"slot": "REVERB", "name": str(s["reverb_type"]), "detail": str(s["reverb_time"])})
    return {
        "amp": str(s["preamp_a_type"]),
        "knobs": {k: s[f"preamp_a_{k}"] for k in ("gain", "bass", "middle", "treble", "presence", "level")},
        "od": ({"type": str(s["od_ds_type"]), "drive": s["od_ds_drive"], "level": s["od_ds_effect_level"]}
               if s["od_ds_on_off"] else None),
        "fx": fx,
    }


def ctl_on_patch(p: Patch) -> Patch:
    """The dual patch as it sounds with CTL on: every CTL1 assign moved to its max value."""
    from .match import DUAL_TARGETS  # lazy: keeps the device commands free of the audio stack

    q = p.copy()
    targets = p.spec.raw["assign_targets"]
    by_id = {targets[name]["id"]: field for name, field in DUAL_TARGETS if name in targets}
    for i in range(1, 9):
        f = by_id.get(p.get_raw(f"assign{i}_target"))
        if p.get_raw(f"assign{i}_on_off") and f:
            q.set_raw(f, p.get_raw(f"assign{i}_target_max"))
    return q


def run_payload(res) -> dict:
    out = []
    for m in res.matches:
        dual = bool(m.recipe.get("dual"))
        groups = [m.recipe["ctl_off"], m.recipe["ctl_on"]] if dual else [m.group]
        tones = [tone_view(m.patch)] + ([tone_view(ctl_on_patch(m.patch))] if dual else [])
        for t, g in zip(tones, groups):
            prof = res.analysis.groups[g]
            t.update(role=g, segments=[[round(a, 1), round(b, 1)] for a, b in prof.segments[:8]],
                     drive=prof.gain_class, stereo=prof.stereo)
        recs = [m.recipe["main"], m.recipe["alt"]] if dual else [m.recipe]
        for t, rec in zip(tones, recs):
            t["claude"] = rec.get("claude")
        out.append({"group": m.group, "name": m.patch.name, "slot": res.written.get(m.group), "dual": dual,
                    "assigns": m.recipe.get("assigns", []), "tones": tones})
    meta = res.meta
    return {"track_id": res.track_id, "title": meta.get("title", ""), "artist": meta.get("artist", ""),
            "duration": res.analysis.duration, "tempo": res.analysis.tempo, "tuning": res.info.get("tuning"),
            "patches": out, "tsl": str(res.tsl_path), "backup": res.info.get("backup"),
            "claude": res.info.get("claude")}
