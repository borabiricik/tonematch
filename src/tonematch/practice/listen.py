"""Real-time note detection for single-note playing (scales, licks, solos).

Fed in small blocks (the audio callback's), it reports each note's onset time and pitch:
  * onset  - spectral flux of a 1024-sample frame every 256 samples (5.8 ms), adaptive threshold, energy gate.
             A picked note is a burst of new energy across the spectrum; flux catches repeated notes too.
  * pitch  - YIN on the frames after the attack (the pick transient itself has no stable pitch).
  * legato - a hammer-on / pull-off has no pick burst, so a stable pitch change of more than ~half a semitone
             inside a sounding note also starts a new note.
Distortion is fine: YIN follows the period, which drive does not change (it adds harmonics).

Times are in samples of the input stream (`DetectedNote.sample`); the session maps them to the metronome clock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

SR = 44100
HOP = 256
FRAME = 1024
YIN_W = 700                 # integration window (16 ms)
TAU_MIN = SR // 1400        # highest pitch ~1.4 kHz (fret 22 on the high E is 1.17 kHz)
TAU_MAX = SR // 68          # lowest ~68 Hz (drop C# low string 69 Hz)
YIN_N = YIN_W + TAU_MAX
YIN_THRESHOLD = 0.15
MIN_CONF = 0.6
MIN_GAP_S = 0.035           # two picked notes closer than this are one (sextuplets at 280 bpm are 36 ms)
ATTACK_SKIP = 0.004         # pitch frames start this long after the onset (pick transient)
PITCH_FRAMES = 3            # confident pitch estimates that settle a note
MAX_WAIT_S = 0.09           # give up waiting for a pitch after this (muted / noisy note)
LEGATO_SEMITONES = 0.6
LEGATO_FRAMES = 3
# flux peaks a little after the true attack (the frame is centred late); measured on synthetic plucks
ONSET_LAG = FRAME // 2 - HOP // 2


@dataclass
class DetectedNote:
    sample: int          # onset, input-stream sample index
    midi: float          # median pitch (fractional MIDI); nan = no pitch found (muted / noise)
    conf: float          # 0..1 pitch confidence
    legato: bool = False

    @property
    def note(self) -> int | None:
        return None if np.isnan(self.midi) else int(round(self.midi))


def yin(x: np.ndarray, sr: int = SR) -> tuple[float, float]:
    """(f0 Hz or nan, confidence) for one buffer of YIN_N samples."""
    w = x[:YIN_W]
    n = 1 << (len(x) + YIN_W).bit_length()
    corr = np.fft.irfft(np.fft.rfft(x, n) * np.conj(np.fft.rfft(w, n)), n)[:TAU_MAX + 1]
    cs = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    taus = np.arange(TAU_MAX + 1)
    e_tau = cs[taus + YIN_W] - cs[taus]
    d = cs[YIN_W] + e_tau - 2 * corr
    d[0] = 0.0
    run = np.cumsum(d[1:])
    cm = np.ones_like(d)
    cm[1:] = d[1:] * taus[1:] / np.maximum(run, 1e-12)
    seg = cm[TAU_MIN:]
    below = np.flatnonzero(seg < YIN_THRESHOLD)
    if below.size:
        t = below[0]
        while t + 1 < len(seg) and seg[t + 1] < seg[t]:
            t += 1
    else:
        t = int(np.argmin(seg))
    tau = t + TAU_MIN
    conf = float(1 - cm[tau])
    if conf < 0.3:
        return float("nan"), max(0.0, conf)
    if 1 <= tau < TAU_MAX:  # parabolic refinement
        a, b, c = cm[tau - 1], cm[tau], cm[tau + 1]
        den = a - 2 * b + c
        if den > 0:
            tau = tau + 0.5 * (a - c) / den
    return sr / tau, conf


def hz_to_midi(f: float) -> float:
    return 69 + 12 * np.log2(f / 440.0)


class NoteDetector:
    """feed(block) -> notes finished in this block. Keeps its own sample counter (call reset() between takes)."""

    def __init__(self, sr: int = SR):
        self.sr = sr
        self.win = np.hanning(FRAME).astype(np.float32)
        lo, hi = 2, int(6000 * FRAME / sr)
        self.bins = slice(lo, hi)
        self.reset()

    def reset(self) -> None:
        self.buf = np.zeros(max(FRAME, YIN_N) + HOP, np.float32)
        self.pending = np.zeros(0, np.float32)
        self.pos = 0                       # samples consumed into hops
        self.prev_spec = None
        self.flux = deque(maxlen=3)        # (sample, flux, rms_db) of the last hops: peak picking needs one ahead
        self.flux_hist = deque(maxlen=40)
        self.floor_hist = deque(maxlen=860)
        self.last_onset = -10 ** 9
        self.cur: dict | None = None       # the sounding note: onset, pitch frames, settled pitch
        self.recent: deque = deque(maxlen=LEGATO_FRAMES)
        self.level_db = -120.0

    # -- feeding ----------------------------------------------------------------------------------
    def feed(self, block: np.ndarray) -> list[DetectedNote]:
        out: list[DetectedNote] = []
        x = np.concatenate([self.pending, np.asarray(block, np.float32)])
        n = len(x) // HOP * HOP
        for k in range(0, n, HOP):
            out += self._hop(x[k:k + HOP])
        self.pending = x[n:]
        return out

    def flush(self) -> list[DetectedNote]:
        """End of the take: report a note still waiting for its pitch."""
        if self.cur is not None and not self.cur["done"]:
            return [self._settle(force=True)]
        return []

    # -- one hop ----------------------------------------------------------------------------------
    def _hop(self, h: np.ndarray) -> list[DetectedNote]:
        out: list[DetectedNote] = []
        self.buf = np.concatenate([self.buf[HOP:], h])
        self.pos += HOP
        end = self.pos                                  # sample index just after this hop
        rms = float(np.sqrt(np.mean(h.astype(np.float64) ** 2)) + 1e-9)
        db = 20 * np.log10(rms)
        self.level_db = db
        self.floor_hist.append(db)
        frame = self.buf[-FRAME:] * self.win
        spec = np.log1p(100 * np.abs(np.fft.rfft(frame))[self.bins])
        flux = 0.0 if self.prev_spec is None else float(np.sum(np.maximum(0.0, spec - self.prev_spec)))
        self.prev_spec = spec
        self.flux.append((end, flux, db))
        # the noise floor is the quiet end of the last ~5 s; capped so continuous playing never lifts the gate
        # above -40 dBFS (a take is -35..-6 dBFS, rig hiss -70..-50)
        gate = max(-65.0, min(-40.0, float(np.percentile(self.floor_hist, 5)) + 12))

        # onset = local flux maximum one hop back, above an adaptive threshold, with signal above the gate
        if len(self.flux) == 3:
            (_, f0, _), (s1, f1, d1), (_, f2, _) = self.flux
            hist = np.array(self.flux_hist) if self.flux_hist else np.array([0.0])
            thr = float(np.median(hist)) * 1.6 + 0.05 * float(np.max(hist)) + 2.0
            if f1 > f0 and f1 >= f2 and f1 > thr and max(d1, db) > gate and s1 - self.last_onset > MIN_GAP_S * self.sr:
                onset = s1 - ONSET_LAG
                if self.cur is not None and not self.cur["done"]:
                    out.append(self._settle(force=True))
                self.cur = {"onset": onset, "pitches": [], "confs": [], "done": False, "legato": False, "midi": None}
                self.last_onset = s1
                self.recent.clear()
        self.flux_hist.append(flux)

        # pitch of the current note, frames that start after the attack
        f, conf = yin(self.buf[-YIN_N:], self.sr) if db > gate else (float("nan"), 0.0)
        m = hz_to_midi(f) if not np.isnan(f) else float("nan")
        c = self.cur
        if c is not None:
            frame_start = end - YIN_N
            if not c["done"]:
                if frame_start >= c["onset"] + ATTACK_SKIP * self.sr and conf >= MIN_CONF:
                    c["pitches"].append(m)
                    c["confs"].append(conf)
                if len(c["pitches"]) >= PITCH_FRAMES or end - c["onset"] > (MAX_WAIT_S * self.sr + YIN_N):
                    out.append(self._settle())
            elif db > gate and conf >= MIN_CONF and c["midi"] is not None:
                # legato: a stable new pitch while the note keeps sounding
                self.recent.append((frame_start, m))
                if len(self.recent) == LEGATO_FRAMES:
                    ms = [v for _, v in self.recent]
                    if (all(abs(v - c["midi"]) >= LEGATO_SEMITONES for v in ms) and max(ms) - min(ms) < 0.5
                            and self.recent[0][0] + YIN_N // 2 - self.last_onset > MIN_GAP_S * self.sr):
                        onset = int(self.recent[0][0] + YIN_W // 2)
                        new = DetectedNote(onset, float(np.median(ms)), 0.8, legato=True)
                        self.cur = {"onset": onset, "pitches": ms, "confs": [0.8] * len(ms), "done": True,
                                    "legato": True, "midi": new.midi}
                        self.last_onset = onset
                        self.recent.clear()
                        out.append(new)
            elif db <= gate:
                self.recent.clear()
        return out

    def _settle(self, force: bool = False) -> DetectedNote:
        c = self.cur
        c["done"] = True
        if c["pitches"]:
            mid = float(np.median(c["pitches"]))
            conf = float(np.mean(c["confs"]))
        else:
            mid, conf = float("nan"), 0.0
        c["midi"] = None if np.isnan(mid) else mid
        return DetectedNote(int(c["onset"]), mid, conf, legato=c["legato"])


def detect(y: np.ndarray, sr: int = SR, block: int = 512) -> list[DetectedNote]:
    """Offline helper (tests, recordings): run the streaming detector over a whole mono signal."""
    d = NoteDetector(sr)
    out: list[DetectedNote] = []
    for k in range(0, len(y), block):
        out += d.feed(y[k:k + block])
    return out + d.flush()
