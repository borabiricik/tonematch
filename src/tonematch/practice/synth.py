"""Sounds the practice system plays: the metronome click and plucked-string notes (ear training, references).

Also used by the tests as a stand-in guitar: a Karplus-Strong string, optionally through a tanh "amp".
"""

from __future__ import annotations

import numpy as np

SR = 44100


def click(accent: bool = False, sr: int = SR) -> np.ndarray:
    """A short woodblock-like click (~25 ms): accent = beat 1, higher and louder."""
    n = int(0.025 * sr)
    t = np.arange(n) / sr
    f = 2000.0 if accent else 1400.0
    env = np.exp(-t * 220)
    return ((0.9 if accent else 0.6) * env * np.sin(2 * np.pi * f * t)).astype(np.float32)


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def pluck(midi: float, seconds: float = 0.6, sr: int = SR, seed: int = 0, bright: float = 0.5) -> np.ndarray:
    """Karplus-Strong plucked string (block form: one period per step). bright 0..1 = how hard the pick attack is."""
    rng = np.random.default_rng(seed)
    p = max(2, int(round(sr / midi_hz(midi))))
    buf = rng.uniform(-1, 1, p)
    for _ in range(int((1 - bright) * 4)):  # a darker burst = a softer attack
        buf = 0.5 * (buf + np.roll(buf, 1))
    n = int(seconds * sr)
    out = np.empty(-(-n // p) * p)
    for k in range(0, len(out), p):
        out[k:k + p] = buf
        buf = 0.996 * 0.5 * (buf + np.roll(buf, -1))
    out = out[:n] * np.exp(-np.arange(n) / sr * 2.5)
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


def render(notes: list[tuple[float, float, float]], seconds: float, sr: int = SR, drive: float = 0.0,
           level: float = 0.3, legato: set[int] | None = None, seed: int = 0) -> np.ndarray:
    """A take: (onset s, midi, length s) notes; a new note cuts the previous one (one string, like a solo line).

    drive > 0 = through tanh distortion. legato: indexes of notes played without a new pick attack (hammer / pull):
    the pitch changes but the level carries on (no burst)."""
    y = np.zeros(int(seconds * sr), np.float32)
    legato = legato or set()
    for i, (t0, m, ln) in enumerate(notes):
        a = int(t0 * sr)
        x = pluck(m, ln + 0.05, sr, seed=seed + i, bright=0.2 if i in legato else 0.6)
        if i in legato:
            x *= 0.55  # no pick attack: softer start
        b = min(len(y), a + len(x))
        y[a:b] = x[:b - a]  # monophonic: the new note replaces the old
        fade = min(64, b - a)
        y[a:a + fade] *= np.linspace(0.2 if i in legato else 0.0, 1.0, fade)
    if drive > 0:
        y = np.tanh(drive * y) / np.tanh(drive)
    return (level * y).astype(np.float32)
