"""Play-to-calibrate (docs/07 item 0): measure (step 1), then correct the edit buffer (step 2).

The player plays the song's riff through the patch; the GT-1's USB record tap sits at the end of the effect chain
(docs/06-extracted §6), so `IN (GT-1)` carries exactly what the patch sounds like. The recording goes through the
same profile code as the song's guitar stem (`analysis.build_profile`) and the two are compared on the engine's
axes (drive, mid / presence / body / fizz / low end, 1/3-octave curve, delay, reverb).

`corrections` turns the difference into knob moves (the engine's own slopes, inverted and damped); `apply_moves` puts
them on the right side of a dual (CTL) patch. The CLI writes them to the edit buffer only on request (`--apply`,
`gt1 apply`); saving to a slot stays a separate, confirmed step (`gt1 save`).
Confounds the numbers cannot remove: the player's guitar / pickups / touch, and the stem being separated + mastered.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .analysis import GroupProfile, Window, build_profile, make_windows, window_features
from .config import SR
from .match import drive_flatness, drive_index

TARGET_RMS_DB = -18.0      # recording is normalized so its loud windows sit like a stem's
MIN_PLAYED_S = 6.0         # less than this after trimming silence -> not enough to measure
SILENCE_DB = -55.0         # window rms (before normalization) below this = nothing played
CLIP = 0.999

# |difference| below these = "close enough" (about the run-to-run spread of the stem measurements)
DEAD_BAND = {"drive": 0.06, "mid_scoop_db": 1.5, "presence_db": 1.5, "body_db": 2.0, "fizz_db": 2.0,
             "low_depth_db": 3.0}
AXES = ("mid_scoop_db", "presence_db", "body_db", "fizz_db", "low_depth_db")


# ------------------------------------------------------------------------------------------ device
def find_input(hint: str = "GT-1") -> tuple[int, str]:
    """(device index, label) of the GT-1's USB recording input. WASAPI first (no resampling at 44.1 kHz), then MME."""
    import sounddevice as sd

    found = [(i, d) for i, d in enumerate(sd.query_devices()) if hint in d["name"] and d["max_input_channels"] > 0]
    if not found:
        raise RuntimeError(f"'{hint}' kayıt girişi bulunamadı (GT-1 USB ile bağlı mı?)")
    apis = [a["name"] for a in sd.query_hostapis()]
    order = ["Windows WASAPI", "MME", "Core Audio", "Windows DirectSound"]
    rank = lambda it: order.index(apis[it[1]["hostapi"]]) if apis[it[1]["hostapi"]] in order else len(order)
    i, d = min(found, key=rank)
    return i, f"{d['name']} ({apis[d['hostapi']]})"


def record(seconds: float, device: int, on_level=None) -> np.ndarray:
    """Record `seconds` of stereo float audio at SR. on_level(dbfs) is called ~10x per second (live meter)."""
    import sounddevice as sd

    chunks: list[np.ndarray] = []
    info = sd.query_devices(device)
    ch = min(2, info["max_input_channels"])

    def cb(indata, frames, t, status):
        chunks.append(indata.copy())

    with sd.InputStream(device=device, channels=ch, samplerate=SR, dtype="float32", callback=cb, blocksize=SR // 10):
        end = time.monotonic() + seconds
        seen = 0
        while time.monotonic() < end:
            time.sleep(0.05)
            if on_level is not None and len(chunks) > seen:
                seen = len(chunks)
                x = chunks[-1]
                on_level(round(float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)), 1))
    y = np.concatenate(chunks, axis=0).T if chunks else np.zeros((ch, 0), np.float32)
    return np.vstack([y[0], y[0]]) if y.shape[0] == 1 else y[:2]


# ------------------------------------------------------------------------------------------ measure
@dataclass
class Played:
    profile: GroupProfile
    seconds: float          # played (non-silent) time
    peak: float             # before normalization
    clipped: bool
    level_db: float         # loud-window rms before normalization (dBFS)


def measure(y: np.ndarray, role: str, tempo: float, center: bool = False) -> Played:
    """Profile a recording the same way a song's group is profiled. Raises if nothing usable was played."""
    if y.shape[1] < SR * 2:
        raise RuntimeError("kayıt çok kısa")
    peak = float(np.max(np.abs(y)))
    wins = make_windows(y.shape[1] / SR, np.array([]), tempo)
    window_features(y, wins)
    loud = [w for w in wins if w.rms_db > SILENCE_DB]
    if not loud:
        raise RuntimeError("kayıtta ses yok: GT-1'den sinyal gelmiyor (gitar takılı mı, USB kayıt seviyesi?)")
    top = float(np.percentile([w.rms_db for w in loud], 90))
    played = [w for w in loud if w.rms_db > top - 18]
    secs = sum(w.end - w.start for w in played)
    if secs < MIN_PLAYED_S:
        raise RuntimeError(f"sadece {secs:.0f} sn çalım algılandı; en az {MIN_PLAYED_S:.0f} sn çal")
    gain = 10 ** ((TARGET_RMS_DB - top) / 20)
    y = y * gain
    for w in wins:
        w.rms_db += 20 * np.log10(gain)
    prof = build_profile(role, _only(played, wins), y, tempo, center=center)
    return Played(prof, round(secs, 1), round(peak, 3), peak >= CLIP, round(top, 1))


def _only(sel: list[Window], wins: list[Window]) -> list[Window]:
    keep = {id(w) for w in sel}
    return [w for w in wins if id(w) in keep]


# ------------------------------------------------------------------------------------------ compare
def _drive(g: GroupProfile) -> float:
    return drive_index(drive_flatness(g))


def compare(target: GroupProfile, played: GroupProfile) -> dict:
    """played - target on the engine's axes, a 1/3-octave distance, and plain-language directions."""
    d = {"drive": round(_drive(played) - _drive(target), 3)}
    for k in AXES:
        d[k] = round(played.descriptors.get(k, 0.0) - target.descriptors.get(k, 0.0), 1)
    bands = [b for b in target.third_oct_db if b in played.third_oct_db]
    curve = {b: round(played.third_oct_db[b] - target.third_oct_db[b], 1) for b in bands}
    # 63-125 Hz left out of the distance: the stem's low end carries bass bleed
    core = [v for b, v in curve.items() if b not in ("63Hz", "80Hz", "100Hz", "125Hz")]
    dist = round(float(np.sqrt(np.mean(np.square(core)))), 2) if core else 0.0
    return {"diff": d, "third_oct_diff": curve, "spectral_distance_db": dist, "hints": hints(d),
            "close": [k for k, v in d.items() if abs(v) < DEAD_BAND[k]]}


_WORDS = {
    "drive": ("daha az distorsiyonlu", "daha çok distorsiyonlu", "GAIN"),
    "mid_scoop_db": ("ortalar daha oyuk", "ortalar daha önde", "MIDDLE"),
    "presence_db": ("daha az ısırık/parlaklık (2-4.5 kHz)", "daha çok ısırık/parlaklık (2-4.5 kHz)", "TREBLE / PRESENCE"),
    "body_db": ("alt-orta gövde daha ince", "alt-orta gövde daha kalın", "BASS / MASTER EQ low-mid"),
    "fizz_db": ("üst tizler (5-8 kHz) daha karanlık", "üst tizler (5-8 kHz) daha cızırtılı", "MASTER EQ high"),
    "low_depth_db": ("alt uç daha sıkı", "alt uç daha derin/gevşek", "BASS"),
}


def hints(d: dict) -> list[dict]:
    """One line per axis outside the dead band, biggest first: what the patch does vs the song."""
    out = []
    for k, (less, more, knob) in _WORDS.items():
        v = d.get(k, 0.0)
        if abs(v) < DEAD_BAND[k]:
            continue
        out.append({"axis": k, "value": v, "knob": knob, "direction": "down" if v > 0 else "up",
                    "text": f"patch şarkıya göre {more if v > 0 else less} → {knob} {'↓' if v > 0 else '↑'}",
                    "weight": abs(v) / DEAD_BAND[k]})
    return sorted(out, key=lambda h: -h["weight"])


# ------------------------------------------------------------------------------------------ correct (step 2)
# The engine's own deviation -> knob slopes (match.build_patch), inverted: 1 dB of mid = 3 MIDDLE steps, 1 dB of
# presence = 2 TREBLE + 1.5 PRESENCE, one unit of drive = 120 GAIN. Damped so 2-3 rounds converge rather than one
# jump overshoots (the player's guitar and touch are in the loop, nothing else is).
DAMPING = 0.6
# Stems read darker and less saturated than the real amp (separation + codec, docs/05 drive_index note), so a patch
# that matches by ear still measures brighter / more driven than the stem. Cutting follows at this fraction only;
# the engine has the same asymmetry. Bass is never raised (the stem's lows carry bass-guitar bleed, docs/05 §2).
CUT_RATE = 0.5
MAX_STEP = {"preamp_a_gain": 15, "preamp_a_middle": 12, "preamp_a_treble": 10, "preamp_a_presence": 10,
            "preamp_a_bass": 8, "master_eq_mid_gain": 3, "master_eq_high_gain": 3}
LIMITS = {"preamp_a_gain": (5, 110), "preamp_a_bass": (25, 75), "preamp_a_middle": (15, 85),
          "preamp_a_treble": (25, 80), "preamp_a_presence": (0, 60),
          "master_eq_mid_gain": (-6, 6), "master_eq_high_gain": (-6, 6)}
LABELS = {"preamp_a_gain": "GAIN", "preamp_a_bass": "BASS", "preamp_a_middle": "MIDDLE", "preamp_a_treble": "TREBLE",
          "preamp_a_presence": "PRESENCE", "master_eq_mid_gain": "M.EQ MID", "master_eq_high_gain": "M.EQ HIGH"}
# assign target (gt1_spec.json) of each field, for the CTL side of a dual patch
ASSIGN_TARGET = {"preamp_a_gain": "PREAMP: GAIN", "preamp_a_bass": "PREAMP: BASS", "preamp_a_middle": "PREAMP: MIDDLE",
                 "preamp_a_treble": "PREAMP: TREBLE", "preamp_a_presence": "PREAMP: PRESENCE",
                 "master_eq_mid_gain": "MASTER: MID GAIN", "master_eq_high_gain": "MASTER: HIGH GAIN"}
MID_EQ_BANDS = {"400Hz", "500Hz", "630Hz", "800Hz", "1.00kHz", "1.25kHz"}  # where M.EQ MID can stand in for MIDDLE


def corrections(diff: dict, knobs: dict, mid_freq: str = "630Hz") -> tuple[dict[str, int], list[str]]:
    """Knob moves (field -> new display value) that pull the patch toward the song, plus notes on what was left.

    diff: compare()["diff"] (played - song); knobs: the side's current display values of the LABELS fields."""
    want: dict[str, float] = {}
    notes: list[str] = []

    def rate(axis: str, v: float) -> float:  # v > 0: the patch has more of it than the song -> a cut
        return 0.0 if abs(v) < DEAD_BAND[axis] else DAMPING * (CUT_RATE if v > 0 else 1.0)

    def add(field: str, delta: float) -> None:
        want[field] = want.get(field, 0.0) + delta

    v = diff.get("drive", 0.0)
    add("preamp_a_gain", -v * 120 * rate("drive", v))
    v = diff.get("mid_scoop_db", 0.0)
    add("preamp_a_middle", -v * 3 * rate("mid_scoop_db", v))
    v = diff.get("presence_db", 0.0)
    add("preamp_a_treble", -v * 2 * rate("presence_db", v))
    add("preamp_a_presence", -v * 1.5 * rate("presence_db", v))
    for axis, slope in (("body_db", 1.5), ("low_depth_db", 1.0)):
        v = diff.get(axis, 0.0)
        if v > 0:
            add("preamp_a_bass", -v * slope * rate(axis, v))
        elif abs(v) >= DEAD_BAND[axis]:
            notes.append("alt uç şarkıdan ince ölçüldü; BASS otomatik artırılmaz (stemde bas gitar sızıntısı var), "
                         "kulağına da inceyse cihazdan aç")
    v = diff.get("fizz_db", 0.0)
    add("master_eq_high_gain", -v / 2 * rate("fizz_db", v))

    moves: dict[str, int] = {}
    for field, delta in want.items():
        cur = knobs[field]
        lo, hi = LIMITS[field]
        step = max(-MAX_STEP[field], min(MAX_STEP[field], delta))
        new = int(round(max(lo, min(hi, cur + step))))
        if new != cur:
            moves[field] = new
        # MIDDLE at its limit: the rest goes to the master EQ's parametric mid (3 MIDDLE steps ~ 1 dB)
        left = step - (new - cur)
        if field == "preamp_a_middle" and abs(left) >= 3:
            if mid_freq in MID_EQ_BANDS:
                m = knobs["master_eq_mid_gain"]
                lo2, hi2 = LIMITS["master_eq_mid_gain"]
                m2 = int(round(max(lo2, min(hi2, m + max(-3, min(3, left / 3))))))
                if m2 != m:
                    moves["master_eq_mid_gain"] = m2
            else:
                notes.append(f"MIDDLE sınırda; M.EQ MID {mid_freq}'de olduğu için ortaya dokunulmadı")
        elif abs(left) >= 3 and new in (lo, hi):
            notes.append(f"{LABELS[field]} sınırda ({new}); kalan farkı amfi modeli ya da OD/DS kapatabilir")
    return moves, notes


def _ctl_assigns(p) -> dict[int, int]:
    """target id -> assign index of the CTL1 assigns that are on (a dual patch's second tone)."""
    src = p.spec.raw["assign_sources"]["CTL1"]
    return {p.get_raw(f"assign{i}_target"): i for i in range(1, 9)
            if p.get_raw(f"assign{i}_on_off") and p.get_raw(f"assign{i}_source") == src}


def side_values(p, ctl_on: bool) -> dict:
    """Display values of the correctable fields as they sound on one side of the patch."""
    ids = p.spec.raw["assign_targets"]
    assigns = _ctl_assigns(p) if ctl_on else {}
    out = {}
    for f in LABELS:
        i = assigns.get(ids[ASSIGN_TARGET[f]]["id"])
        out[f] = p.spec.raw_to_display(f, p.get_raw(f"assign{i}_target_max")) if i else p.get(f)
    return out


def apply_moves(p, moves: dict[str, int], ctl_on: bool) -> list[str]:
    """Write moves (display values) into patch p for one side; returns notes on moves that could not be made.

    A plain patch gets the field. A dual patch (CTL1 assigns) keeps the other side as it is: CTL off = the field
    and its assign's min, CTL on = the assign's max; a field without an assign gets one (if one of 8 is free)."""
    spec = p.spec
    ids = spec.raw["assign_targets"]
    assigns = _ctl_assigns(p)
    notes = []
    for f, value in moves.items():
        raw = spec.display_to_raw(f, value)
        if not assigns:  # single-tone patch
            p.set_raw(f, raw)
            continue
        tid = ids[ASSIGN_TARGET[f]]["id"]
        i = assigns.get(tid)
        if i is None:
            free = [k for k in range(1, 9) if not p.get_raw(f"assign{k}_on_off")]
            if not free:
                notes.append(f"{LABELS[f]}: 8 assign dolu, {'CTL açık' if ctl_on else 'CTL kapalı'} tarafa ayrı değer verilemedi")
                continue
            i = free[0]
            cur = p.get_raw(f)
            p.set_raw(f"assign{i}_on_off", 1)
            p.set_raw(f"assign{i}_target", tid)
            p.set_raw(f"assign{i}_target_min", cur)
            p.set_raw(f"assign{i}_target_max", cur)
            p.set_raw(f"assign{i}_source", spec.raw["assign_sources"]["CTL1"])
            p.set_raw(f"assign{i}_source_mode", spec.raw["assign_source_modes"]["TOGGLE"])
            p.set_raw(f"assign{i}_act_range_lo", 0)
            p.set_raw(f"assign{i}_act_range_hi", 127)
            assigns[tid] = i
        if ctl_on:
            p.set_raw(f"assign{i}_target_max", raw)
        else:
            p.set_raw(f, raw)
            p.set_raw(f"assign{i}_target_min", raw)
    return notes
