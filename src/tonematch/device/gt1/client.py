"""High-level GT-1 client: connect, read/write the edit buffer, save to user slots, backups.

Protocol facts come from the decompiled BOSS TONE STUDIO (see docs/06-gt1-protocol-extracted.md):
  * identity request -> device id = reply[2]
  * editor mode on:  DT1 7F,00,00,01 = 01 (then ~100 ms)   off: 7F,00,06,00 = 01 ; 7F,00,00,01 = 00
  * patch = 24 DT1 blocks, 30 ms apart; same layout in temp (60,00,..) and user slot i (10,i,..)
  * save edit buffer to slot i: DT1 7F,00,01,04 = [i // 128, i % 128]
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

import mido

from .patch import Patch
from .spec import GT1Spec, load_spec
from .sysex import IDENTITY_REQUEST, dt1, parse_dt1, rq1

log = logging.getLogger(__name__)

# The "EQ" area (60,00,01,30-3B) exists in BTS' shared address map but the GT-1 has no such block:
# the device ignores writes there (verified 2026-10-17). Tone EQ lives in MASTER EQ instead.
IGNORED_PREFIXES = ("eq_",)

MSG_GAP_S = 0.030
READ_TIMEOUT_S = 3.0
RETRIES = 3


class GT1Error(RuntimeError):
    pass


def bts_running() -> bool:
    """True if BOSS TONE STUDIO for GT-1 is running (Windows: tasklist, macOS/Linux: ps)."""
    import subprocess
    import sys

    cmd = (["tasklist", "/FI", "IMAGENAME eq BOSS TONE STUDIO for GT-1.exe", "/NH"] if sys.platform == "win32"
           else ["ps", "-axo", "comm="])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "BOSS TONE STUDIO" in out


def find_ports(hint: str = "GT-1") -> tuple[str, str]:
    ins = [n for n in mido.get_input_names() if hint.lower() in n.lower()]
    outs = [n for n in mido.get_output_names() if hint.lower() in n.lower()]
    if not ins or not outs:
        raise GT1Error(
            f"GT-1 MIDI port not found (inputs={mido.get_input_names()}, outputs={mido.get_output_names()}). "
            "Is the GT-1 connected via USB and BOSS TONE STUDIO closed?")
    return ins[0], outs[0]


class GT1Client:
    def __init__(self, spec: GT1Spec | None = None, port_hint: str = "GT-1"):
        self.spec = spec or load_spec()
        self.port_hint = port_hint
        self.inp = self.out = None
        self.dev = 0x00
        self.identity: list[int] = []

    # -- connection -------------------------------------------------------------------------------
    def open(self) -> "GT1Client":
        if bts_running():
            # Two editors on the device at once confused the GT-1 (stuck "BULK DATA RECEIVING", 2026-10-17)
            raise GT1Error("BOSS TONE STUDIO açık. Cihazla aynı anda iki editör konuşamaz; BTS'i kapatıp tekrar dene.")
        in_name, out_name = find_ports(self.port_hint)
        try:
            self.inp = mido.open_input(in_name)
            self.out = mido.open_output(out_name)
        except Exception as e:  # port busy (BTS open) etc.
            raise GT1Error(f"cannot open GT-1 MIDI ports ({e}). Close BOSS TONE STUDIO and retry.") from e
        self._drain()
        self._send(IDENTITY_REQUEST)
        reply = self._wait(lambda m: len(m) > 6 and m[1] == 0x7E and m[3] == 0x06 and m[4] == 0x02, 2.0)
        if reply is None:
            raise GT1Error("GT-1 did not answer the identity request")
        self.identity = reply
        self.dev = reply[2]
        if reply[5] != 0x41:
            raise GT1Error(f"identity reply is not from Roland/BOSS: {bytes(reply).hex(' ')}")
        self.write(self.spec.commands["editor_comunication_mode"], [0x01])
        time.sleep(0.5)  # let a previous session's patch load / flash write settle
        log.info("GT-1 connected (device id %02X)", self.dev)
        return self

    def close(self) -> None:
        if self.out is not None:
            try:
                self.write(self.spec.commands["usb_direct_mon"], [0x01])
                self.write(self.spec.commands["editor_comunication_mode"], [0x00])
            finally:
                self.out.close()
                self.inp.close()
                self.out = self.inp = None

    def __enter__(self) -> "GT1Client":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # -- low level --------------------------------------------------------------------------------
    def _send(self, raw: bytes, gap: bool = True) -> None:
        """gap: pause after writes so the device keeps up; a read request waits for its reply instead."""
        self.out.send(mido.Message("sysex", data=list(raw[1:-1])))
        if gap:
            time.sleep(MSG_GAP_S)

    def _drain(self) -> None:
        for _ in self.inp.iter_pending():
            pass

    def _wait(self, pred, timeout: float) -> list[int] | None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for m in self.inp.iter_pending():
                if m.type == "sysex":
                    full = [0xF0, *m.data, 0xF7]
                    if pred(full):
                        return full
            time.sleep(0.002)
        return None

    def write(self, addr: list[int], data: list[int]) -> None:
        self._send(dt1(self.dev, self.spec.model_id, addr, data))

    def read(self, addr: list[int], size: int, allow_short: bool = False) -> list[int]:
        """RQ1 and collect DT1 replies until `size` bytes starting at addr have arrived.

        allow_short: the device stops at the end of a memory area (e.g. the last patch block is
        26 bytes, not the 64 BTS requests); accept a contiguous prefix once replies go quiet.
        """
        for attempt in range(RETRIES):
            self._drain()
            self._send(rq1(self.dev, self.spec.model_id, addr, size), gap=False)
            got: dict[int, int] = {}
            base = _a2i(addr)
            end = time.monotonic() + READ_TIMEOUT_S
            last_rx = None
            while time.monotonic() < end and len(got) < size:
                if allow_short and last_rx and time.monotonic() - last_rx > 0.25:
                    break
                for m in self.inp.iter_pending():
                    if m.type != "sysex":
                        continue
                    r = parse_dt1([0xF0, *m.data, 0xF7], self.spec.model_id)
                    if r is None:
                        continue
                    a, data = r
                    start = _a2i(a)
                    last_rx = time.monotonic()
                    for i, v in enumerate(data):
                        if 0 <= start + i - base < size:
                            got[start + i - base] = v
                time.sleep(0.002)
            if len(got) == size:
                return [got[i] for i in range(size)]
            if allow_short and got and sorted(got) == list(range(len(got))):
                return [got[i] for i in range(len(got))] + [0] * (size - len(got))
            log.warning("read %s size %d: got %d bytes (attempt %d)", addr, size, len(got), attempt + 1)
        raise GT1Error(f"read timeout at {bytes(addr).hex(',')}")

    # -- patches ----------------------------------------------------------------------------------
    def read_patch(self, slot: int | None = None) -> Patch:
        """slot None = edit buffer (temporary patch), else 0-based user slot."""
        area = self.spec.temp_area() if slot is None else self.spec.user_area(slot)
        blocks = [self.read(a, b.size, allow_short=True) for b, a in self.spec.block_addrs(area)]
        return Patch.from_block_bytes(blocks, self.spec)

    def patch_summary(self, slot: int | None = None) -> dict:
        """Name, amp model and gain from ONE small read (~25 ms) instead of the whole patch (~2 s).
        Patch name sits at 00,00-0F and PREAMP A type/gain at 00,51-52 of the patch area."""
        area = self.spec.temp_area() if slot is None else self.spec.user_area(slot)
        d = self.read([*area, 0x00, 0x00], 0x53)
        types = self.spec.options("preamp_a_type")
        return {"name": bytes(d[:16]).decode("ascii", "replace"),
                "amp": types[d[0x51]] if d[0x51] < len(types) else "?", "gain": d[0x52]}

    def write_temp(self, patch: Patch) -> None:
        for (b, addr), data in zip(self.spec.block_addrs(self.spec.temp_area()), patch.block_bytes()):
            self.write(addr, data)

    def save_temp_to_slot(self, slot: int) -> None:
        self.spec.user_area(slot)  # validates range
        self._drain()
        self.write(self.spec.commands["patch_write"], [slot // 128, slot % 128])
        time.sleep(0.5)  # device stores to flash

    def store_patch(self, patch: Patch, slot: int, verify: bool = True) -> None:
        """Load patch into the edit buffer, save it to user slot, verify by reading the slot back.

        The edit buffer is read back BEFORE saving: once the device saved another buffer than ours
        (U99 got the U96 patch, 2026-10-17), so never issue the save unless the buffer is ours.
        """
        for attempt in range(3):
            self.write_temp(patch)
            time.sleep(0.3 + attempt)
            buf = self.read_patch()
            bad = self._diff(patch, buf)
            if not bad:
                break
            log.warning("edit buffer mismatch before save (attempt %d): %s", attempt + 1, bad[:6])
        else:
            raise GT1Error(f"edit buffer does not hold the new patch ({bad[:6]}); {slot_label(slot)} NOT saved")
        self.save_temp_to_slot(slot)
        if verify:
            diffs: list[str] = []
            for attempt in range(3):  # right after a save the flash write may not be finished yet
                if attempt:
                    time.sleep(1.5)
                diffs = self._diff(patch, self.read_patch(slot))
                if not diffs:
                    break
            if diffs:
                raise GT1Error(f"slot U{slot + 1:02d} verify failed for {len(diffs)} fields: {diffs[:10]}")

    def _diff(self, want: Patch, got: Patch) -> list[str]:
        return [f for f, v in want.params.items() if f in self.spec.field_off and not f.startswith(IGNORED_PREFIXES)
                and not _inaudible(want, f) and got.params.get(f, 0) != v]

    def select_patch(self, slot: int) -> None:
        """Switch the GT-1 to user slot (loads it into the edit buffer). Program Change is ignored
        while editor mode is on, so do it the BTS way: write setup current_patch_no."""
        self.spec.user_area(slot)
        self.write([0x00, 0x01, 0x00, 0x00], [slot // 128, slot % 128])
        time.sleep(0.3)

    def current_patch_number(self) -> int:
        hi, lo = self.read([0x00, 0x01, 0x00, 0x00], 2)
        return hi * 128 + lo

    def read_system(self, name: str) -> int:
        return self.read(self.spec.system[name], 1)[0]


# FX type -> field-name fragment of its parameters (for the types tonematch uses)
FX_TYPE_KEYS = {"COMPRESSOR": "adv_comp", "CHORUS": "chorus", "PHASER": "phaser", "FLANGER": "flanger",
                "TREMOLO": "tremolo", "ROTARY": "rotary", "UNI_V": "uni_v", "VIBRATO": "vibrato",
                "PEQ": "parametric_eq", "GEQ": "graphic_eq", "LIMITER": "limiter", "TWAH": "t_wah"}


def _inaudible(p: Patch, f: str) -> bool:
    """Fields the device may normalise on its own without any audible effect: parameters of a block
    that is off, or of an FX sub-type that is not the selected one (verified: fx2_tremolo_depth)."""
    for blk in ("fx1", "fx2"):
        if f.startswith(blk + "_") and f not in (f"{blk}_on_off", f"{blk}_fx_type"):
            if not p.get_raw(f"{blk}_on_off"):
                return True
            key = FX_TYPE_KEYS.get(str(p.get(f"{blk}_fx_type")))
            return key is not None and not f.startswith(f"{blk}_{key}")
    return False


def _a2i(a: list[int]) -> int:
    v = 0
    for b in a:
        v = (v << 7) | b
    return v


@contextmanager
def connect(port_hint: str = "GT-1"):
    c = GT1Client(port_hint=port_hint)
    c.open()
    try:
        yield c
    finally:
        c.close()


def slot_label(slot: int) -> str:
    return f"U{slot + 1:02d}"


def parse_slot(text: str | int) -> int:
    """'U05', '5', 5 -> 4 (0-based)."""
    s = str(text).strip().upper().lstrip("U")
    n = int(s)
    if not 1 <= n <= 99:
        raise ValueError("slot must be U01..U99")
    return n - 1
