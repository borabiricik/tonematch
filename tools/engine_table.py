"""Dev tool: run the tone engine on every cached track and print the chosen model/knobs."""

import json

from tonematch.config import TRACKS_DIR
from tonematch.match import build_patch
from tonematch.pipeline import _load_or_analyze

for d in sorted(TRACKS_DIR.iterdir()):
    if not (d / "stems" / "guitar.wav").exists():
        continue
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    ana = _load_or_analyze(d, {"guitar": d / "stems" / "guitar.wav"}, d / "source.wav")
    for n, g in ana.groups.items():
        m = build_patch(n, g, ana.tempo, meta)
        s = m.patch.summary()
        fx = [x for x, on in (("OD:" + str(s["od_ds_type"]), s["od_ds_on_off"]), ("NS", s["ns1_on_off"]),
                              (f"DLY{s['delay_delay_time']}", s["delay_on_off"]),
                              (f"REV:{s['reverb_type']}", s["reverb_on_off"]), ("COMP", s["fx1_on_off"])) if on]
        print(f"{meta.get('title', '')[:20]:20s} {n:6s} {s['preamp_a_type']:15s} G{s['preamp_a_gain']:3d} "
              f"B{s['preamp_a_bass']:3d} M{s['preamp_a_middle']:3d} T{s['preamp_a_treble']:3d} P{s['preamp_a_presence']:3d} "
              f"EQ{s['master_eq_low_gain']:+d}/{s['master_eq_mid_gain']:+d}/{s['master_eq_high_gain']:+d} {' '.join(fx)} "
              f"| {list(m.scores)[:3]}  [{m.patch.name}]")
