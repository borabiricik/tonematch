"""Scoring a take: detected notes against the exercise's expected notes, online (one event per note).

Every expected note gets one verdict:
  hit   - right pitch, inside the tight window (shown green)
  early / late - right pitch, outside the tight window but inside the match window (yellow)
  wrong - a note at the right time with the wrong pitch (red)
  miss  - nothing played for it (red, reported once its window has passed)
A detected note that matches nothing is an "extra" (shown as a mark between notes), except a re-trigger of the
note still ringing (same pitch as the previous note): string ring and amp feedback do that, not the player.

Octave: a pitch an octave off counts as right (the tab says where, but the detector's octave on a heavily driven
low string is the least certain part, and the hand did the right thing).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TIGHT_MS = 25.0       # "on the beat" (pro players sit within about +-15 ms; 25 ms keeps it honest but reachable)
MAX_WINDOW_MS = 110.0


@dataclass
class Expected:
    i: int                # index over the whole take (all loops)
    j: int                # index inside the exercise's notes
    loop: int
    t: float              # seconds on the take clock
    midi: int
    gap: float            # seconds to the neighbouring notes (smaller side)
    verdict: str | None = None
    dt_ms: float | None = None
    played: int | None = None


@dataclass
class Scorer:
    expected: list[Expected]
    events: list[dict] = field(default_factory=list)
    extras: int = 0
    _last_pitch: int | None = None
    _next_miss: int = 0

    @classmethod
    def for_take(cls, notes: list[dict], beat_s: float, loop_beats: float, loops: int, t0: float) -> "Scorer":
        """Expected notes of `loops` repeats of an exercise starting at take time t0 (s)."""
        ex: list[Expected] = []
        for k in range(loops):
            for j, n in enumerate(notes):
                ex.append(Expected(len(ex), j, k, t0 + (k * loop_beats + n["beat"]) * beat_s, int(n["midi"]), 0.0))
        for a, e in enumerate(ex):
            prev = e.t - ex[a - 1].t if a else 1.0
            nxt = ex[a + 1].t - e.t if a + 1 < len(ex) else 1.0
            e.gap = max(0.02, min(prev, nxt))
        return cls(ex)

    def window(self, e: Expected) -> float:
        return min(MAX_WINDOW_MS, 0.5 * e.gap * 1000)

    def tight(self, e: Expected) -> float:
        return min(TIGHT_MS, 0.25 * e.gap * 1000)

    def note(self, t: float, midi: float | None) -> dict:
        """A detected note at take time t (s). Returns the event (also kept in self.events)."""
        played = None if midi is None or np.isnan(midi) else int(round(midi))
        # nearest open expected note within its window
        best, best_dt = None, None
        for e in self._around(t):
            if e.verdict is not None:
                continue
            dt = (t - e.t) * 1000
            if abs(dt) <= self.window(e) and (best is None or abs(dt) < abs(best_dt)):
                best, best_dt = e, dt
        if best is None:
            same = played is not None and self._last_pitch is not None and played == self._last_pitch
            ev = {"kind": "note", "status": "ring" if same else "extra", "played": played, "t": round(t, 3)}
            if not same:
                self.extras += 1
            self.events.append(ev)
            return ev
        right = played is not None and (played - best.midi) % 12 == 0 and abs(played - best.midi) <= 12
        if not right:
            status = "wrong"
        elif abs(best_dt) <= self.tight(best):
            status = "hit"
        else:
            status = "early" if best_dt < 0 else "late"
        best.verdict, best.dt_ms, best.played = status, round(best_dt, 1), played
        self._last_pitch = played
        ev = {"kind": "note", "status": status, "i": best.i, "j": best.j, "loop": best.loop, "dt_ms": best.dt_ms,
              "played": played, "expected": best.midi, "t": round(t, 3)}
        self.events.append(ev)
        return ev

    def misses(self, now: float) -> list[dict]:
        """Expected notes whose window ended before take time `now` without a match."""
        out = []
        while self._next_miss < len(self.expected):
            e = self.expected[self._next_miss]
            if e.t + self.window(e) / 1000 > now:
                break
            self._next_miss += 1
            if e.verdict is None:
                e.verdict = "miss"
                ev = {"kind": "note", "status": "miss", "i": e.i, "j": e.j, "loop": e.loop, "expected": e.midi}
                self.events.append(ev)
                out.append(ev)
        return out

    def _around(self, t: float):
        # expected notes are sorted by time: bisect to the neighbourhood
        lo, hi = 0, len(self.expected)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.expected[mid].t < t - MAX_WINDOW_MS / 1000:
                lo = mid + 1
            else:
                hi = mid
        for e in self.expected[lo:]:
            if e.t > t + MAX_WINDOW_MS / 1000:
                break
            yield e

    def summary(self, upto_loop: int | None = None) -> dict:
        """Accuracy (right pitch inside the match window), timing, per loop. upto_loop: only finished loops."""
        ex = [e for e in self.expected if e.verdict is not None and (upto_loop is None or e.loop <= upto_loop)]
        if not ex:
            return {"notes": 0, "correct": 0, "accuracy": 0.0, "on_time": 0.0, "mean_ms": None, "spread_ms": None,
                    "extras": self.extras, "per_loop": [], "counts": {}}
        right = [e for e in ex if e.verdict in ("hit", "early", "late")]
        dts = np.array([e.dt_ms for e in right]) if right else np.zeros(0)
        loops = []
        for k in sorted({e.loop for e in ex}):
            le = [e for e in ex if e.loop == k]
            loops.append(round(sum(e.verdict in ("hit", "early", "late") for e in le) / len(le), 3))
        counts = {v: sum(e.verdict == v for e in ex) for v in ("hit", "early", "late", "wrong", "miss")}
        # where it goes wrong: exercise positions missed in more than one loop
        trouble = {}
        for e in ex:
            if e.verdict in ("wrong", "miss"):
                trouble[e.j] = trouble.get(e.j, 0) + 1
        return {"notes": len(ex), "correct": len(right), "accuracy": round(len(right) / len(ex), 3),
                "on_time": round(counts["hit"] / len(ex), 3),
                "mean_ms": round(float(dts.mean()), 1) if dts.size else None,
                "spread_ms": round(float(dts.std()), 1) if dts.size else None,
                "extras": self.extras, "per_loop": loops, "counts": counts,
                "trouble": sorted([j for j, c in trouble.items() if c > 1])}
