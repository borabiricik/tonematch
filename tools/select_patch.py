"""Dev tool: select a user patch on the GT-1 the way BTS does (write setup current_patch_no).

uv run python tools/select_patch.py U10
"""

import sys
import time

from tonematch.device.gt1.client import connect, parse_slot

slot = parse_slot(sys.argv[1])
with connect() as g:
    print("current before:", g.current_patch_number(), g.read_patch().name)
    g.write([0x00, 0x01, 0x00, 0x00], [slot // 128, slot % 128])
    for t in (0.3, 1.0, 2.0):
        time.sleep(t)
        print(f"+{t}s current:", g.current_patch_number(), "edit buffer:", g.read_patch().name)
with connect() as g:
    print("after reconnect:", g.current_patch_number(), g.read_patch().name)
