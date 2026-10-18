"""Play-to-calibrate (docs/07 item 0), step 1: measure only.

The player plays the song's riff through the patch; the GT-1's USB record tap sits at the end of the effect chain
(docs/06-extracted §6), so `IN (GT-1)` carries exactly what the patch sounds like. The recording goes through the
same profile code as the song's guitar stem (`analysis.build_profile`) and the two are compared on the engine's
axes (drive, mid / presence / body / fizz / low end, 1/3-octave curve, delay, reverb).

Nothing is written to the device here: the knob corrections are only suggested (step 2 applies them).
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
