"""Dev tool: tuning calibration.

  uv run python tools/tuning_evidence.py --extract   # (slow) features for all cached tracks -> JSON
  uv run python tools/tuning_evidence.py             # (fast) score with tuning.score_tunings vs known truth
"""

import json
import sys

from tonematch.config import DATA_DIR, TRACKS_DIR
from tonematch.tuning import FMIN_MIDI, extract_features, midi_name, score_tunings

CACHE = DATA_DIR / "tuning_features.json"
# known tunings of the calibration recordings (well documented)
TRUTH = {
    "zbSjDVcZA2o": "E standard",   # Master of Puppets
    "ozXZnwYTMbs": "E standard",   # Nothing Else Matters
    "pAgnJDJN4VA": "E standard",   # Back in Black
    "XZuM4zFg-60": "E standard",   # Enter Sandman
    "qK7j_EERgT4": "E standard",   # Smoke on the Water
    "I3MTGhRC82s": "Eb standard",  # Pride and Joy
    "D2gWc5Sw75w": "Eb standard",  # Sweet Child O' Mine
    "JYJ6QJqy92s": "Drop D",       # Killing in the Name
    "GK-DkHHAMIU": "Drop C",       # Chop Suey
    "3GWwohI5h1w": "Drop B",       # Duality
}

if "--extract" in sys.argv:
    feats = {}
    for d in sorted(TRACKS_DIR.iterdir()):
        if (d / "stems" / "guitar.wav").exists():
            f = extract_features(d / "stems" / "guitar.wav", d / "source.wav", d / "stems" / "bass.wav")
            f["title"] = json.loads((d / "meta.json").read_text(encoding="utf-8")).get("title")
            feats[d.name] = f
            print("extracted", d.name, f["title"], flush=True)
    CACHE.write_text(json.dumps(feats), encoding="utf-8")

feats = json.loads(CACHE.read_text(encoding="utf-8"))
ok = n = 0
for tid, f in feats.items():
    e = score_tunings(f)
    t = TRUTH.get(tid)
    mark = "" if t is None else ("OK " if e.name == t else "XX ")
    ok += t is not None and e.name == t
    n += t is not None
    low = " ".join(f"{midi_name(i + FMIN_MIDI)}:{v:.2f}" for i, v in enumerate(f["low_share"]) if v >= 0.05)
    print(f"{mark:3s}{f['title'][:22]:22s} -> {e.name:12s} (truth {t or '?':11s}) conf {e.confidence:.2f} "
          f"key {e.key:8s} {f['cents']:+d}c | low {low} | {list(e.scores.items())[:3]}")
print(f"\n{ok}/{n} correct on known tunings")
