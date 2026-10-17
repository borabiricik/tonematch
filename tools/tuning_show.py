"""Dev tool: print cached tuning features of one track.  uv run python tools/tuning_show.py <track_id>"""

import json
import sys

from tonematch.config import DATA_DIR
from tonematch.tuning import FMIN_MIDI, midi_name

f = json.loads((DATA_DIR / "tuning_features.json").read_text(encoding="utf-8"))[sys.argv[1]]
print(f["title"], f["cents"], f["tonic"], f["mode"])
for i in range(0, 32):
    print(f"{midi_name(i + FMIN_MIDI):4s} low {f['low_share'][i]:.3f}  sal {f['salience'][i]:.2f}")
