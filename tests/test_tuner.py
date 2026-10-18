from tonematch.device.gt1.spec import load_spec
from tonematch.device.gt1.sysex import dt1
from tonematch.device.gt1.tuner import Reading, Tuner, decode_pitch, run_tuner

SPEC = load_spec()


def _push(name: str, data: list[int]) -> list[int]:
    return list(dt1(0x00, SPEC.model_id, SPEC.commands[name], data))


def test_decode_pitch_matches_bts():
    # Tuner.as: value[0] = note (00 = C .. 0B = B, 0C = no signal), value[1] - 50 = cents
    assert decode_pitch([0x04, 50]) == Reading("E", 0)
    assert decode_pitch([0x09, 38]) == Reading("A", -12)
    assert decode_pitch([0x0A, 100]) == Reading("A#", 50)
    assert decode_pitch([0x0C, 50]) == Reading(None, 0)
    assert decode_pitch([0x04, 53]).in_tune and not decode_pitch([0x04, 54]).in_tune


def test_feed_single_multi_and_mode():
    t = Tuner(SPEC)
    assert t.feed(_push("tuner_single_mode_pitch", [0x02, 45])) == \
        {"kind": "single", "note": "D", "cents": -5, "in_tune": False}
    assert t.feed(_push("tuner_multi_mode_str_6_pitch", [0x04, 51]))["string"] == 6
    assert t.feed(_push("running_mode", [0x00])) == {"kind": "mode", "mode": "off"}
    assert t.feed(_push("running_mode", [0x02])) == {"kind": "mode", "mode": "multi"}
    assert t.feed(_push("patch_write", [0, 4])) is None


class _Msg:
    type = "sysex"

    def __init__(self, raw):
        self.data = raw[1:-1]


class _FakeClient:
    """Plays back pushes; records DT1 writes."""

    def __init__(self, pushes):
        self.spec = SPEC
        self.pushes = [_Msg(p) for p in pushes]
        self.writes = []
        self.inp = self

    def iter_pending(self):
        out, self.pushes = self.pushes, []
        return out

    def _drain(self):
        pass

    def write(self, addr, data):
        self.writes.append((addr, data))


def test_run_tuner_dedupes_and_restores_play_mode():
    same = _push("tuner_single_mode_pitch", [0x04, 50])
    c = _FakeClient([same, same, _push("tuner_single_mode_pitch", [0x04, 60])])
    events, polls = [], iter(range(3))
    reason = run_tuner(c, "single", events.append, lambda: next(polls, 99) >= 2)
    assert reason == "stopped" and [e["cents"] for e in events] == [0, 10]
    rm = SPEC.commands["running_mode"]
    assert c.writes == [(rm, [1]), (rm, [0])]


def test_run_tuner_stops_when_left_on_device():
    c = _FakeClient([_push("running_mode", [0x00])])
    assert run_tuner(c, "multi", lambda e: None, lambda: False) == "device"
    assert c.writes == [(SPEC.commands["running_mode"], [2])]  # the unit already left the tuner
