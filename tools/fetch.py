"""Dev tool: download + separate a list of sources (for calibration sets).  uv run python tools/fetch.py "<src>" ..."""

import sys

from tonematch.ingest import ingest, track_dir
from tonematch.separate import separate

for src in sys.argv[1:]:
    try:
        tid, wav, meta = ingest(src)
        separate(wav, track_dir(tid))
        print("OK", tid, meta.get("title"), flush=True)
    except Exception as e:  # keep going with the rest of the list
        print("FAIL", src, e, flush=True)
