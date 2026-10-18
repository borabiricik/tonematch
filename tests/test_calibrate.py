import numpy as np
import pytest

from tonematch import calibrate as cal
from tonematch.config import SR


def _strum(seconds: float, drive: float, bright: float = 1.0, seed: int = 0) -> np.ndarray:
    """E5 power chords, one per 0.5 s, through tanh 'distortion' (drive 0 = clean). Stereo, quiet like a USB take."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    x = np.zeros_like(t)
    for f in (82.4, 123.5, 164.8):
        for h in range(1, 12):
            x += np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6)) * bright ** h / h
    x *= np.exp(-3 * (t % 0.5))
    if drive > 0:
        x = np.tanh(drive * x / np.max(np.abs(x)))
    x = 0.1 * x / np.max(np.abs(x)) + 1e-4 * rng.standard_normal(len(t))
    return np.vstack([x, x]).astype(np.float32)


def test_measure_and_compare_see_drive_and_brightness():
    clean = cal.measure(_strum(14, 0.0), "rhythm", 120)
    driven = cal.measure(_strum(14, 30.0), "rhythm", 120)
    assert clean.seconds >= cal.MIN_PLAYED_S and not clean.clipped
    c = cal.compare(target=driven.profile, played=clean.profile)
    assert c["diff"]["drive"] < -cal.DEAD_BAND["drive"]
    hint = {h["axis"]: h for h in c["hints"]}
    assert hint["drive"]["direction"] == "up"  # patch too clean -> GAIN up
    same = cal.compare(driven.profile, driven.profile)
    assert same["hints"] == [] and same["spectral_distance_db"] == 0.0
    assert set(same["close"]) == set(cal.DEAD_BAND)


def test_measure_normalizes_level():
    a = cal.measure(_strum(12, 10.0), "rhythm", 120)
    b = cal.measure(_strum(12, 10.0) * 0.1, "rhythm", 120)  # same tone, 20 dB quieter
    d = cal.compare(a.profile, b.profile)
    assert abs(d["diff"]["drive"]) < 0.02 and d["spectral_distance_db"] < 0.5
    assert b.level_db < a.level_db - 15


def test_measure_rejects_silence_and_short_takes():
    with pytest.raises(RuntimeError, match="ses yok"):
        cal.measure(np.zeros((2, SR * 10), np.float32), "rhythm", 120)
    take = _strum(12, 10.0)
    take[:, int(3 * SR):] = 0
    with pytest.raises(RuntimeError, match="en az"):
        cal.measure(take, "rhythm", 120)


def test_hints_respect_dead_band_and_order():
    h = cal.hints({"drive": 0.03, "mid_scoop_db": -4.0, "presence_db": 2.0, "body_db": 0.5, "fizz_db": 0.0,
                   "low_depth_db": 0.0})
    assert [x["axis"] for x in h] == ["mid_scoop_db", "presence_db"]
    assert h[0]["direction"] == "up" and h[1]["direction"] == "down"


def test_save_lists_changed_knobs_in_display_units():
    from tonematch.cli import _changed_knobs
    from tonematch.device.gt1.patch import Patch

    old = Patch()
    old.set("preamp_a_gain", 60)
    old.set("preamp_a_middle", 50)
    new = old.copy()
    new.set("preamp_a_gain", 72)
    new.set("master_eq_high_gain", -3)
    assert _changed_knobs(old, old) == []
    ch = {c["label"]: (c["from"], c["to"]) for c in _changed_knobs(old, new)}
    assert ch["GAIN"] == ("60", "72") and "MIDDLE" not in ch
    assert ch["M.EQ HIGH"][1] == "-3"
