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


# ---------------------------------------------------------------------------------------- step 2: corrections
KNOBS = {"preamp_a_gain": 60, "preamp_a_bass": 50, "preamp_a_middle": 50, "preamp_a_treble": 50,
         "preamp_a_presence": 30, "master_eq_mid_gain": 0, "master_eq_high_gain": 0}
FLAT = {"drive": 0.0, "mid_scoop_db": 0.0, "presence_db": 0.0, "body_db": 0.0, "fizz_db": 0.0, "low_depth_db": 0.0}


def test_corrections_move_against_the_difference():
    moves, _ = cal.corrections({**FLAT, "drive": -0.2, "mid_scoop_db": -3.0, "presence_db": -2.0}, KNOBS)
    assert moves["preamp_a_gain"] > 60          # patch too clean -> more gain
    assert moves["preamp_a_middle"] > 50        # mids too scooped -> more middle
    assert moves["preamp_a_treble"] > 50 and moves["preamp_a_presence"] > 30
    assert cal.corrections(FLAT, KNOBS) == ({}, [])
    # inside the dead band nothing moves
    assert cal.corrections({**FLAT, "drive": 0.03, "presence_db": 1.0}, KNOBS)[0] == {}


def test_corrections_cut_slower_than_they_boost_and_stay_in_limits():
    up, _ = cal.corrections({**FLAT, "presence_db": -3.0}, KNOBS)
    down, _ = cal.corrections({**FLAT, "presence_db": 3.0}, KNOBS)
    assert up["preamp_a_treble"] - 50 > 50 - down["preamp_a_treble"] > 0
    big, _ = cal.corrections({**FLAT, "drive": -1.0}, KNOBS)
    assert big["preamp_a_gain"] == 60 + cal.MAX_STEP["preamp_a_gain"]
    top, notes = cal.corrections({**FLAT, "drive": -1.0}, {**KNOBS, "preamp_a_gain": 108})
    assert top["preamp_a_gain"] == 110 and any("GAIN sınırda" in n for n in notes)


def test_corrections_never_raise_bass():
    moves, notes = cal.corrections({**FLAT, "body_db": -5.0, "low_depth_db": -6.0}, KNOBS)
    assert "preamp_a_bass" not in moves and notes
    moves, _ = cal.corrections({**FLAT, "body_db": 5.0}, KNOBS)
    assert moves["preamp_a_bass"] < 50


def test_middle_at_its_limit_spills_into_master_eq_mid():
    moves, _ = cal.corrections({**FLAT, "mid_scoop_db": -8.0}, {**KNOBS, "preamp_a_middle": 84})
    assert moves["preamp_a_middle"] == 85 and moves["master_eq_mid_gain"] > 0
    moves, notes = cal.corrections({**FLAT, "mid_scoop_db": -8.0}, {**KNOBS, "preamp_a_middle": 84}, mid_freq="4.00kHz")
    assert "master_eq_mid_gain" not in moves and notes


def _dual():
    from tonematch.device.gt1.patch import Patch

    p = Patch()
    p.set("preamp_a_gain", 80)      # CTL off: 80, CTL on: 30 (assign 1)
    p.set("preamp_a_treble", 50)    # same on both sides: no assign
    spec = p.spec
    p.set_raw("assign1_on_off", 1)
    p.set_raw("assign1_target", spec.raw["assign_targets"]["PREAMP: GAIN"]["id"])
    p.set_raw("assign1_target_min", 80)
    p.set_raw("assign1_target_max", 30)
    p.set_raw("assign1_source", spec.raw["assign_sources"]["CTL1"])
    return p


def test_apply_moves_single_patch_sets_the_field():
    from tonematch.device.gt1.patch import Patch

    p = Patch()
    p.set("preamp_a_gain", 60)
    assert cal.apply_moves(p, {"preamp_a_gain": 70, "master_eq_high_gain": -2}, ctl_on=False) == []
    assert p.get("preamp_a_gain") == 70 and p.get("master_eq_high_gain") == -2


def test_apply_moves_dual_patch_keeps_the_other_side():
    p = _dual()
    assert cal.side_values(p, True)["preamp_a_gain"] == 30
    assert cal.side_values(p, False)["preamp_a_gain"] == 80
    on = p.copy()
    cal.apply_moves(on, {"preamp_a_gain": 40, "preamp_a_treble": 60}, ctl_on=True)
    assert cal.side_values(on, True)["preamp_a_gain"] == 40 and cal.side_values(on, False)["preamp_a_gain"] == 80
    # treble had no assign: a new one keeps CTL off at 50
    assert cal.side_values(on, True)["preamp_a_treble"] == 60 and on.get("preamp_a_treble") == 50
    assert on.get_raw("assign2_on_off") == 1 and on.get_raw("assign2_target_min") == 50
    off = p.copy()
    cal.apply_moves(off, {"preamp_a_gain": 90}, ctl_on=False)
    assert off.get("preamp_a_gain") == 90 and off.get_raw("assign1_target_min") == 90
    assert cal.side_values(off, True)["preamp_a_gain"] == 30


def test_apply_moves_reports_full_assigns():
    p = _dual()
    for i in range(2, 9):
        p.set_raw(f"assign{i}_on_off", 1)
        p.set_raw(f"assign{i}_source", p.spec.raw["assign_sources"]["CTL1"])
        p.set_raw(f"assign{i}_target", p.spec.raw["assign_targets"]["DELAY: ON/OFF"]["id"])
    q = p.copy()
    notes = cal.apply_moves(q, {"preamp_a_presence": 40}, ctl_on=True)
    assert notes and notes[0].startswith("PRESENCE") and q.params == p.params


def test_apply_and_undo_through_the_cli(tmp_path, monkeypatch):
    import contextlib
    import json

    from tonematch import cli
    from tonematch.device.gt1 import client
    from tonematch.device.gt1.patch import Patch

    buf = Patch()
    buf.name = "SONG RHY"
    buf.set("preamp_a_gain", 60)
    buf.set("preamp_a_middle", 50)

    class Fake:
        def read_patch(self):
            return buf.copy()

        def write_fields(self, p, fields):
            for f in fields:
                buf.params[f] = p.params[f]

    monkeypatch.setattr(client, "connect", lambda: contextlib.nullcontext(Fake()))
    rec = tmp_path / "rhythm.json"
    rec.write_text(json.dumps({"patch": {"name": "SONG RHY"}, "ctl_on": False, "moves": [
        {"field": "preamp_a_gain", "label": "GAIN", "from": 60, "to": 70},
        {"field": "preamp_a_middle", "label": "MIDDLE", "from": 45, "to": 55}]}))  # MIDDLE turned on the unit since
    a = cli._apply_calib(rec)
    assert [m["label"] for m in a["applied"]] == ["GAIN"] and a["skipped"]
    assert buf.get("preamp_a_gain") == 70 and buf.get("preamp_a_middle") == 50
    with pytest.raises(RuntimeError, match="zaten"):
        cli._apply_calib(rec)
    u = cli._apply_calib(rec, undo=True)
    assert u["applied"][0]["to"] == 60 and buf.get("preamp_a_gain") == 60
    assert len(json.loads(rec.read_text())["apply_log"]) == 2
    buf.name = "OTHER"
    rec.write_text(json.dumps({"patch": {"name": "SONG RHY"}, "ctl_on": False, "moves": []}))
    with pytest.raises(RuntimeError, match="başka patch"):
        cli._apply_calib(rec)


def test_write_fields_sends_14_bit_values_as_one_pair():
    from tonematch.device.gt1.client import GT1Client
    from tonematch.device.gt1.patch import Patch

    sent: list[tuple[list[int], list[int]]] = []
    mem: dict[tuple, list[int]] = {}

    class Fake(GT1Client):
        def write(self, addr, data):
            sent.append((addr, data))
            mem[tuple(addr)] = data

        def read(self, addr, size, allow_short=False):
            return mem[tuple(addr)][:size]

    p = Patch()
    p.set("preamp_a_gain", 70)
    p.set_raw("assign8_target_max", 1)
    c = Fake(spec=p.spec)
    c.write_fields(p, ["preamp_a_gain", "assign8_target_max_l"])
    off = p.spec.field_off["assign8_target_max_h"]
    assert ([*p.spec.temp_area(), off >> 7, off & 0x7F], [0, 1]) in sent  # starts at _h, both bytes
    assert len(sent) == 2
