"""A GT-1 patch = raw device bytes keyed by BTS/TSL field name (same keys as .tsl `params`)."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from .spec import GT1Spec, load_spec

NAME_LEN = 16


class Patch:
    def __init__(self, params: dict[str, int] | None = None, spec: GT1Spec | None = None,
                 meta: dict | None = None):
        self.spec = spec or load_spec()
        # keep only real device fields; .tsl files also carry derived values (e.g. delay_delay_time
        # = _h*128+_l) that would go stale once the byte pair is edited
        self.params: dict[str, int] = {k: int(v) for k, v in (params or {}).items()
                                       if k in self.spec.field_off and isinstance(v, (int, float))
                                       and not isinstance(v, bool)}
        self.meta = dict(meta or {})

    def copy(self) -> "Patch":
        return Patch(copy.deepcopy(self.params), self.spec, copy.deepcopy(self.meta))

    # -- name -------------------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "".join(chr(self.params.get(f"patch_name{i}", 32)) for i in range(1, NAME_LEN + 1)).rstrip()

    @name.setter
    def name(self, value: str) -> None:
        s = "".join(c if 32 <= ord(c) < 127 else "?" for c in value)[:NAME_LEN].ljust(NAME_LEN)
        for i, c in enumerate(s, 1):
            self.params[f"patch_name{i}"] = ord(c)

    # -- values -----------------------------------------------------------------------------------
    def get_raw(self, field: str) -> int:
        if field in self.spec.combined:
            return self.params.get(field + "_h", 0) * 128 + self.params.get(field + "_l", 0)
        return self.params.get(field, 0)

    def set_raw(self, field: str, raw: int) -> None:
        if field in self.spec.combined:
            self.params[field + "_h"], self.params[field + "_l"] = divmod(int(raw), 128)
            return
        if field not in self.spec.field_off:
            raise KeyError(f"unknown GT-1 field {field}")
        if not 0 <= raw <= 127:
            raise ValueError(f"{field}: raw value {raw} not 7-bit")
        self.params[field] = int(raw)

    def get(self, field: str):
        return self.spec.raw_to_display(field, self.get_raw(field))

    def set(self, field: str, value) -> None:
        """Set using display units (e.g. eq_low_gain=-3, preamp_a_type='MS1959 I', patch_level=100)."""
        if isinstance(value, bool):
            value = int(value)
        self.set_raw(field, self.spec.display_to_raw(field, value) if field in self.spec.defs else int(value))

    def on(self, block: str, state: bool = True) -> None:
        self.set_raw(f"{block}_on_off", 1 if state else 0)

    # -- serialization ----------------------------------------------------------------------------
    def block_bytes(self) -> list[list[int]]:
        out = []
        for b in self.spec.blocks:
            out.append([self.params.get(f, 0) if f else 0 for f in self.spec.block_fields(b)])
        return out

    @classmethod
    def from_block_bytes(cls, blocks: list[list[int]], spec: GT1Spec | None = None) -> "Patch":
        spec = spec or load_spec()
        p: dict[str, int] = {}
        for b, data in zip(spec.blocks, blocks):
            for f, v in zip(spec.block_fields(b), data):
                if f:
                    p[f] = v
        return cls(p, spec)

    def to_tsl_params(self) -> dict[str, int]:
        out = dict(self.params)
        for c in self.spec.combined:
            out[c] = self.get_raw(c)
        out["patchname"] = self.name  # type: ignore[assignment]
        return out

    def summary(self) -> dict:
        s = self.spec
        keys = ["preamp_a_type", "preamp_a_gain", "preamp_a_bass", "preamp_a_middle", "preamp_a_treble",
                "preamp_a_presence", "preamp_a_level", "preamp_a_sp_type", "od_ds_on_off", "od_ds_type",
                "od_ds_drive", "od_ds_effect_level", "master_eq_low_gain", "master_eq_mid_freq",
                "master_eq_mid_gain", "master_eq_high_gain", "ns1_on_off", "ns1_threshold", "delay_on_off",
                "delay_type", "delay_delay_time", "delay_f_back", "delay_effect_level", "reverb_on_off",
                "reverb_type", "reverb_time", "reverb_effect_level", "fx1_on_off", "fx1_fx_type", "fx2_on_off", "fx2_fx_type", "patch_level", "output_select"]
        return {k: s.raw_to_display(k, self.get_raw(k)) if k in s.defs else self.get_raw(k) for k in keys}


def tsl_document(patches: list[Patch], liveset_name: str = "tonematch") -> dict:
    return {
        "name": liveset_name,
        "formatRev": "0000",
        "device": "GT-1",
        "patchList": [{
            "params": p.to_tsl_params(), "name": p.name, "note": p.meta.get("note"),
            "category": p.meta.get("category"), "category2": p.meta.get("category2"),
            "orderNumber": i + 1, "id": str(int(time.time() * 1000) + i),
        } for i, p in enumerate(patches)],
        "liveSetData": {"name": liveset_name, "orderNumber": 1, "id": str(int(time.time()))},
        "version": "1.0.0",
    }


def write_tsl(path: Path, patches: list[Patch], liveset_name: str = "tonematch") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tsl_document(patches, liveset_name), indent=1), encoding="utf-8")


def read_tsl(path: Path) -> list[Patch]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for e in doc.get("patchList", []):
        p = Patch(e.get("params", {}), meta={k: e.get(k) for k in ("name", "note", "category", "category2")})
        out.append(p)
    return out
