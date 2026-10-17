"""Build src/tonematch/device/gt1/data/gt1_spec.json from a BOSS TONE STUDIO for GT-1 install.

The spec is the single source of truth for addresses, write blocks and parameter ranges/options.
It is generated, not hand-written, because BTS already encodes everything we need:

  * _assets/data/addressmap_gt.json           -> model id, regions, command addresses
  * TemporaryParams.as  (decompiled SWF)        -> field name <-> temp-area address (receive path)
  * ParameterDefinitionGT.as (decompiled SWF)   -> min/max/step, enum option lists

Decompile once with JPEXS FFDec:
    java -jar ffdec-cli.jar -export script <out> "<BTS>/BOSS_TONE_STUDIO_for_GT1.swf"

Usage:
    python tools/build_gt1_spec.py <ffdec_out>/scripts [--bts "C:/Program Files (x86)/BOSS TONE STUDIO for GT-1"]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BS = chr(92)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "tonematch" / "device" / "gt1" / "data" / "gt1_spec.json"

# BTS write blocks for the temporary patch (SystemExclusive.as:353-425, temporaryDecimalPatchSize).
# (address bytes 3-4 as "hh,ll", byte count). 24 messages, 1423 data bytes.
BLOCKS = [("00,00", 64), ("00,50", 48), ("01,00", 64), ("01,40", 64), ("02,00", 65), ("02,41", 63),
          ("03,00", 64), ("03,40", 64), ("04,00", 64), ("04,41", 63), ("05,01", 63), ("05,40", 64),
          ("06,00", 64), ("06,40", 64), ("07,00", 64), ("07,40", 64), ("08,00", 64), ("08,50", 48),
          ("09,10", 48), ("09,50", 48), ("0A,10", 33), ("10,10", 64), ("10,50", 48), ("11,00", 64)]

# enum constant -> field ids it describes
TYPE_CONSTS = {
    "COMP_TYPE": ["comp_type"],
    "ODDS_TYPE": ["od_ds_type"],
    "PREAMP_TYPE": ["preamp_a_type", "preamp_b_type"],
    "FX1_TYPE": ["fx1_fx_type"],
    "FX2_TYPE": ["fx2_fx_type"],
    "DELAY_TYPE": ["delay_type"],
    "CHORUS_TYPE": ["chorus_mode"],
    "REVERB_TYPE": ["reverb_type"],
    "PEDAL_FX_TYPE": ["pedal_fx_type"],
    "ACCEL_FX_TYPE": ["accel_fx_type"],
}
OUTPUT_SELECT = ["JC-120", "SMALL AMP", "COMBO AMP", "STACK AMP",
                 "JC-120 RETURN", "COMBO RETURN", "STACK RETURN", "LINE/PHONES"]


def parse_as3_consts(src: str) -> dict:
    """Parse `public static const X:T = <literal>;` blocks that are (almost) JSON."""
    gen = {
        "createReverbTimeList()": json.dumps([f"{k / 10:.1f}s" for k in range(1, 101)]),
        "createNSThresholdList()": json.dumps(["OFF"] + [str(k) for k in range(1, 101)]),
        "createChorusPreDelayList()": json.dumps([f"{k * 5 / 10:.1f}ms" for k in range(81)]),
        "createMixerChBalanceList()": "null",
    }
    out = {}
    for m in re.finditer(r"public static const (\w+):(\w+) = ", src):
        i = j = m.end()
        depth, instr = 0, False
        while j < len(src):
            c = src[j]
            if instr:
                if c == BS:
                    j += 2
                    continue
                instr = c != '"'
            elif c == '"':
                instr = True
            elif c in "[{(":
                depth += 1
            elif c in "]})":
                depth -= 1
            elif c == ";" and depth == 0:
                break
            j += 1
        lit = src[i:j].replace(BS + "'", "'")
        for k, v in gen.items():
            lit = lit.replace(k, v)
        lit = re.sub(r'(?<=[:\[,])\s*([A-Z][A-Z0-9_]+)\s*(?=[,}\]])', r'"@\1"', lit)
        try:
            out[m.group(1)] = json.loads(lit)
        except json.JSONDecodeError:
            pass
    return out


def parse_temp_fields(tp_src: str) -> dict[int, str]:
    """TemporaryParams.setData(): `if(param1 == N) { this.field = param2; }` -> {N: field}.

    N = addr[2]*256 + addr[3] of the 60,00,xx,yy temp area.
    """
    lines = tp_src.split("\n")
    s = next(i for i, ln in enumerate(lines) if re.search(r"function setData\(", ln))
    e = next(i for i in range(s + 1, len(lines)) if re.match(r"\s*(public|private|protected) function", lines[i]))
    fields: dict[int, str] = {}
    cur = None
    for ln in lines[s:e]:
        mm = re.search(r"if\(param1 == (\d+)\)", ln)
        if mm:
            cur = int(mm.group(1))
            continue
        mm = re.search(r"this\.([A-Za-z0-9_]+) = param2;", ln)
        if mm and cur is not None:
            fields.setdefault(cur, mm.group(1))
            cur = None
    return fields


def collect_defs(c: dict) -> dict[str, dict]:
    defs: dict[str, dict] = {}

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and "min" in o and "max" in o:
                d = defs.setdefault(o["id"], {})
                d.update({k: o[k] for k in ("min", "max", "step", "name") if k in o})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for name, val in c.items():
        if name.endswith("_PARAMS_LIST") or name == "STEPPER_AND_DROPDOWN_LIST":
            walk(val)
    for name, val in c.get("STEPPER_AND_DROPDOWN_LIST", {}).items():
        d = defs.setdefault(name, {})
        d.update({k: val[k] for k in ("min", "max", "step") if k in val})
        dd = val.get("dropdown")
        if isinstance(dd, str) and dd.startswith("@") and isinstance(c.get(dd[1:]), list):
            d["dropdown"] = {str(x["val"]): x["name"] for x in c[dd[1:]] if x.get("val", 0) > 0}

    def set_options(fid: str, names: list[str]):
        d = defs.setdefault(fid, {})
        d["options"] = names
        d.setdefault("min", 0)
        d.setdefault("max", len(names) - 1)
        d.setdefault("step", 1)

    for const, ids in TYPE_CONSTS.items():
        if const in c:
            names = [x["name"] for x in sorted(c[const], key=lambda x: x["val"])]
            for fid in ids:
                set_options(fid, names)
    for fid, opts in c.get("DROPDOWN_LIST", {}).items():
        if isinstance(opts, list):
            set_options(fid, opts)
    # FX sub types: FX1_SUB_TYPE_LIST["PHASER"] -> fx1_phaser_type, etc.
    sub_map = {"PHASER": "phaser_type", "SUB WAH": "sub_wah_type", "COMPRESSOR": "adv_comp_type",
               "LIMITER": "limiter_type", "SUB OD/DS": "sub_od_ds_type", "TONEMODIFY": "tone_modify_type",
               "GTRSIM": "guitar_sim_type", "AC_PROC": "ac_processor_type", "PAN": "pan_type",
               "SUBDELAY": "sub_delay_type"}
    for fx in ("FX1", "FX2"):
        for k, v in c.get(f"{fx}_SUB_TYPE_LIST", {}).items():
            if k in sub_map and isinstance(v, list):
                set_options(f"{fx.lower()}_{sub_map[k]}", [x["name"] for x in sorted(v, key=lambda x: x["val"])])
    if "ODDS_SUB_TYPE_LIST" in c:
        set_options("od_ds_custom_type", [x["name"] for x in c["ODDS_SUB_TYPE_LIST"]["CUSTOM"]])
    if "PREAMP_SUB_TYPE_LIST" in c:
        for p in ("preamp_a", "preamp_b"):
            set_options(f"{p}_custom_type", [x["name"] for x in c["PREAMP_SUB_TYPE_LIST"]["CUSTOM"]])
    set_options("output_select", OUTPUT_SELECT)
    return defs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", type=Path, help="FFDec export dir containing tonecentral/...")
    ap.add_argument("--bts", type=Path, default=Path(r"C:/Program Files (x86)/BOSS TONE STUDIO for GT-1"))
    a = ap.parse_args()

    amap = json.loads((a.bts / "_assets/data/addressmap_gt.json").read_text(encoding="utf-8"))
    tp_src = (a.scripts / "tonecentral/parametors/TemporaryParams.as").read_text(encoding="utf-8")
    pd_src = (a.scripts / "tonecentral/common/define/ParameterDefinitionGT.as").read_text(encoding="utf-8")

    fields = parse_temp_fields(tp_src)
    consts = parse_as3_consts(pd_src)
    defs = collect_defs(consts)
    # ASSIGN targets: name -> target id (assignN_target = h*128+l, "val" = "hh,ll") and value range
    at_src = (a.scripts / "tonecentral/common/define/CTLAssignTargetDefinitionGT.as").read_text(encoding="utf-8")
    at = parse_as3_consts(at_src).get("ASSIGN_TARGET_MASTER_LIST", [])
    assign_targets = {}
    for t in at:
        if isinstance(t, dict) and isinstance(t.get("val"), str) and "," in t["val"]:
            h, l = (int(x, 16) for x in t["val"].split(","))
            assign_targets[t["name"]] = {"id": h * 128 + l, "min": t.get("min", 0), "max": t.get("max", 127)}
    commands = {e["name"]: e["address"] for e in amap["command"]}
    system = {e["name"]: e["address"] for e in amap["system"] if "name" in e}

    spec = {
        "_generated_by": "tools/build_gt1_spec.py",
        "model_id": [int(x, 16) for x in amap["id"]["model_id_gt001"].split(",")],
        "temp_top": [0x60, 0x00],
        "user_top": [0x10],
        "preset_top": [0x20],
        "blocks": [[b, n] for b, n in BLOCKS],
        "fields": {f: f"{n >> 8:02X},{n & 0xFF:02X}" for n, f in sorted(fields.items())},
        "defs": {k: defs[k] for k in sorted(defs)},
        "commands": commands,
        "system": {k: system[k] for k in ("PREFERENCE: OUTPUT SELECT", "PREFERENCE: PREAMP", "OUTPUT SELECT",
                                          "INPUT LEVEL") if k in system},
        "setup": {e["name"]: e["address"] for e in amap["setup"]},
        "patch_categories": consts.get("PATCH_CATEGORY", []),
        "assign_targets": assign_targets,
        # CTLDefinitionGT.as: ASSIGN_SOURCE_LIST / ASSIGN_SOURCE_MODE_LIST / CONTROL_FUNC1
        "assign_sources": {"EXP1": 0, "CTL1": 1, "EXP2": 2, "CTL2": 3, "CTL3": 4, "INT PEDAL": 5, "WAVE PEDAL": 6},
        "assign_source_modes": {"MOMENT": 0, "TOGGLE": 1},
        "ctl_functions": ["OFF", "OD SOLO", "PREAMP SOLO", "FX1", "OD/DS", "PREAMP", "FX2", "DELAY", "REVERB",
                          "PEDAL FX", "TUNER", "BPM TAP", "DELAY TAP", "LEVEL +10", "LEVEL +20", "LEVEL -10",
                          "LEVEL -20", "NUMBER +1", "NUMBER -1", "LED ON/OFF"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} fields={len(spec['fields'])} defs={len(spec['defs'])}")


if __name__ == "__main__":
    main()
