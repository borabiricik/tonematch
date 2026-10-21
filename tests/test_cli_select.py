"""`gt1 select` (desktop app: "Cihazda seç"): selects the slot, writes nothing, one @@RESULT line."""

import json
from contextlib import contextmanager

from typer.testing import CliRunner

from tonematch import cli
from tonematch.device.gt1 import client


class FakeGT1:
    def __init__(self):
        self.selected = None
        self.writes = 0

    def select_patch(self, slot: int) -> None:
        self.selected = slot

    def patch_summary(self, slot=None) -> dict:
        return {"name": "PINK FLOYD SOLO ", "amp": "T-AMP LEAD", "gain": 70}

    def store_patch(self, *a, **k):  # must never be called by select
        self.writes += 1


def test_select_json(monkeypatch):
    fake = FakeGT1()

    @contextmanager
    def connect(port_hint="GT-1"):
        yield fake

    monkeypatch.setattr(client, "connect", connect)
    out = CliRunner().invoke(cli.app, ["gt1", "select", "U21", "--json"])
    assert out.exit_code == 0, out.output
    line = next(l for l in out.output.splitlines() if l.startswith("@@RESULT "))
    assert json.loads(line[9:]) == {"slot": "U21", "name": "PINK FLOYD SOLO "}
    assert fake.selected == 20  # 0-based, as GT1Client.select_patch expects
    assert fake.writes == 0
