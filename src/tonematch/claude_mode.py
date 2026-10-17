"""Claude mode (opt-in, `run --claude`): Claude reviews the deterministic engine's patches.

The engine (`match.build_patch`) always runs first. In Claude mode its proposal, the measurements and the
song's identity go to Claude, which may change the amp model, knobs, boost and effects using what it knows
about the recording's real rig. Its answer is a JSON recipe (schema below) applied on top of the engine
patch; everything the engine guarantees stays: GT-1 block rules, pitch shifter for the user's tuning,
loudness matching, noise gate, CTL dual-tone switching. Any failure falls back to the engine patch.

Backends: the Anthropic API (when ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN is set) or the local `claude`
CLI (Claude Code login), both with structured JSON output. No tools, no web search: Claude answers from
what it knows.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import replace

from .analysis import GroupProfile, TrackAnalysis
from .catalog import MOD_TYPES, OD_TYPES, PREAMP_TYPES
from .kb import matched_preamp_level
from .match import MatchResult, drive_flatness, drive_index
from .report import tone_view

log = logging.getLogger(__name__)

MODEL = os.environ.get("TONEMATCH_CLAUDE_MODEL", "claude-opus-5-5")
SP_TYPES = ["ORIGIN", '1x8"', '1x10"', '1x12"', '2x12"', '4x10"', '4x12"', '8x12"']
DELAY_TYPES = ["STANDARD", "PAN", "REVERSE", "ANALOG", "TAPE", "MODULATE", "TERA ECHO"]
REVERB_TYPES = ["AMBIENCE", "ROOM", "HALL1", "HALL2", "PLATE", "SPRING", "MODULATE"]
EQ_FREQS = ["200Hz", "250Hz", "315Hz", "400Hz", "500Hz", "630Hz", "800Hz", "1.00kHz", "1.25kHz", "1.60kHz",
            "2.00kHz", "2.50kHz", "3.15kHz", "4.00kHz"]
# FX2 modulation type -> (rate, depth, level) fields
MOD_FIELDS = {
    "CHORUS": ("fx2_chorus_rate", "fx2_chorus_depth", "fx2_chorus_e_level"),
    "PHASER": ("fx2_phaser_rate", "fx2_phaser_depth", "fx2_phaser_effect_level"),
    "FLANGER": ("fx2_flanger_rate", "fx2_flanger_depth", "fx2_flanger_effect_level"),
    "TREMOLO": ("fx2_tremolo_rate", "fx2_tremolo_depth", "fx2_tremolo_level"),
    "ROTARY": ("fx2_rotary_rate_slow", "fx2_rotary_depth", "fx2_rotary_level"),
    "UNI_V": ("fx2_uni_v_rate", "fx2_uni_v_depth", "fx2_uni_v_level"),
    "VIBRATO": ("fx2_vibrato_rate", "fx2_vibrato_depth", "fx2_vibrato_level"),
}

SYSTEM = """You are a guitar tone engineer who knows the gear behind well-known recordings and knows the BOSS GT-1
multi-effects processor inside out. You recreate a recording's guitar tones as GT-1 patches for one player.
You get measurements of the isolated guitar, the song's identity and the patch a measurement-only engine
proposed. Improve that proposal where your knowledge of the recording or of the GT-1 says it is off; keep
what is already right. Answer only with the JSON object the schema asks for."""

RULES = """How the player's rig works:
- Guitar -> GT-1 -> the front input of a guitar amp with every knob at zero (the amp only makes it loud).
  The whole tone lives in the patch: PREAMP on with its speaker simulation.
- The GT-1 has no separate EQ, COMP or CHORUS block. Modulation goes in FX2; tone shaping beyond the preamp
  knobs goes in MASTER EQ (keep it within +-6 dB, avoid boosting lows: the stem's lows contain bass bleed).
- These are handled for you, do not try to set them: noise gate, patch/preamp levels (all patches are
  loudness-matched afterwards), pitch shifter for the song's tuning (FX1), the clean compressor, CTL switching.

What the player told us by ear about earlier patches:
- Crunch tones came out too soft and too clean: recordings are more saturated and sustained than a bare
  measurement suggests. A crunch amp near the middle of its gain range often needs more gain or a boost.
- Clean tones must not be sterile ("like an acoustic, no amp at all"): keep amp character and some ambience.

How to read the measurements:
- `drive` 0..1 from spectral flatness (0.05 clean ... 0.45+ high gain); single-note riffs read lower than
  they sound. `gain_class` clean / crunch / high_gain.
- `deviation_db`: mid_scoop (- = scooped), presence, body (low mids), low_depth, fizz, relative to a typical
  recording. `bands_db`: long-term spectrum of the stem by octave.
- `delay.detected` with a time is a measured echo: keep it. `delay.possible` is weaker evidence.
  `reverb.amount` is measured ambience (mix reverb included; unknown = could not be measured).

How to answer:
- Identify the recording and what rig was used for each part, as far as you know it. Say how sure you are
  in `confidence` (low when you do not know the recording) and explain the change in `why` (one or two
  sentences, Turkish).
- When unsure, stay close to the engine's proposal.
- Give one entry per group, using the group keys given."""


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def schema(groups: list[str]) -> dict:
    i, n, b = {"type": "integer"}, {"type": "number"}, {"type": "boolean"}
    enum = lambda xs: {"type": "string", "enum": list(xs)}  # noqa: E731
    patch = _obj({
        "group": enum(groups),
        "preamp": _obj({"type": enum(PREAMP_TYPES), "gain": i, "bass": i, "middle": i, "treble": i, "presence": i,
                        "sp_type": enum(SP_TYPES)}),
        "od": _obj({"on": b, "type": enum(OD_TYPES), "drive": i, "tone": i, "level": i}),
        "delay": _obj({"on": b, "type": enum(DELAY_TYPES), "time_ms": i, "feedback": i, "level": i}),
        "reverb": _obj({"on": b, "type": enum(REVERB_TYPES), "time_s": n, "level": i}),
        "mod": _obj({"on": b, "type": enum(MOD_TYPES), "rate": i, "depth": i, "level": i}),
        "master_eq": _obj({"low_db": i, "mid_db": i, "mid_freq": enum(EQ_FREQS), "high_db": i}),
        "confidence": enum(["high", "medium", "low"]),
        "why": {"type": "string"},
    })
    return _obj({"song": {"type": "string"}, "rig_notes": {"type": "string"},
                 "patches": {"type": "array", "items": patch}})


# ------------------------------------------------------------------------------------------- prompt
def _measurements(g: GroupProfile) -> dict:
    return {
        "seconds": g.seconds, "segments": [[round(a, 1), round(b, 1)] for a, b in g.segments[:6]],
        "gain_class": g.gain_class, "drive": round(drive_index(drive_flatness(g)), 2), "stereo": g.stereo,
        "single_note_periodicity": g.periodicity, "sustain": g.sustain, "crest_db": g.crest_db,
        "deviation_db": {k: round(v, 1) for k, v in g.descriptors.items()}, "bands_db": g.bands_db,
        "delay": {"detected": g.delay.detected, "possible": g.delay.possible, "time_ms": round(g.delay.time_ms),
                  "feedback": round(g.delay.feedback, 2)},
        "reverb": {"amount": g.reverb.amount, "decay_s": g.reverb.decay_s},
    }


def _proposal(m: MatchResult) -> dict:
    p, s = m.patch, m.patch.summary()
    v = tone_view(p)
    v.update(sp_type=s["preamp_a_sp_type"], why=m.recipe.get("why", ""),
             master_eq={"low_db": s["master_eq_low_gain"], "mid_db": s["master_eq_mid_gain"],
                        "mid_freq": s["master_eq_mid_freq"], "high_db": s["master_eq_high_gain"]})
    return v


def build_prompt(meta: dict, ana: TrackAnalysis, singles: dict[str, MatchResult], tuning) -> str:
    song = {k: meta.get(k) for k in ("title", "artist", "uploader", "channel", "album", "release_year", "upload_date")
            if meta.get(k)}
    parts = [
        "Recording:", json.dumps(song, ensure_ascii=False),
        f"Tempo (beat tracker, may be half/double): {ana.tempo} BPM",
        f"Song tuning given by the player: {tuning.name if tuning else 'EADGBE'} (shift handled by the patch)",
        "Guitar parts found in the isolated guitar stem (key = group):",
        json.dumps({g: _measurements(ana.groups[g]) for g in singles}, indent=1, ensure_ascii=False),
        "The engine's proposal per group:",
        json.dumps({g: _proposal(m) for g, m in singles.items()}, indent=1, ensure_ascii=False),
        RULES,
    ]
    return "\n\n".join(parts)


# ------------------------------------------------------------------------------------------ backends
class ClaudeError(RuntimeError):
    pass


def backend() -> str:
    forced = os.environ.get("TONEMATCH_CLAUDE_BACKEND")
    if forced in ("api", "cli"):
        return forced
    return "api" if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") else "cli"


def _ask_api(system: str, prompt: str, sch: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": sch}},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as e:
        raise ClaudeError(f"Claude API'ye bağlanılamadı: {e}") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Claude API hatası {e.status_code}: {e.message}") from e
    if resp.stop_reason == "refusal":
        raise ClaudeError(f"Claude isteği reddetti: {getattr(resp.stop_details, 'category', None)}")
    if resp.stop_reason == "max_tokens":
        raise ClaudeError("Claude'un cevabı yarıda kesildi (max_tokens)")
    text = next((blk.text for blk in resp.content if blk.type == "text"), "")
    return json.loads(text)


def _ask_cli(system: str, prompt: str, sch: dict) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise ClaudeError("Claude modu için ANTHROPIC_API_KEY ya da giriş yapılmış `claude` CLI (Claude Code) gerekli")
    cmd = [exe, "-p", "--output-format", "json", "--model", MODEL, "--json-schema", json.dumps(sch),
           "--system-prompt", system, "--tools", "", "--no-session-persistence", "--effort", "high"]
    with tempfile.TemporaryDirectory() as cwd:  # neutral cwd: no project CLAUDE.md, nothing to read
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=900)
        except subprocess.TimeoutExpired as e:
            raise ClaudeError("Claude 15 dakikada cevap vermedi") from e
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"claude CLI başarısız ({r.returncode}): {(r.stderr or r.stdout)[-400:]}") from e
    if out.get("is_error") or r.returncode != 0:
        raise ClaudeError(f"claude CLI hatası: {str(out.get('result'))[:400]}")
    data = out.get("structured_output")
    if not isinstance(data, dict):
        raise ClaudeError("claude CLI yapılandırılmış cevap döndürmedi")
    return data


def ask(prompt: str, groups: list[str]) -> dict:
    sch = schema(groups)
    return (_ask_api if backend() == "api" else _ask_cli)(SYSTEM, prompt, sch)


# ------------------------------------------------------------------------------------- recipe -> patch
def _clamp(v, lo, hi) -> int:
    try:
        return int(round(max(lo, min(hi, float(v)))))
    except (TypeError, ValueError):
        return int(lo)


def apply_recipe(m: MatchResult, r: dict, g: GroupProfile) -> MatchResult:
    """Claude's recipe on top of the engine patch; engine guarantees stay (see module doc)."""
    p = m.patch.copy()
    pre = r["preamp"]
    p.set("preamp_a_type", pre["type"])
    p.set("preamp_a_gain", _clamp(pre["gain"], 0, 100))
    for k in ("bass", "middle", "treble", "presence"):
        p.set(f"preamp_a_{k}", _clamp(pre[k], 0, 100))
    p.set("preamp_a_sp_type", pre["sp_type"])

    od = r["od"]
    p.on("od_ds", bool(od["on"]))
    if od["on"]:
        p.set("od_ds_type", od["type"])
        p.set("od_ds_drive", _clamp(od["drive"], 0, 100))
        p.set("od_ds_tone", _clamp(od["tone"], -50, 50))
        p.set("od_ds_effect_level", _clamp(od["level"], 0, 100))
        p.set("od_ds_bottom", 0)
        p.set("od_ds_direct_mix", 0)
        p.set("od_ds_solo_sw", "OFF")

    dl = r["delay"]
    measured = g.delay.detected
    if dl["on"] or measured:  # a measured echo always stays, at the measured time
        p.on("delay")
        p.set("delay_type", dl["type"])
        p.set_raw("delay_delay_time", _clamp(g.delay.time_ms if measured else dl["time_ms"], 1, 2000))
        p.set("delay_f_back", _clamp(dl["feedback"], 0, 80))
        p.set("delay_effect_level", _clamp(dl["level"], 0, 100))
        p.set("delay_direct_mix", 100)
    else:
        p.on("delay", False)

    rv = r["reverb"]
    p.on("reverb", bool(rv["on"]))
    if rv["on"]:
        p.set("reverb_type", rv["type"])
        p.set_raw("reverb_time", _clamp(float(rv["time_s"]) * 10 - 1, 0, 99))
        p.set("reverb_effect_level", _clamp(rv["level"], 0, 100))
        p.set("reverb_direct_mix", 100)

    mod = r["mod"]
    fx2_busy = p.get_raw("fx2_on_off") and p.get("fx2_fx_type") == "COMPRESSOR"  # clean comp while shifting
    if mod["on"] and not fx2_busy and mod["type"] in MOD_FIELDS:
        rate, depth, level = MOD_FIELDS[mod["type"]]
        p.on("fx2")
        p.set("fx2_fx_type", mod["type"])
        p.set_raw(rate, _clamp(mod["rate"], 0, 100))
        p.set_raw(depth, _clamp(mod["depth"], 0, 100))
        p.set_raw(level, _clamp(mod["level"], 0, 100))
    elif not fx2_busy:
        p.on("fx2", False)

    eq = r["master_eq"]
    p.set("master_eq_low_gain", _clamp(eq["low_db"], -6, 2))
    p.set("master_eq_mid_gain", _clamp(eq["mid_db"], -6, 6))
    p.set("master_eq_mid_freq", eq["mid_freq"])
    p.set("master_eq_high_gain", _clamp(eq["high_db"], -6, 6))

    # loudness: same rule as the engine, for Claude's amp / gain / boost
    p.set("preamp_a_level", matched_preamp_level(pre["type"], p.get("preamp_a_gain"), bool(od["on"]),
                                                 p.get("od_ds_effect_level"), p.get("od_ds_drive")))
    p.set("patch_level", 100)

    recipe = dict(m.recipe, preamp=pre["type"], pedal=None, engine_why=m.recipe.get("why", ""),
                  claude={"confidence": r["confidence"], "why": r["why"]},
                  why=f"Claude ({r['confidence']}): {r['why']}")
    return replace(m, patch=p, recipe=recipe)


def refine(meta: dict, ana: TrackAnalysis, singles: dict[str, MatchResult], tuning, progress=print
           ) -> tuple[dict[str, MatchResult], dict]:
    """Claude mode: returns (patches, info). On any failure the engine patches come back unchanged."""
    groups = list(singles)
    which = backend()
    progress(f"    Claude'a soruluyor ({MODEL}, {'API' if which == 'api' else 'claude CLI'}) …")
    try:
        out = ask(build_prompt(meta, ana, singles, tuning), groups)
    except (ClaudeError, json.JSONDecodeError, OSError) as e:
        log.warning("Claude mode failed (%s); using the engine's patches", e)
        return singles, {"enabled": True, "ok": False, "backend": which, "model": MODEL, "error": str(e)}
    refined = dict(singles)
    for r in out.get("patches", []):
        gname = r.get("group")
        if gname in singles:
            try:
                refined[gname] = apply_recipe(singles[gname], r, ana.groups[gname])
            except (KeyError, ValueError, TypeError) as e:
                log.warning("Claude recipe for %s not applied (%s)", gname, e)
    info = {"enabled": True, "ok": True, "backend": which, "model": MODEL, "song": out.get("song", ""),
            "rig_notes": out.get("rig_notes", ""),
            "applied": [g for g in groups if refined[g] is not singles[g]]}
    return refined, info
