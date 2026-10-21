"""Theory and ear drills answered on the guitar: the app asks, you play, the detector judges.

Kinds:
  fretboard - "C on string 5": find any note name on any string (frets 0..15).
  interval  - "a major third above A (string 6, fret 5)": play the target note.
  degree    - "the b3 of A minor": scale degrees anywhere on the neck.
  chord     - "the 7th of Dm7": chord tones.
  echo      - ear: the app plays 2..4 notes (through the GT-1 to the amp), you play them back.

Answering by playing ties the name, the sound and the hand together; reaction time is measured too (knowing a
note is finding it without thinking). Items you miss or answer slowly come back more often (a simple weighted
spaced repetition kept in the practice state).
"""

from __future__ import annotations

import random
import time

import numpy as np

from .theory import (CHORD_SYMBOLS, CHORDS, DEGREES, INTERVALS, SCALE_NAMES, SCALES, STANDARD, frets_for_pc, midi_of,
                     note_name, pc, scale_pcs, uses_flats)

KINDS = {"fretboard": "Klavyede nota", "interval": "Aralık", "degree": "Gam derecesi", "chord": "Akor tonu",
         "echo": "Kulaktan tekrar"}
ANSWER_S = {"fretboard": 8.0, "interval": 8.0, "degree": 8.0, "chord": 8.0, "echo": 10.0}
NATURALS = ["C", "D", "E", "F", "G", "A", "B"]
ROOTS = ["C", "G", "D", "A", "E", "F", "Bb"]
QUIZ_SCALES = ["major", "natural_minor", "minor_pentatonic", "dorian", "mixolydian"]


def _weight(item: str, stats: dict) -> float:
    s = stats.get(item)
    if not s:
        return 2.0                           # never seen: high
    miss = 1 - s["right"] / max(1, s["seen"])
    slow = min(1.0, s.get("ms", 3000) / 4000)
    return 0.3 + 2.5 * miss + slow


def question(kind: str, rng: random.Random, stats: dict | None = None, level: int = 1) -> dict:
    """One question: prompt text, the accepted MIDI notes (or pitch classes), and the answer to reveal."""
    stats = stats or {}
    if kind == "fretboard":
        names = NATURALS if level < 2 else NATURALS + ["C#", "Eb", "F#", "Ab", "Bb"]
        pool = [(s, n) for s in range(1, 7) for n in names]
        s, n = rng.choices(pool, [_weight(f"fb:{s}:{n}", stats) for s, n in pool])[0]
        frets = frets_for_pc(s, pc(n), 0, 15)
        return {"kind": kind, "item": f"fb:{s}:{n}", "prompt": f"{s}. telde {n}", "string": s,
                "accept": [midi_of(s, f) for f in frets], "answer": f"{n}: {s}. tel {', '.join(map(str, frets))}. perde",
                "frets": frets, "count": 1}
    if kind == "interval":
        ivs = [3, 4, 5, 7, 12] if level < 2 else list(range(1, 13))
        s = rng.choice([6, 5, 4])
        f = rng.randint(1, 9)
        root = midi_of(s, f)
        iv = rng.choices(ivs, [_weight(f"iv:{i}", stats) for i in ivs])[0]
        flats = False
        return {"kind": kind, "item": f"iv:{iv}", "count": 1,
                "prompt": f"{note_name(root, flats)} ({s}. tel {f}. perde) üstüne {INTERVALS[iv][1]}",
                "root": root, "accept": [root + iv, root + iv + 12], "pcs": None,
                "answer": f"{note_name(root + iv, flats)} ({INTERVALS[iv][0]}, {iv} yarım ses)"}
    if kind == "degree":
        key = rng.choice(ROOTS)
        scale = rng.choice(QUIZ_SCALES[:3] if level < 2 else QUIZ_SCALES)
        ivs = SCALES[scale][1:]
        iv = rng.choices(ivs, [_weight(f"dg:{scale}:{i}", stats) for i in ivs])[0]
        flats = uses_flats(key, scale)
        target = (pc(key) + iv) % 12
        return {"kind": kind, "item": f"dg:{scale}:{iv}", "count": 1,
                "prompt": f"{key} {SCALE_NAMES[scale]}: {DEGREES[iv]}. derece", "pcs": [target], "accept": None,
                "answer": f"{note_name(target, flats)} ({DEGREES[iv]})"}
    if kind == "chord":
        root = rng.choice(ROOTS)
        quality = rng.choice(["maj", "min", "dom7", "min7", "maj7"] if level >= 2 else ["maj", "min", "dom7", "min7"])
        tones = CHORDS[quality]
        which = rng.randrange(1, len(tones))
        names = {1: "3'lüsü", 2: "5'lisi", 3: "7'lisi"}
        target = (pc(root) + tones[which]) % 12
        flats = root in ("F", "Bb")
        return {"kind": kind, "item": f"ch:{quality}:{which}", "count": 1,
                "prompt": f"{root}{CHORD_SYMBOLS[quality]} akorunun {names[which]}", "pcs": [target], "accept": None,
                "answer": f"{note_name(target, flats)}"}
    if kind == "echo":
        n = 2 if level < 2 else rng.choice([3, 4])
        key = rng.choice(ROOTS)
        pcs = scale_pcs(key, "major")
        start = 52 + pcs[0] % 12  # around the middle of the neck
        notes = [start]
        for _ in range(n - 1):
            cand = [m for m in range(notes[-1] - 7, notes[-1] + 8) if m % 12 in pcs and m != notes[-1]]
            notes.append(rng.choice(cand))
        names = " ".join(note_name(m) for m in notes)
        return {"kind": kind, "item": f"ec:{n}", "count": n, "prompt": f"Dinle ve çal: {n} nota", "play": notes,
                "pcs": None, "accept": None, "sequence": notes, "answer": names}
    raise ValueError(f"bilinmeyen soru türü: {kind}")


def judge(q: dict, played: list[int]) -> bool:
    """played: detected MIDI notes after the prompt, in order."""
    if q["kind"] == "echo":
        # pitch classes in order (octave free: the ear found the notes, the hand may pick another octave)
        got = [m % 12 for m in played[:q["count"]]]
        return got == [m % 12 for m in q["sequence"]]
    if not played:
        return False
    m = played[0]
    if q.get("accept"):
        return m in q["accept"]
    return m % 12 in q["pcs"]


def update_stats(stats: dict, q: dict, right: bool, ms: float | None) -> None:
    s = stats.setdefault(q["item"], {"seen": 0, "right": 0, "ms": 4000})
    s["seen"] += 1
    s["right"] += int(right)
    if right and ms:
        s["ms"] = round(0.7 * s["ms"] + 0.3 * ms)


def run_quiz(kind: str, count: int, emit, should_stop, settings: dict, level: int = 1, seed: int | None = None) -> dict:
    """Ask `count` questions on the GT-1 (listen + play the echo prompts)."""
    import queue

    from . import progress
    from .listen import SR, NoteDetector
    from .session import Duplex, find_device
    from .synth import pluck

    st = progress.load_state()
    stats = st.setdefault("quiz", {})
    rng = random.Random(seed if seed is not None else time.time())
    dev, label = find_device()
    det = NoteDetector()
    results = []
    with Duplex(dev, float(settings.get("click_level", 0.7))) as io:
        emit({"kind": "start", "quiz": kind, "count": count, "device": label})
        for qi in range(count):
            if should_stop():
                break
            k = kind if kind != "mix" else rng.choice(["fretboard", "interval", "degree", "chord", "echo"])
            q = question(k, rng, stats, level)
            listen_from = io.frame + int(0.15 * SR)
            if q.get("play"):
                gap = int(0.55 * SR)
                for n, m in enumerate(q["play"]):
                    io.add(io.frame + int(0.3 * SR) + n * gap, 0.6 * pluck(m, 0.6, seed=n))
                listen_from = io.frame + int(0.3 * SR) + len(q["play"]) * gap
            emit({"kind": "question", "n": qi + 1, **{k2: v for k2, v in q.items() if k2 not in ("accept", "pcs",
                                                                                                    "sequence")}})
            played: list[int] = []
            t_prompt = time.monotonic()
            first_ms = None
            deadline = time.monotonic() + ANSWER_S[k] + (len(q.get("play", [])) * 0.55)
            while time.monotonic() < deadline and len(played) < q["count"] and not should_stop():
                try:
                    a, block = io.q.get(timeout=0.5)
                except queue.Empty:
                    raise RuntimeError("GT-1'den ses gelmiyor (USB ses akışı durdu)")
                for nd in det.feed(block):
                    if nd.sample < listen_from or nd.note is None:
                        continue
                    if played and nd.note == played[-1] and q["kind"] != "echo":
                        continue
                    played.append(nd.note)
                    if first_ms is None:
                        first_ms = round((time.monotonic() - t_prompt) * 1000)
                    emit({"kind": "heard", "n": qi + 1, "note": note_name(nd.note), "midi": nd.note})
            right = judge(q, played)
            update_stats(stats, q, right, first_ms)
            results.append({"item": q["item"], "right": right, "ms": first_ms})
            emit({"kind": "answer", "n": qi + 1, "right": right, "answer": q["answer"],
                  "played": [note_name(m) for m in played], "ms": first_ms})
            t_end = time.monotonic() + 1.4
            while time.monotonic() < t_end:  # let the answer show; drain input meanwhile
                try:
                    _, block = io.q.get(timeout=0.2)
                    det.feed(block)
                except queue.Empty:
                    pass
    progress.save_state(st)
    right = sum(r["right"] for r in results)
    times = [r["ms"] for r in results if r["right"] and r["ms"]]
    summary = {"quiz": kind, "asked": len(results), "right": right,
               "accuracy": round(right / len(results), 3) if results else 0.0,
               "mean_ms": round(float(np.mean(times))) if times else None, "items": results}
    progress.log_quiz(summary)
    return summary
