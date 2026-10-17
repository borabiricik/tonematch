"""Dev tool: load each patch of a .tsl into the GT-1 edit buffer, read it back, compare; restore the buffer.

Never saves to a user slot.  uv run python tools/temp_roundtrip.py output/<file>.tsl
"""

import sys
import time

from tonematch.device.gt1.client import connect
from tonematch.device.gt1.patch import read_tsl

patches = read_tsl(sys.argv[1])
with connect() as g:
    original = g.read_patch()
    try:
        for p in patches:
            g.write_temp(p)
            time.sleep(0.2)
            back = g.read_patch()
            diff = [f for f, v in p.params.items() if back.params.get(f, 0) != v and not f.startswith("eq_")]
            print(f"{p.name:16s} written+read back, mismatching fields: {len(diff)} {diff[:8]}")
    finally:
        g.write_temp(original)
        print("edit buffer restored:", g.read_patch().name)
