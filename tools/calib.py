"""Dev tool: print analysis windows/groups for cached tracks (used to calibrate analysis.py).

uv run python tools/calib.py <track_id> [<track_id> ...] [-v] [--from 3:20 --to 5:50]
"""

import json
import sys

from tonematch.analysis import analyze
from tonematch.config import TRACKS_DIR


def secs(s: str) -> float:
    m, _, x = s.partition(":")
    return int(m) * 60 + float(x) if x else float(m)


args = sys.argv[1:]
verbose = "-v" in args
t_from = secs(args[args.index("--from") + 1]) if "--from" in args else 0
t_to = secs(args[args.index("--to") + 1]) if "--to" in args else 1e9
ids = [a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] not in ("--from", "--to"))]
for tid in ids:
    d = TRACKS_DIR / tid
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    a = analyze(d / "stems" / "guitar.wav", d / "source.wav")
    print(f"### {tid} {meta['video_title']} tempo {a.tempo}")
    for w in a.windows if verbose else []:
        if not w["active"] or not t_from <= w["start"] <= t_to:
            continue
        print(f"{int(w['start'])//60}:{int(w['start'])%60:02d} L{w['label']} g{w['gain']:.2f} fm{w['flat_mid']:.3f} "
              f"su{w['sustain']:.2f} cr{w['crest_db']:4.1f} hf{w['hf_ratio_db']:5.1f} "
              f"w{w['width']:.2f} cr{w['c_ratio']:.2f} cp{w['c_per']:.2f} cf{w['c_f0']:4.0f}")
    for g, p in a.groups.items():
        print("GROUP", g, p.seconds, p.gain, p.gain_class, p.stereo, p.segments[:5], p.bands_db,
              "delay", p.delay, "rev", p.reverb)
