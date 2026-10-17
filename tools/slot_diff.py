"""Dev tool: compare a .tsl patch with what a user slot holds.  uv run python tools/slot_diff.py <tsl> <index> U98"""

import sys

from tonematch.device.gt1.client import connect, parse_slot
from tonematch.device.gt1.patch import read_tsl

p = read_tsl(sys.argv[1])[int(sys.argv[2]) - 1]
with connect() as g:
    b = g.read_patch(parse_slot(sys.argv[3]))
print("slot name:", b.name, "| tsl name:", p.name)
for f, v in p.params.items():
    if b.params.get(f, 0) != v and not f.startswith("eq_"):
        print(f"{f:24s} tsl {v} slot {b.params.get(f)}  ({p.get(f)} vs {b.get(f)})")
print("preamp type:", p.get("preamp_a_type"), "gain_sw:", p.get("preamp_a_gain_sw"))
