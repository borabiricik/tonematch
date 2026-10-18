"""GT-1 tuner, the BOSS TONE STUDIO way (decompiled `Tuner.as`, `SystemExclusive.as:1210-1240`).

  * on:  DT1 running_mode (7F,00,00,02) = 01 (single) or 02 (multi / polyphonic);  off: = 00
  * while on, the unit pushes DT1s by itself (editor mode must be on, GT1Client.open does that):
      tuner_single_mode_pitch       7F,00,05,00       [note, cents + 50]
      tuner_multi_mode_str_N_pitch  7F,00,02,00..0A   [note, cents + 50] per string (1 = high E)
    note 0..11 = C..B, 0x0C = no signal. cents -50..+50.
  * the unit also pushes running_mode when the player leaves the tuner on the unit itself.

The reference pitch (A=435..445) and tuner output (MUTE/BYPASS/THRU) are SYSTEM settings: not touched here.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .sysex import parse_dt1

NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
NO_SIGNAL = 0x0C
MODES = {"single": 1, "multi": 2}
IN_TUNE_CENTS = 3  # BTS lights both arrows within +-3 cents (single); the multi meter snaps 45..55 to center


@dataclass(frozen=True)
class Reading:
    note: str | None   # None = no signal
    cents: int         # -50..+50, 0 when no signal

    @property
    def in_tune(self) -> bool:
        return self.note is not None and abs(self.cents) <= IN_TUNE_CENTS


def decode_pitch(data: list[int]) -> Reading:
    """[note, cents+50] -> Reading."""
    if len(data) < 2 or data[0] >= NO_SIGNAL:
        return Reading(None, 0)
    return Reading(NOTES[data[0]], max(-50, min(50, data[1] - 50)))


class Tuner:
    """Decodes the unit's tuner pushes. feed() takes one raw SysEx message and returns an event dict or None:
    {"kind": "single", "note", "cents", "in_tune"} | {"kind": "multi", "string": 1..6, ...} | {"kind": "mode", "mode"}."""

    def __init__(self, spec):
        c = spec.commands
        self.model_id = spec.model_id
        self.single = c["tuner_single_mode_pitch"]
        self.running = c["running_mode"]
        self.strings = {tuple(c[f"tuner_multi_mode_str_{n}_pitch"]): n for n in range(1, 7)}

    def feed(self, msg: list[int]) -> dict | None:
        r = parse_dt1(msg, self.model_id)
        if r is None:
            return None
        addr, data = r
        if addr == self.single:
            return {"kind": "single", **_reading_dict(decode_pitch(data))}
        if tuple(addr) in self.strings:
            return {"kind": "multi", "string": self.strings[tuple(addr)], **_reading_dict(decode_pitch(data))}
        if addr == self.running and data:
            return {"kind": "mode", "mode": next((k for k, v in MODES.items() if v == data[0]), "off")}
        return None


def _reading_dict(r: Reading) -> dict:
    return {**asdict(r), "in_tune": r.in_tune}


def run_tuner(client, mode: str, on_event, should_stop) -> str:
    """Put the unit in tuner mode, call on_event(dict) for every pitch change until should_stop() or the
    player leaves the tuner on the unit; always switches the unit back to play mode. Returns the reason."""
    tuner = Tuner(client.spec)
    client._drain()
    client.write(client.spec.commands["running_mode"], [MODES[mode]])
    last: dict = {}
    left_on_device = False
    try:
        while not left_on_device and not should_stop():
            for m in client.inp.iter_pending():
                if m.type != "sysex":
                    continue
                ev = tuner.feed([0xF0, *m.data, 0xF7])
                if ev is None:
                    continue
                if ev["kind"] == "mode":
                    left_on_device = ev["mode"] == "off"
                    continue
                key = (ev["kind"], ev.get("string"))
                if last.get(key) != ev:  # the unit repeats identical readings; pass on changes only
                    last[key] = ev
                    on_event(ev)
            time.sleep(0.005)
    finally:
        if not left_on_device:
            client.write(client.spec.commands["running_mode"], [0x00])
    return "device" if left_on_device else "stopped"
