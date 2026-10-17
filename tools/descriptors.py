"""Dev tool: (re)analyse all cached tracks and print per-group descriptors (calibration table for match.py)."""

import json

from tonematch.config import TRACKS_DIR
from tonematch.pipeline import _load_or_analyze

for d in sorted(TRACKS_DIR.iterdir()):
    if not (d / "stems" / "guitar.wav").exists():
        continue
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    ana = _load_or_analyze(d, {"guitar": d / "stems" / "guitar.wav"}, d / "source.wav")
    for n, g in ana.groups.items():
        de = g.descriptors
        print(f"{meta.get('title', '')[:24]:24s} {n:7s} s{g.seconds:5.0f} gain{g.gain:5.2f} flat{g.flatness:6.3f} "
              f"su{g.sustain:5.2f} cr{g.crest_db:5.1f} w{g.width:5.2f} per{g.periodicity:5.2f} f0{g.f0_median:5.0f} "
              f"low{de['low_depth_db']:6.1f} mid{de['mid_scoop_db']:6.1f} pres{de['presence_db']:6.1f} "
              f"fizz{de['fizz_db']:6.1f} body{de['body_db']:6.1f} rev:{g.reverb.amount} dly:{g.delay.time_ms if g.delay.detected or g.delay.possible else '-'}")
