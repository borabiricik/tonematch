"""Deterministic tone engine: measured GroupProfile -> GT-1 patch. No external services.

1. Pick the preamp model whose sonic signature (drive, mid shape, presence, body) is closest to
   what was measured (`PREAMP_SIGNATURES`).
2. Start the knobs from that model's median setting in 411 professional GT-1 patches, then move
   them by the measured deviations from the reference stems (`REF`).
3. Add boost / gate / compressor / delay / reverb from measurements and simple, safe rules.

Reference values come from 7 calibration songs through this same pipeline (docs/04-tone-analysis.md).
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

from .analysis import GroupProfile, TrackAnalysis
from .device.gt1.patch import Patch
from .kb import load_kb, matched_preamp_level, type_stats
from .tuning import TuningEstimate

log = logging.getLogger(__name__)

# Medians of the descriptors over the calibration stems (driven / clean groups).
REF = {
    "driven": {"mid_scoop_db": 0.4, "presence_db": -3.7, "body_db": 7.0, "low_depth_db": -6.5, "fizz_db": -16.0},
    "clean": {"mid_scoop_db": 0.0, "presence_db": -6.0, "body_db": 9.0, "low_depth_db": -9.5, "fizz_db": -19.0},
}

# drive D (0..1, from spectral flatness), mid M / presence P / body B as deviation from REF (dB).
# Hand-made from how the GT-1 COSM models voice (gain range, mid curve, top end, low-mid weight).
PREAMP_SIGNATURES = {
    # crunch family
    "COMBO CRUNCH":   dict(D=0.40, M=0.0, P=0.0, B=0.0),
    "DELUXE CRUNCH":  dict(D=0.38, M=0.0, P=-1.0, B=1.0),
    "TWEED":          dict(D=0.40, M=1.0, P=-3.0, B=3.0),
    "PRO CRUNCH":     dict(D=0.35, M=0.5, P=1.0, B=0.0),
    "VO DRIVE":       dict(D=0.47, M=1.5, P=3.0, B=-1.0),
    "MATCH DRIVE":    dict(D=0.47, M=1.0, P=2.0, B=0.0),
    "MS1959 I":       dict(D=0.50, M=2.0, P=1.0, B=-1.0),
    "MS1959 I+II":    dict(D=0.58, M=2.0, P=0.0, B=1.0),
    "STACK CRUNCH":   dict(D=0.58, M=0.0, P=0.0, B=0.0),
    "BG DRIVE":       dict(D=0.60, M=1.0, P=-1.0, B=0.0),
    # high gain
    "VO LEAD":        dict(D=0.70, M=1.0, P=3.0, B=-1.0),
    "BG LEAD":        dict(D=0.76, M=1.0, P=-1.0, B=0.0),
    "HiGAIN STACK":   dict(D=0.76, M=0.0, P=0.0, B=0.0),
    "SLDN":           dict(D=0.78, M=2.0, P=0.0, B=0.0),
    "ORNG ROCK REVERB": dict(D=0.78, M=1.0, P=-2.5, B=2.0),
    "POWER DRIVE":    dict(D=0.80, M=0.0, P=-2.0, B=2.0),
    "T-AMP LEAD":     dict(D=0.80, M=0.0, P=1.0, B=0.0),
    "R-FIER VINTAGE": dict(D=0.82, M=-1.0, P=-2.5, B=2.5),
    "5150 DRIVE":     dict(D=0.84, M=-2.5, P=1.0, B=0.0),
    "EXTREME LEAD":   dict(D=0.86, M=1.0, P=0.0, B=0.0),
    "R-FIER MODERN":  dict(D=0.88, M=-5.0, P=1.0, B=0.0, L=1.0),
    "BGNR UB METAL":  dict(D=0.92, M=-3.0, P=0.0, B=1.0, L=1.0),
    "CORE METAL":     dict(D=0.96, M=-6.0, P=2.0, B=-1.0, L=1.0),
    # "amp|pedal": very saturated but thin-bottomed = distortion/fuzz pedal into a crunch amp (grunge, punk)
    "STACK CRUNCH|DISTORTION": dict(D=0.88, M=-3.0, P=2.0, B=0.0, L=-8.0),
    "MS1959 I|MUFF FUZZ":      dict(D=0.92, M=-4.0, P=-1.0, B=1.0, L=-7.0),
}
PEDAL_SETTINGS = {"DISTORTION": (55, 55), "MUFF FUZZ": (60, 50)}  # (drive, level)
LEAD_FRIENDLY = {"BG LEAD", "EXTREME LEAD", "SLDN", "T-AMP LEAD", "VO LEAD", "MS1959 I+II"}
CLEAN_SIGNATURES = {
    # g = clean "edge" (0 = glassy clean, 1 = edge of breakup). NATURAL CLEAN / FULL RANGE are left out
    # on purpose: they are near-transparent and sounded "like an acoustic, no amp at all" (user, 2026-10-17).
    "CLEAN TWIN":     dict(g=0.4, M=-1.0, P=0.0, B=0.0),
    "JC-120":         dict(g=0.1, M=0.0, P=3.0, B=-1.0),
    "PRO CRUNCH":     dict(g=1.0, M=0.5, P=0.0, B=0.0),
    "DELUXE CRUNCH":  dict(g=1.0, M=0.0, P=-1.0, B=1.5),
}
DEFAULT_KNOBS = {"gain": 65, "bass": 52, "middle": 50, "treble": 55, "presence": 10}


@dataclass
class MatchResult:
    group: str
    patch: Patch
    recipe: dict                     # human-readable decisions (shown in CLI / report)
    base: str | None = None
    scores: dict[str, float] = field(default_factory=dict)


def drive_index(flatness: float, for_gain: bool = False) -> float:
    """Spectral flatness -> 0..1 drive on a log scale.

    Model selection uses the range the signatures were designed on (0.05 .. 0.45). The GAIN knob uses
    a lower range (0.035 .. 0.40): separated, mastered, codec-compressed stems read less saturated than
    the real amp (A/B by ear: Gitaroo rhythm "too soft crunch", 2026-10-17).
    """
    lo, hi = (0.035, 0.40) if for_gain else (0.05, 0.45)
    return max(0.0, min(1.0, (math.log(max(flatness, 1e-4)) - math.log(lo)) / (math.log(hi) - math.log(lo))))


# Flatness is "how noise-like" the 0.8-5 kHz spectrum is. Chords through distortion fill it with
# intermodulation, but a single-note riff keeps a clean harmonic line spectrum however hard it is driven,
# so it reads too clean (Do I Wanna Know fuzz riff: periodicity 0.84, flatness 0.09 = "soft crunch" by ear,
# 2026-10-17). Typical driven chord parts sit at periodicity <= 0.6; above that the flatness is scaled up.
MONO_PERIODICITY = 0.6
MONO_FLATNESS_GAIN = 1.75  # per unit periodicity above MONO_PERIODICITY, in log flatness


def drive_flatness(g: GroupProfile) -> float:
    """Measured flatness, corrected for single-note playing (driven parts only)."""
    if g.gain_class == "clean":
        return g.flatness
    return g.flatness * math.exp(MONO_FLATNESS_GAIN * max(0.0, g.periodicity - MONO_PERIODICITY))


def _dev(g: GroupProfile, kind: str) -> dict[str, float]:
    ref = REF[kind]
    return {k: g.descriptors.get(k, ref[k]) - ref[k] for k in ref}


def choose_preamp(g: GroupProfile, role: str) -> tuple[str, dict[str, float]]:
    if g.gain_class == "clean":
        dv = _dev(g, "clean")
        edge = max(0.0, min(1.0, (g.gain - 0.1) / 0.3))
        scores = {t: ((edge - s["g"]) / 0.35) ** 2 + ((dv["mid_scoop_db"] - s["M"]) / 3) ** 2
                  + ((dv["presence_db"] - s["P"]) / 3) ** 2 + 0.3 * ((dv["body_db"] - s["B"]) / 4) ** 2
                  for t, s in CLEAN_SIGNATURES.items()}
    else:
        dv = _dev(g, "driven")
        D = drive_index(drive_flatness(g))
        # low end is noisy (bass bleed), so it only counts where a signature states it (metal vs pedal)
        scores = {t: ((D - s["D"]) / 0.10) ** 2 + ((dv["mid_scoop_db"] - s["M"]) / 2.5) ** 2
                  + ((dv["presence_db"] - s["P"]) / 3) ** 2 + 0.3 * ((dv["body_db"] - s["B"]) / 4) ** 2
                  + (((dv["low_depth_db"] - s["L"]) / 4) ** 2 if "L" in s else 0.0)
                  - (0.6 if role == "lead" and t in LEAD_FRIENDLY else 0.0)
                  for t, s in PREAMP_SIGNATURES.items()}
    best = min(scores, key=scores.get)
    return best, {k: round(v, 2) for k, v in sorted(scores.items(), key=lambda kv: kv[1])[:4]}


def _clamp(v: float, lo: float, hi: float) -> int:
    return int(round(max(lo, min(hi, v))))


def _neutral_template(preamp_type: str) -> tuple[Patch, str]:
    """A BOSS preset with the same preamp type (sane routing/levels/assigns), else the first preset."""
    kb = [e for e in load_kb() if e.collection == "BOSS GT-1 Presets"]
    same = [e for e in kb if e.patch.get("preamp_a_type") == preamp_type]
    e = same[0] if same else kb[0]
    return e.patch.copy(), e.id


def short_title(meta: dict, width: int = 11) -> str:
    """Whole words of the song title that fit into `width` characters."""
    t = re.sub(r"\(.*?\)|\[.*?\]", "", meta.get("title", "") or "")
    t = re.sub(r"[^A-Za-z0-9 ]+", " ", t).upper().split()
    out = ""
    for w in t:
        if len(out) + len(w) + (1 if out else 0) > width:
            break
        out = f"{out} {w}".strip()
    return out or (t[0][:width] if t else "TONE")


def apply_pitch_shift(p: Patch, semitones: int, cents: int) -> None:
    """FX1 (before the amp) = PITCH SHIFTER, wet only: retunes the user's guitar to the recording.

    GT-1 exposes PITCH / FINE / EFFECT LEVEL / DIRECT LEVEL / PRE DELAY / FEEDBACK; voice and mode are
    hidden legacy fields, kept at 1 voice / MEDIUM like BOSS' own tune-down preset (METAL DELAY).
    """
    p.on("fx1")
    p.set("fx1_fx_type", "PITCHSHIFTER")
    p.set_raw("fx1_pitch_shifter_voice", 0)
    p.set("fx1_pitch_shifter_ps1mode", "MEDIUM")
    p.set("fx1_pitch_shifter_ps1pitch", semitones)
    p.set("fx1_pitch_shifter_ps1fine", max(-40, min(40, cents)))
    p.set("fx1_pitch_shifter_ps1level", 100)
    p.set("fx1_pitch_shifter_direct_mix", 0)
    p.set_raw("fx1_pitch_shifter_ps1pre_dly", 0)
    p.set("fx1_pitch_shifter_ps1f_back", 0)
    p.set_raw("fx1_pitch_shifter_ps2level", 0)


def build_patch(role: str, g: GroupProfile, tempo: float, meta: dict,
                output_select_raw: int | None = None, tuning: "TuningEstimate | None" = None) -> MatchResult:
    choice, scores = choose_preamp(g, role)
    ptype, _, pedal = choice.partition("|")
    p, base_id = _neutral_template(ptype)
    p.meta = {"category": "ROCK"}
    kind = "clean" if g.gain_class == "clean" else "driven"
    dv = _dev(g, kind)
    st = type_stats().get(ptype, {})
    knobs = {k: st.get(k, DEFAULT_KNOBS[k]) if st.get("n", 0) >= 5 else DEFAULT_KNOBS[k] for k in DEFAULT_KNOBS}
    why: list[str] = []

    # routing / unused or non-existent blocks (GT-1 has no EQ/COMP/CHORUS blocks: docs/01)
    p.set("divider_mode", "SINGLE")
    p.set("divider_ch_select", "Ch A")
    for blk in ("fx1", "fx2", "pedal_fx", "comp", "chorus", "eq", "od_ds"):
        p.on(blk, False)
    # Controls: the template's CTL1 toggled its FX2 (a BPM-synced mod) and ASSIGN1 ran a wave LFO
    # (user report 2026-10-17). Make CTL1 a solo boost (most common pro choice: 116/411), kill assigns.
    p.set_raw("ctl_exp_accel_ctl_func", 2)      # CONTROL_FUNC1[2] = PREAMP SOLO
    p.set_raw("ctl_exp_accel_ctl_min", 0)
    p.set_raw("ctl_exp_accel_ctl_max", 1)
    p.set_raw("ctl_exp_accel_ctl_src_mode", 0)
    p.set_raw("ctl_exp_sub_ctl1_func", 0)       # external footswitches: OFF
    p.set_raw("ctl_exp_sub_ctl2_func", 0)
    for i in range(1, 9):
        p.set_raw(f"assign{i}_on_off", 0)
    p.set_raw("preamp_a_solo_level", 60)

    # ---- preamp
    if kind == "driven":
        D, Dc = drive_index(drive_flatness(g)), PREAMP_SIGNATURES[choice]["D"]
        Dg = drive_index(drive_flatness(g), for_gain=True)
        # with a distortion pedal doing the saturation the amp itself stays at crunch level
        # +10: pro-patch medians sit low for a live guitar (user: "ana ton çok clean" on MS1959 I G58)
        gain = ((knobs["gain"] if not pedal else knobs["gain"] - 10) + (D - Dc) * 120 + (Dg - D) * 60 + 10
                + (6 if role == "lead" else 0))
        why.append(f"drive {D:.2f} -> {choice.replace('|', ' + ')}")
    else:
        edge = max(0.0, min(1.0, (g.gain - 0.1) / 0.3))
        # by ear (2026-10-17): G53 had audible drive, G37 sounded sterile -> stay around the pro median (~45)
        gain = 40 + edge * 10
        why.append(f"clean edge {edge:.2f} -> {ptype}")
    # Low end: the stem's lows include bass-guitar bleed, so only ever reduce bass from the median.
    bass = max(knobs["bass"] - 10, knobs["bass"] - max(0.0, dv["low_depth_db"]) * 2 - max(0.0, dv["body_db"] - 3) * 1.5)
    middle = knobs["middle"] + dv["mid_scoop_db"] * 3
    # Separation + codec dull the top end, so measured darkness may only pull treble/presence down a
    # little; brightness is followed fully (user: clean "çok sönük" with treble cut to 43).
    treble = knobs["treble"] + max(-3.0, dv["presence_db"] * 2) + (4 if kind == "clean" else 0)
    presence = knobs["presence"] + max(-2.0, dv["presence_db"] * 1.5 + max(-4.0, min(4.0, dv["fizz_db"] / 3)))
    if kind == "clean":
        presence += 4
    p.on("preamp_a")
    p.set("preamp_a_type", ptype)
    p.set("preamp_a_gain", _clamp(gain, 5, 95))
    p.set("preamp_a_bass", _clamp(bass, 25, 75))
    p.set("preamp_a_middle", _clamp(middle, 15, 85))
    p.set("preamp_a_treble", _clamp(treble, 25, 80))
    p.set("preamp_a_presence", _clamp(presence, 0, 60))
    p.set("preamp_a_bright", "OFF")
    p.set("preamp_a_gain_sw", "MIDDLE")  # GT-1 pins it to MIDDLE
    p.set("preamp_a_solo_sw", "OFF")
    p.set("preamp_a_sp_type", "ORIGIN")

    # ---- master EQ: what the tone stack cannot reach (max +-4 dB, never a low boost)
    m_gain = 0
    if abs(dv["mid_scoop_db"]) > 4:
        m_gain = _clamp(math.copysign((abs(dv["mid_scoop_db"]) - 3) / 2, dv["mid_scoop_db"]), -4, 4)
    p.set("master_eq_low_gain", -_clamp(max(0.0, dv["low_depth_db"] - 3) / 2, 0, 4))
    p.set("master_eq_mid_freq", "630Hz")
    p.set("master_eq_mid_q", "1")
    p.set("master_eq_mid_gain", m_gain)
    p.set("master_eq_high_gain", _clamp(dv["fizz_db"] / 6, -1, 2))

    # ---- boost: tight high gain rhythm or any driven lead
    od = None
    if pedal:
        od = (pedal, *PEDAL_SETTINGS[pedal])
    elif kind == "driven" and role == "lead":
        od = ("T-SCREAM", 20, 65) if drive_index(drive_flatness(g)) > 0.6 else ("MID BOOST", 25, 62)
    elif kind == "driven" and drive_index(drive_flatness(g)) > 0.75 and dv["low_depth_db"] < 2:
        od = ("T-SCREAM", 10, 60)
    elif kind == "driven" and g.sustain >= 0.8:
        # long, singing sustain on a crunch amp = an overdrive pushing it (user: "daha sustainli")
        od = ("T-SCREAM", 30, 62)
    if od:
        p.on("od_ds")
        p.set("od_ds_type", od[0])
        p.set("od_ds_drive", od[1])
        p.set("od_ds_effect_level", od[2])
        p.set("od_ds_tone", 0)
        p.set("od_ds_bottom", 0)
        p.set("od_ds_direct_mix", 0)
        p.set("od_ds_solo_sw", "OFF")
        why.append(f"{od[0]} boost")

    # ---- loudness: every patch at the same volume (user: Running Away far louder than the others).
    # Level follows BOSS' level-matched factory presets for this amp, gain and boost; PATCH LEVEL stays 100.
    p.set("preamp_a_level", matched_preamp_level(ptype, p.get("preamp_a_gain"), od is not None,
                                                 od[2] if od else 50, od[1] if od else 50))
    p.set("patch_level", 100)

    # ---- noise gate: the GT-1 keeps NS1 always on (device re-enables it; 411/411 pro patches) -> use threshold
    p.on("ns1", True)
    if kind == "driven":
        p.set("ns1_threshold", _clamp(20 + (drive_index(drive_flatness(g)) - 0.4) * 50, 15, 50))
    else:
        p.set("ns1_threshold", 5)

    # ---- tuning: pitch shifter only when the song is not in EADGBE / DADGBE (user rule)
    shifting = tuning is not None and tuning.needs_shift
    if shifting:
        apply_pitch_shift(p, tuning.semitones, tuning.cents)
        why.append(f"akort {tuning.name}: {tuning.semitones:+d} yarım ses")

    # ---- compressor for clean parts: FX1 (pre-amp), or FX2 when FX1 holds the pitch shifter
    if kind == "clean":
        blk = "fx2" if shifting else "fx1"
        p.on(blk)
        p.set(f"{blk}_fx_type", "COMPRESSOR")
        p.set(f"{blk}_adv_comp_type", "BOSS COMP")
        p.set(f"{blk}_adv_comp_sustain", 30)
        p.set(f"{blk}_adv_comp_attack", 50)
        p.set(f"{blk}_adv_comp_tone", 0)
        p.set(f"{blk}_adv_comp_level", 50)

    # ---- delay: measured only. A weak ("possible") echo is trusted on lighter parts where delays are
    # common; on heavy rhythm it is too often a false positive (calibration: CAYA chorus section).
    dl = g.delay
    use_delay = dl.detected or (dl.possible and (role in ("lead", "clean") or g.gain_class != "high_gain"))
    p.on("delay", use_delay)
    if use_delay:
        p.set("delay_type", "STANDARD")
        p.set_raw("delay_delay_time", int(round(dl.time_ms)))
        p.set("delay_f_back", _clamp(dl.feedback * 100, 10, 45))
        p.set("delay_effect_level", 35 if dl.detected else 22)
        p.set("delay_direct_mix", 100)
        why.append(f"delay {dl.time_ms:.0f} ms")

    # ---- reverb
    amount = g.reverb.amount
    rv = {"dry": None, "small": ("ROOM", 0.8, 15), "medium": ("PLATE", 1.6, 22), "large": ("HALL1", 2.5, 30)}.get(amount)
    if amount == "unknown":
        rv = ("PLATE", 1.8, 20) if kind == "clean" else ("ROOM", 1.2, 18) if role == "lead" else ("ROOM", 0.8, 12)
    p.on("reverb", rv is not None)
    if rv:
        p.set("reverb_type", rv[0])
        p.set_raw("reverb_time", int(round(rv[1] * 10)) - 1)
        p.set("reverb_effect_level", rv[2])
        p.set("reverb_direct_mix", 100)

    if 40 <= tempo <= 250:
        p.set_raw("master_bpm", int(round(tempo)))
    if output_select_raw is not None:
        p.set_raw("output_select", output_select_raw)
    suffix = {"rhythm": "RHY", "lead": "LEAD", "clean": "CLN", "crunch": "CRN"}.get(role, role[:4].upper())
    p.name = f"{short_title(meta)} {suffix}"[:16]

    recipe = {"preamp": ptype, "pedal": pedal or None,
              "tuning": tuning.to_dict() if tuning is not None else None, "drive": round(drive_index(drive_flatness(g)), 2) if kind == "driven" else None,
              "deviation_db": {k: round(v, 1) for k, v in dv.items()}, "why": "; ".join(why)}
    return MatchResult(role, p, recipe, base_id, scores)


# ---------------------------------------------------------------------------------- dual-tone patch
# (assign target name in gt1_spec.json, patch field) in priority order; at most 8 assigns per patch
DUAL_TARGETS = [
    # LEVEL right after the amp: both tones must come out equally loud (user, 2026-10-17)
    ("PREAMP: TYPE", "preamp_a_type"), ("PREAMP: GAIN", "preamp_a_gain"), ("PREAMP: LEVEL", "preamp_a_level"),
    ("OD/DS: ON/OFF", "od_ds_on_off"),
    ("DELAY: ON/OFF", "delay_on_off"), ("FX1: ON/OFF", "fx1_on_off"), ("FX2: ON/OFF", "fx2_on_off"),
    # ambience before small knob moves: a dry clean side sounded "like no effect at all" (user, 2026-10-17)
    ("REVERB: E.LEVEL", "reverb_effect_level"), ("REVERB: TYPE", "reverb_type"), ("REVERB: TIME", "reverb_time"),
    ("PREAMP: TREBLE", "preamp_a_treble"), ("PREAMP: BASS", "preamp_a_bass"), ("PREAMP: MIDDLE", "preamp_a_middle"),
    ("PREAMP: PRESENCE", "preamp_a_presence"),
]
# knob differences below this are not worth one of the 8 assigns
_KNOBS = {"preamp_a_treble", "preamp_a_bass", "preamp_a_middle", "preamp_a_presence"}
_MIN_KNOB_STEP = 4
_DUAL_SHORT = {"rhythm": "RHY", "lead": "LD", "clean": "CLN", "crunch": "CRN"}


def build_dual(main: MatchResult, alt: MatchResult, meta: dict) -> MatchResult:
    """One patch, two tones: CTL off = `main`, CTL on (toggle) = `alt`, via CTL1 -> ASSIGN 1..8."""
    p = main.patch.copy()
    a = alt.patch
    spec = p.spec
    # blocks only the alt tone uses: carry their settings over (switched on/off by an assign)
    if a.get_raw("delay_on_off") and not p.get_raw("delay_on_off"):
        for f in ("delay_type", "delay_delay_time", "delay_f_back", "delay_effect_level", "delay_direct_mix"):
            p.set_raw(f, a.get_raw(f))
    for blk in ("fx1", "fx2"):
        if a.get_raw(f"{blk}_on_off") and not p.get_raw(f"{blk}_on_off"):
            for f in [k for k in spec.field_off if k.startswith((f"{blk}_fx_type", f"{blk}_adv_comp_"))]:
                p.set_raw(f, a.get_raw(f))
    if a.get_raw("od_ds_on_off") and not p.get_raw("od_ds_on_off"):
        for f in [k for k in spec.field_off if k.startswith("od_ds_") and k != "od_ds_on_off"]:
            p.set_raw(f, a.get_raw(f))
    targets = spec.raw["assign_targets"]
    used = []
    for tname, field_name in DUAL_TARGETS:
        lo, hi = p.get_raw(field_name), a.get_raw(field_name)
        if lo == hi or tname not in targets or len(used) == 8:
            continue
        if field_name in _KNOBS and abs(hi - lo) < _MIN_KNOB_STEP:
            continue
        i = len(used) + 1
        p.set_raw(f"assign{i}_on_off", 1)
        p.set_raw(f"assign{i}_target", targets[tname]["id"])
        p.set_raw(f"assign{i}_target_min", lo)
        p.set_raw(f"assign{i}_target_max", hi)
        p.set_raw(f"assign{i}_source", spec.raw["assign_sources"]["CTL1"])
        p.set_raw(f"assign{i}_source_mode", spec.raw["assign_source_modes"]["TOGGLE"])
        p.set_raw(f"assign{i}_act_range_lo", 0)
        p.set_raw(f"assign{i}_act_range_hi", 127)
        used.append(f"{tname} {spec.raw_to_display(field_name, lo)}→{spec.raw_to_display(field_name, hi)}")
    for i in range(len(used) + 1, 9):
        p.set_raw(f"assign{i}_on_off", 0)
    p.set_raw("ctl_exp_accel_ctl_func", 0)  # CTL1 only drives the assigns (no extra solo boost)
    # NS threshold cannot be assigned: keep it gentle enough for the clean side
    p.set("ns1_threshold", min(int(p.get("ns1_threshold") or 0), int(a.get("ns1_threshold") or 0) + 17, 22))
    tag = f"{_DUAL_SHORT.get(main.group, 'A')}/{_DUAL_SHORT.get(alt.group, 'B')}"
    p.name = f"{short_title(meta, 15 - len(tag))} {tag}"[:16]
    recipe = {"dual": True, "ctl_off": main.group, "ctl_on": alt.group, "assigns": used,
              "main": main.recipe, "alt": alt.recipe,
              "why": f"CTL kapalı = {main.group} ({main.recipe['preamp']}), CTL açık = {alt.group} ({alt.recipe['preamp']})"}
    return MatchResult(f"{main.group}+{alt.group}", p, recipe, main.base, main.scores)


def pick_dual(ana: TrackAnalysis, groups: list[str]) -> tuple[str, str] | None:
    """Main tone = longest group; CTL tone = clean if there is one, else lead, else the next longest."""
    if len(groups) < 2:
        return None
    main = max(groups, key=lambda g: ana.groups[g].seconds)
    rest = [g for g in groups if g != main]
    alt = next((g for g in ("clean", "lead") if g in rest), max(rest, key=lambda g: ana.groups[g].seconds))
    return main, alt


def match_groups(meta: dict, ana: TrackAnalysis, groups: list[str], output_select_raw: int | None,
                 dual: bool = True, tuning: "TuningEstimate | None" = None, claude: bool = False,
                 progress=lambda s: None, info: dict | None = None) -> list[MatchResult]:
    """Engine patch per group; with `claude` Claude reviews them first (claude_mode); then CTL pairing.
    `info` (if given) receives what Claude mode did."""
    singles = {g: build_patch(g, ana.groups[g], ana.tempo, meta, output_select_raw, tuning) for g in groups}
    if claude:
        from .claude_mode import refine

        singles, cinfo = refine(meta, ana, singles, tuning, progress)
        if info is not None:
            info["claude"] = cinfo
    pair = pick_dual(ana, groups) if dual else None
    if not pair:
        return list(singles.values())
    main, alt = pair
    out = [build_dual(singles[main], singles[alt], meta)]
    # any third group still gets its own patch
    out += [m for g, m in singles.items() if g not in pair]
    return out
