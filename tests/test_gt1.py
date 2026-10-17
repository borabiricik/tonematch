import pytest

from tonematch.catalog import MOD_TYPES, OD_TYPES, PREAMP_TYPES
from tonematch.device.gt1.patch import Patch
from tonematch.device.gt1.spec import load_spec
from tonematch.device.gt1.sysex import addr_add, checksum, dt1, parse_dt1, rq1

SPEC = load_spec()


def test_patch_write_message_matches_bts():
    # BTS WRITE to U05 (from the decompiled SystemExclusive.as)
    msg = dt1(0x00, SPEC.model_id, SPEC.commands["patch_write"], [0x00, 0x04])
    assert msg.hex(" ").upper() == "F0 41 00 00 00 00 30 12 7F 00 01 04 00 04 78 F7"


def test_checksum_and_parse_roundtrip():
    m = dt1(0, SPEC.model_id, [0x60, 0, 0, 0x50], [1, 4, 0x50])
    addr, data = parse_dt1(m, SPEC.model_id)
    assert addr == [0x60, 0, 0, 0x50] and data == [1, 4, 0x50]
    assert checksum([0x60, 0, 0, 0x50, 1, 4, 0x50]) == m[-2]
    assert rq1(0, SPEC.model_id, [0x10, 4, 0, 0], 64)[-6:-2] == bytes([0, 0, 0, 0x40])


def test_addr_add_is_7bit():
    assert addr_add([0x60, 0, 0, 0x7F], 1) == [0x60, 0, 1, 0]


def test_blocks_cover_1423_bytes():
    assert len(SPEC.blocks) == 24
    assert sum(b.size for b in SPEC.blocks) == 1423


def test_block_roundtrip_preset():
    from tonematch.kb import load_kb

    p = load_kb()[0].patch
    q = Patch.from_block_bytes(p.block_bytes())
    for f, v in p.params.items():
        if f in SPEC.field_off:
            assert q.params[f] == v, f


def test_display_conversions():
    p = Patch()
    p.set("eq_low_gain", -3)
    assert p.get_raw("eq_low_gain") == 17 and p.get("eq_low_gain") == -3
    p.set("patch_level", 100)
    assert p.get_raw("patch_level") == 50
    p.set("preamp_a_type", "MS1959 I+II")
    assert p.get("preamp_a_type") == "MS1959 I+II"
    p.set_raw("delay_delay_time", 389)
    assert p.get_raw("delay_delay_time") == 389 and p.params["delay_delay_time_h"] == 3
    p.name = "NEM RHYTHM"
    assert p.name == "NEM RHYTHM"


def test_catalog_names_exist_in_spec():
    assert set(PREAMP_TYPES) <= set(SPEC.options("preamp_a_type"))
    assert set(OD_TYPES) <= set(SPEC.options("od_ds_type"))
    assert set(MOD_TYPES) <= set(SPEC.options("fx2_fx_type"))


def _profile(gain_class, flatness, gain=0.9, **desc):
    from tonematch.analysis import GroupProfile

    d = {"mid_scoop_db": 0.4, "presence_db": -3.7, "body_db": 7.0, "low_depth_db": -6.5, "fizz_db": -16.0}
    d.update(desc)
    return GroupProfile(name="x", seconds=30, segments=[(0, 30)], gain=gain, gain_class=gain_class,
                        flatness=flatness, width=0.3, periodicity=0.8, f0_median=300, crest_db=12, sustain=0.7,
                        bands_db={}, tilt_db_per_oct=-4, descriptors=d)


@pytest.mark.parametrize("role,gain_class,flat", [("clean", "clean", 0.02), ("rhythm", "crunch", 0.15),
                                                  ("rhythm", "high_gain", 0.35), ("lead", "high_gain", 0.3)])
def test_engine_builds_valid_patch(role, gain_class, flat):
    from tonematch.match import build_patch

    m = build_patch(role, _profile(gain_class, flat, gain=0.05 if gain_class == "clean" else 0.95), 120,
                    {"title": "Some Song (Remastered)"})
    p = m.patch
    assert all(0 <= v <= 127 for v in p.params.values())
    assert p.get_raw("preamp_a_on_off") == 1 and p.get_raw("master_bpm") == 120
    assert p.name.startswith("SOME SONG")
    assert p.get_raw("ctl_exp_accel_ctl_func") == 2  # CTL1 = PREAMP SOLO
    assert not any(p.get_raw(f"assign{i}_on_off") for i in range(1, 9))


def test_dual_patch_assigns():
    from tonematch.match import build_dual, build_patch

    spec = load_spec()
    meta = {"title": "Song"}
    main = build_patch("rhythm", _profile("crunch", 0.15), 120, meta)
    alt = build_patch("clean", _profile("clean", 0.02, gain=0.05), 120, meta)
    d = build_dual(main, alt, meta).patch
    on = [i for i in range(1, 9) if d.get_raw(f"assign{i}_on_off")]
    assert 1 <= len(on) <= 8 and d.get_raw("ctl_exp_accel_ctl_func") == 0
    t = {d.get_raw(f"assign{i}_target"): i for i in on}
    i = t[spec.raw["assign_targets"]["PREAMP: TYPE"]["id"]]
    assert d.get_raw(f"assign{i}_target_min") == main.patch.get_raw("preamp_a_type")
    assert d.get_raw(f"assign{i}_target_max") == alt.patch.get_raw("preamp_a_type")
    assert d.get_raw(f"assign{i}_source") == 1 and d.get_raw(f"assign{i}_source_mode") == 1
    assert all(0 <= v <= 127 for v in d.params.values())


def test_pitch_shift_only_when_needed():
    from tonematch.match import build_dual, build_patch
    from tonematch.tuning import TuningEstimate

    meta = {"title": "Song"}
    e_std = TuningEstimate("E standard", "EADGBE", 0, 12, 1.0, "E minor", "E2")
    eb = TuningEstimate("Eb standard", "EADGBE", -1, 20, 1.0, "Eb major", "Eb2")
    p0 = build_patch("rhythm", _profile("crunch", 0.15), 120, meta, tuning=e_std).patch
    assert p0.get("fx1_fx_type") != "PITCHSHIFTER" or not p0.get_raw("fx1_on_off")
    main = build_patch("rhythm", _profile("crunch", 0.15), 120, meta, tuning=eb)
    p1 = main.patch
    assert p1.get_raw("fx1_on_off") == 1 and p1.get("fx1_fx_type") == "PITCHSHIFTER"
    assert p1.get("fx1_pitch_shifter_ps1pitch") == -1 and p1.get("fx1_pitch_shifter_ps1fine") == 20
    assert p1.get("fx1_pitch_shifter_direct_mix") == 0 and p1.get("fx1_pitch_shifter_ps1level") == 100
    # dual: the clean side's compressor moves to FX2, pitch shifter stays on in both tones
    alt = build_patch("clean", _profile("clean", 0.02, gain=0.05), 120, meta, tuning=eb)
    assert alt.patch.get("fx2_fx_type") == "COMPRESSOR" and alt.patch.get_raw("fx1_on_off") == 1
    d = build_dual(main, alt, meta).patch
    spec = load_spec()
    targets = {d.get_raw(f"assign{i}_target") for i in range(1, 9) if d.get_raw(f"assign{i}_on_off")}
    assert spec.raw["assign_targets"]["FX1: ON/OFF"]["id"] not in targets
    assert spec.raw["assign_targets"]["FX2: ON/OFF"]["id"] in targets


def test_tuning_safety_fallback():
    from tonematch.tuning import FMIN_MIDI, score_tunings

    low = [0.0] * 48
    low[38 - FMIN_MIDI] = 0.4  # D2 dominant
    sal = [0.3] * 48
    f = {"low_share": low, "salience": sal, "tonic": 2, "mode": "major", "cents": -48}
    e = score_tunings(f)
    assert e.semitones == 0  # half-way-between-semitones recording never gets a shift


def test_engine_is_deterministic_and_follows_measurements():
    from tonematch.match import build_patch, choose_preamp

    a = build_patch("rhythm", _profile("high_gain", 0.36), 100, {"title": "x"}).patch.params
    b = build_patch("rhythm", _profile("high_gain", 0.36), 100, {"title": "x"}).patch.params
    assert a == b
    scooped, _ = choose_preamp(_profile("high_gain", 0.4, mid_scoop_db=-8), "rhythm")
    crunch, _ = choose_preamp(_profile("crunch", 0.15, mid_scoop_db=2.5), "rhythm")
    clean, _ = choose_preamp(_profile("clean", 0.02, gain=0.05), "clean")
    assert scooped in {"R-FIER MODERN", "CORE METAL", "BGNR UB METAL", "5150 DRIVE"}
    assert crunch in {"MS1959 I", "MS1959 I+II", "VO DRIVE", "TWEED", "COMBO CRUNCH", "MATCH DRIVE"}
    assert clean in {"NATURAL CLEAN", "CLEAN TWIN", "JC-120"}


def test_single_note_riff_reads_more_driven():
    from tonematch.match import drive_flatness, drive_index

    chords = _profile("crunch", 0.09)
    riff = _profile("crunch", 0.09)
    riff.periodicity = 0.85
    chords.periodicity = 0.5
    assert drive_flatness(chords) == 0.09
    assert drive_index(drive_flatness(riff)) > drive_index(drive_flatness(chords)) + 0.15
    clean = _profile("clean", 0.02, gain=0.05)
    clean.periodicity = 0.9
    assert drive_flatness(clean) == 0.02


@pytest.mark.parametrize("text,user,k", [("EADGBE", "EADGBE", 0), ("DADGBE", "DADGBE", 0),
                                         ("D#G#C#F#A#D#", "EADGBE", -1), ("Eb Ab Db Gb Bb Eb", "EADGBE", -1),
                                         ("DGCFAD", "EADGBE", -2), ("CGCFAD", "DADGBE", -2),
                                         ("BEADF#B", "EADGBE", -5), ("eadgbe", "EADGBE", 0)])
def test_user_tuning(text, user, k):
    from tonematch.tuning import parse_tuning

    e = parse_tuning(text)
    assert (e.user_tuning, e.semitones, e.cents) == (user, k, 0)


@pytest.mark.parametrize("text", ["DGDGBD", "EADG", "XYZ"])
def test_user_tuning_rejects_unreachable(text):
    from tonematch.tuning import parse_tuning

    with pytest.raises(ValueError):
        parse_tuning(text)


def test_levels_are_loudness_matched():
    from tonematch.match import build_dual, build_patch

    meta = {"title": "Song"}
    hot = build_patch("rhythm", _profile("high_gain", 0.36), 120, meta).patch
    soft = build_patch("rhythm", _profile("crunch", 0.09), 120, meta).patch
    clean = build_patch("clean", _profile("clean", 0.02, gain=0.05), 120, meta)
    assert hot.get("patch_level") == soft.get("patch_level") == 100
    assert clean.patch.get("preamp_a_level") > hot.get("preamp_a_level")  # BOSS: cleans need more level
    # dual patch: the level difference is switched by CTL too
    main = build_patch("rhythm", _profile("high_gain", 0.36), 120, meta)
    d = build_dual(main, clean, meta).patch
    spec = load_spec()
    lv = spec.raw["assign_targets"]["PREAMP: LEVEL"]["id"]
    i = next(i for i in range(1, 9) if d.get_raw(f"assign{i}_on_off") and d.get_raw(f"assign{i}_target") == lv)
    assert d.get_raw(f"assign{i}_target_max") == clean.patch.get_raw("preamp_a_level")


def test_claude_recipe_keeps_engine_guarantees():
    from tonematch.claude_mode import apply_recipe, schema
    from tonematch.kb import matched_preamp_level
    from tonematch.match import build_patch
    from tonematch.tuning import parse_tuning

    eb = parse_tuning("D#G#C#F#A#D#")
    g = _profile("crunch", 0.15)
    m = build_patch("rhythm", g, 120, {"title": "Song"}, tuning=eb)
    r = {"group": "rhythm", "confidence": "high", "why": "Marshall + TS",
         "preamp": {"type": "MS1959 I+II", "gain": 140, "bass": 50, "middle": 60, "treble": 55, "presence": 40, "sp_type": "4x12\""},
         "od": {"on": True, "type": "T-SCREAM", "drive": 20, "tone": 5, "level": 70},
         "delay": {"on": False, "type": "STANDARD", "time_ms": 300, "feedback": 20, "level": 20},
         "reverb": {"on": True, "type": "ROOM", "time_s": 1.0, "level": 15},
         "mod": {"on": True, "type": "CHORUS", "rate": 30, "depth": 40, "level": 50},
         "master_eq": {"low_db": 9, "mid_db": 1, "mid_freq": "800Hz", "high_db": 0}}
    p = apply_recipe(m, r, g).patch
    assert p.get("preamp_a_type") == "MS1959 I+II" and p.get("preamp_a_gain") == 100  # clamped
    assert p.get("fx1_fx_type") == "PITCHSHIFTER" and p.get_raw("fx1_on_off") == 1      # tuning kept
    assert p.get("master_eq_low_gain") == 2                                               # no big low boost
    assert p.get("preamp_a_level") == matched_preamp_level("MS1959 I+II", 100, True, 70, 20)
    assert p.get("fx2_fx_type") == "CHORUS" and p.get("patch_level") == 100
    s = schema(["rhythm", "clean"])
    assert s["properties"]["patches"]["items"]["properties"]["group"]["enum"] == ["rhythm", "clean"]


def test_claude_failure_falls_back_to_engine(monkeypatch):
    from tonematch import claude_mode
    from tonematch.match import build_patch

    m = build_patch("rhythm", _profile("crunch", 0.15), 120, {"title": "Song"})

    def boom(*a, **k):
        raise claude_mode.ClaudeError("no backend")

    monkeypatch.setattr(claude_mode, "ask", boom)

    class Ana:
        tempo = 120
        groups = {"rhythm": _profile("crunch", 0.15)}

    out, info = claude_mode.refine({"title": "Song"}, Ana(), {"rhythm": m}, None, progress=lambda s: None)
    assert out["rhythm"] is m and info["ok"] is False and "no backend" in info["error"]
