"""Dev tool: run tuning detection on every cached track (optionally only some ids)."""

import json
import sys
import time

from tonematch.config import TRACKS_DIR
from tonematch.tuning import detect_tuning

ids = set(sys.argv[1:])
for d in sorted(TRACKS_DIR.iterdir()):
    if not (d / "stems" / "guitar.wav").exists() or (ids and d.name not in ids):
        continue
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    t = time.time()
    e = detect_tuning(d / "stems" / "guitar.wav", d / "source.wav")
    print(f"{meta.get('title', '')[:26]:26s} -> {e.name:12s} {e.user_tuning} {e.semitones:+d} st {e.cents:+d}c "
          f"conf {e.confidence:.2f} key {e.key:9s} low {e.lowest_note:4s} {round(time.time() - t)}s | {e.scores}",
          flush=True)
