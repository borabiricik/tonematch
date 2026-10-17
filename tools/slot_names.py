"""Dev tool (read-only): current patch, edit buffer and the names of a slot range.

uv run python tools/slot_names.py U94 U99
"""

import sys

from tonematch.device.gt1.client import connect, parse_slot, slot_label

a, b = parse_slot(sys.argv[1]), parse_slot(sys.argv[2])
with connect() as g:
    print("current:", slot_label(g.current_patch_number()), "| edit buffer:", g.read_patch().name)
    for s in range(a, b + 1):
        p = g.read_patch(s)
        print(slot_label(s), f"{p.name:16s}", p.get("preamp_a_type"), p.get("preamp_a_gain"))
