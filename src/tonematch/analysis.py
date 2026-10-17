"""Guitar stem analysis: windowing, role clustering (rhythm / lead / clean ...), tone profiles.

Everything here is pure DSP on numpy arrays; no device I/O.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter
from scipy.signal import butter, sosfiltfilt, welch

from .config import SR

log = logging.getLogger(__name__)

EPS = 1e-12
BAND_CENTERS = [80, 160, 320, 640, 1280, 2560, 5120, 10240]  # octave bands


# ------------------------------------------------------------------------------------------- utils
def load_stereo(path: Path) -> np.ndarray:
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != SR:
        y = librosa.resample(y.T, orig_sr=sr, target_sr=SR).T
    y = y.T
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    return y[:2]


def _db(x: float) -> float:
    return float(10 * np.log10(max(x, EPS)))


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x * x) + EPS))


def _sigmoid(z: float) -> float:
    return float(1 / (1 + np.exp(-z)))


def _highpass(x: np.ndarray, hz: float) -> np.ndarray:
    sos = butter(4, hz, btype="highpass", fs=SR, output="sos")
    return sosfiltfilt(sos, x, axis=-1)


# ----------------------------------------------------------------------------------------- windows
@dataclass
class Window:
    start: float
    end: float
    rms_db: float = -120.0
    width: float = 0.0        # side/mid rms ratio
    corr: float = 1.0         # L/R correlation
    pan: float = 0.0          # -1 L .. +1 R
    flat_mid: float = 0.0     # spectral flatness 0.8-5 kHz
    hf_ratio_db: float = 0.0  # 2-6 kHz vs 150 Hz-1 kHz
    crest_db: float = 0.0
    sustain: float = 0.0      # median / p95 frame rms
    flat_hi: float = 0.0      # spectral flatness 1.5-6 kHz
    periodicity: float = 0.0  # mean normalized autocorr peak (monophonic -> high)
    f0: float = 0.0           # median f0 of periodic frames
    c_ratio: float = 0.0      # centre-panned energy share
    c_per: float = 0.0        # periodicity of the centre-extracted signal
    c_f0: float = 0.0
    gain: float = 0.0         # distortion estimate 0..1
    active: bool = False
    label: int = -1


def make_windows(duration: float, beats: np.ndarray, tempo: float) -> list[Window]:
    beat_len = 60.0 / max(tempo, 40.0)
    k = max(1, int(round(2.6 / beat_len)))  # ~2-3 s, aligned to beats
    edges = list(beats[::k]) if len(beats) > 2 * k else list(np.arange(0, duration, 2.6))
    if not edges or edges[0] > 0.5:
        edges = [0.0] + edges
    edges.append(duration)
    return [Window(a, b) for a, b in zip(edges[:-1], edges[1:]) if b - a > 1.0]


def _frame_periodicity(mono: np.ndarray, sr: int, hop: int = 512, n: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame normalized autocorrelation peak (70-1400 Hz) and the f0 at that peak."""
    frames = librosa.util.frame(np.pad(mono, (n // 2, n // 2)), frame_length=n, hop_length=hop).T
    frames = frames * np.hanning(n)
    spec = np.fft.rfft(frames, 2 * n, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :n]
    ac = ac / (ac[:, :1] + EPS)
    # unbias the window taper so long lags are not penalised
    taper = np.correlate(np.hanning(n), np.hanning(n), "full")[n - 1:]
    ac = ac / np.maximum(taper / taper[0], 0.1)
    lo, hi = int(sr / 1400), int(sr / 70)
    seg = ac[:, lo:hi]
    idx = np.argmax(seg, axis=1)
    peak = np.clip(seg[np.arange(len(idx)), idx], 0, 1)
    return peak, sr / (idx + lo)


def _pitch_track(mono: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sr_p = 22050
    x = librosa.resample(mono, orig_sr=SR, target_sr=sr_p)
    env = librosa.feature.rms(y=x, frame_length=2048, hop_length=512)[0]
    per, f0 = _frame_periodicity(x, sr_p)
    n = min(len(per), len(env))
    return per[:n], f0[:n], env[:n]


def _window_pitch(per, f0, env, w: "Window", fps: float) -> tuple[float, float]:
    fa, fb = int(w.start * fps), min(int(w.end * fps), len(per))
    if fb <= fa:
        return 0.0, 0.0
    fe = env[fa:fb]
    sel = fe > 0.1 * (fe.max() + EPS)
    pp = per[fa:fb][sel]
    good = sel & (per[fa:fb] > 0.6)
    return (float(np.mean(pp)) if len(pp) else 0.0,
            float(np.median(f0[fa:fb][good])) if good.sum() > 3 else 0.0)


def window_features(y: np.ndarray, wins: list[Window]) -> None:
    L, R = y[0], y[1]
    M, S = (L + R) / 2, (L - R) / 2
    C = center_extract(y)[0]
    per, f0, frame_env = _pitch_track(M)
    cper, cf0, cenv = _pitch_track(C)
    fps = 22050 / 512
    for w in wins:
        a, b = int(w.start * SR), int(w.end * SR)
        l, r, m, s = L[a:b], R[a:b], M[a:b], S[a:b]
        if len(m) < SR // 2:
            continue
        rl, rr = _rms(l), _rms(r)
        w.rms_db = 20 * np.log10((rl + rr) / 2)
        w.width = _rms(s) / (_rms(m) + EPS)
        w.corr = float(np.sum(l * r) / np.sqrt(np.sum(l * l) * np.sum(r * r) + EPS))
        w.pan = (rr - rl) / (rr + rl + EPS)
        st = np.abs(librosa.stft(m, n_fft=4096, hop_length=2048)) ** 2 + np.abs(
            librosa.stft(s, n_fft=4096, hop_length=2048)) ** 2
        freqs = librosa.fft_frequencies(sr=SR, n_fft=4096)
        band = (freqs > 800) & (freqs < 5000)
        p = st[band] + EPS
        fl = np.exp(np.mean(np.log(p), axis=0)) / np.mean(p, axis=0)
        frame_e = st.sum(axis=0)
        loud = frame_e > 0.05 * frame_e.max()
        w.flat_mid = float(np.median(fl[loud])) if loud.any() else 0.0
        ph = st[(freqs > 1500) & (freqs < 6000)] + EPS
        flh = np.exp(np.mean(np.log(ph), axis=0)) / np.mean(ph, axis=0)
        w.flat_hi = float(np.median(flh[loud])) if loud.any() else 0.0
        e_hi = st[(freqs > 2000) & (freqs < 6000)].sum()
        e_lo = st[(freqs > 150) & (freqs < 1000)].sum()
        w.hf_ratio_db = _db(e_hi / (e_lo + EPS))
        env = librosa.feature.rms(y=m, frame_length=1024, hop_length=512)[0]
        w.crest_db = 20 * np.log10((np.max(np.abs(m)) + EPS) / (_rms(m)))
        w.sustain = float(np.median(env) / (np.percentile(env, 95) + EPS))
        w.periodicity, w.f0 = _window_pitch(per, f0, frame_env, w, fps)
        w.c_per, w.c_f0 = _window_pitch(cper, cf0, cenv, w, fps)
        w.c_ratio = _rms(C[a:b]) / (_rms(m) + EPS)
        w.gain = gain_score(w)


def gain_score(w: Window) -> float:
    """Distortion amount 0..1, dominated by 0.8-5 kHz spectral flatness (log scale).

    Calibration (docs/04): clean stems sit at flatness 0.002-0.04 (NEM intro, MoP interlude,
    Run Like Hell), driven/distorted at 0.07-0.45 (Back in Black, MoP, NEM chorus).
    Sustain/crest only nudge, because ringing clean arpeggios and mastering compression fool them.
    """
    z = (3.0 * (np.log10(w.flat_mid + 1e-4) - np.log10(0.05)) / 0.3
         + 0.5 * (w.sustain - 0.65) / 0.15
         - 0.3 * (w.crest_db - 13.0) / 3.0)
    return _sigmoid(z)


# ---------------------------------------------------------------------------------------- clusters
def cluster_windows(wins: list[Window]) -> dict[int, list[Window]]:
    from sklearn.mixture import GaussianMixture

    act = [w for w in wins if w.active]
    if len(act) < 6:
        for w in act:
            w.label = 0
        return {0: act}
    X = np.array([[w.gain, w.width, w.c_ratio, w.c_per, np.log2(max(w.c_f0, 60) / 200),
                   w.hf_ratio_db, w.pan] for w in act])
    X = (X - X.mean(0)) / (X.std(0) + 1e-6) * np.array([2.0, 1.0, 1.2, 0.8, 1.0, 0.6, 0.5])
    best, best_bic = None, np.inf
    for k in range(1, min(5, len(act) // 6 + 1)):
        g = GaussianMixture(k, covariance_type="diag", random_state=0, n_init=3).fit(X)
        bic = g.bic(X)
        if bic < best_bic:
            best, best_bic = g, bic
    labels = best.predict(X)
    labels = median_filter(labels, size=3, mode="nearest")
    # drop tiny clusters into the nearest big one
    counts = np.bincount(labels, minlength=best.n_components)
    gains = {c: np.median([w.gain for w, l in zip(act, labels) if l == c]) for c in range(len(counts)) if counts[c]}
    main = [c for c in gains if counts[c] >= max(3, 0.08 * len(act))]
    # a short clean interlude inside a heavy song (or vice versa) is small but clearly different
    big = main + [c for c in gains if c not in main and counts[c] >= 4 and main
                  and min(abs(gains[c] - gains[m]) for m in main) > 0.5]
    if not big:
        big = [int(np.argmax(counts))]
    for i, l in enumerate(labels):
        if l not in big:
            d = [np.sum((X[i] - best.means_[c]) ** 2) for c in big]
            labels[i] = big[int(np.argmin(d))]
    out: dict[int, list[Window]] = {}
    for w, l in zip(act, labels):
        w.label = int(l)
        out.setdefault(int(l), []).append(w)
    return out


def name_groups(clusters: dict[int, list[Window]]) -> dict[str, list[Window]]:
    stats = {}
    for c, ws in clusters.items():
        stats[c] = {k: float(np.median([getattr(w, k) for w in ws]))
                    for k in ("gain", "width", "c_ratio", "c_per", "c_f0", "pan")}
        stats[c]["dur"] = sum(w.end - w.start for w in ws)
    clean = [c for c in stats if stats[c]["gain"] < 0.42]
    dist = [c for c in stats if c not in clean]
    groups: dict[str, list[Window]] = {}
    if clean:
        groups["clean"] = sorted(sum((clusters[c] for c in clean), []), key=lambda w: w.start)
    if dist:
        def lead_score(c):
            # a lead sits in the centre over wide rhythm guitars and plays single high notes
            s = stats[c]
            return s["c_ratio"] + 0.5 * s["c_per"] + 0.5 * (s["c_f0"] > 250) - 0.3 * min(s["width"], 1)
        lead_c = max(dist, key=lead_score)
        s = stats[lead_c]
        is_lead = len(dist) > 1 and s["c_f0"] > 220 and s["c_per"] > 0.6 and \
            lead_score(lead_c) - max((lead_score(c) for c in dist if c != lead_c), default=0) > 0.2
        rhythm = [c for c in dist if not (is_lead and c == lead_c)]
        if is_lead:
            groups["lead"] = sorted(clusters[lead_c], key=lambda w: w.start)
        if rhythm:
            rhythm.sort(key=lambda c: -stats[c]["dur"])
            main = rhythm[0]
            groups["rhythm"] = list(clusters[main])
            for c in rhythm[1:]:
                if stats[main]["gain"] - stats[c]["gain"] > 0.2:
                    groups.setdefault("crunch", []).extend(clusters[c])
                else:
                    groups["rhythm"].extend(clusters[c])
            for g in ("rhythm", "crunch"):
                if g in groups:
                    groups[g].sort(key=lambda w: w.start)
    return groups


# ----------------------------------------------------------------------------------------- profile
@dataclass
class DelayEstimate:
    detected: bool = False    # strong, unambiguous echo
    possible: bool = False    # weaker echo-like peak: trust only if the rig is known to use delay
    time_ms: float = 0.0
    strength: float = 0.0     # normalized coherent echo peak
    feedback: float = 0.0     # 0..1
    pingpong: bool = False
    note: str = ""            # nearest tempo subdivision


@dataclass
class ReverbEstimate:
    tail_db: float = -60.0    # energy 80-250 ms after note releases, relative to the note
    decay_s: float = 0.0      # RT60-ish from release slopes
    amount: str = "unknown"   # dry / small / medium / large / unknown (too few clean note releases)


@dataclass
class GroupProfile:
    name: str
    seconds: float
    segments: list[tuple[float, float]]
    gain: float
    gain_class: str
    flatness: float
    width: float
    periodicity: float
    f0_median: float
    crest_db: float
    sustain: float
    bands_db: dict[str, float]
    tilt_db_per_oct: float
    third_oct_db: dict[str, float] = field(default_factory=dict)
    descriptors: dict[str, float] = field(default_factory=dict)
    delay: DelayEstimate = field(default_factory=DelayEstimate)
    reverb: ReverbEstimate = field(default_factory=ReverbEstimate)
    stereo: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _merge_segments(ws: list[Window], gap: float = 0.05) -> list[tuple[float, float]]:
    segs: list[list[float]] = []
    for w in sorted(ws, key=lambda w: w.start):
        if segs and w.start - segs[-1][1] <= gap:
            segs[-1][1] = w.end
        else:
            segs.append([w.start, w.end])
    return [(round(a, 2), round(b, 2)) for a, b in segs]


def center_extract(y: np.ndarray, chunk_s: float = 30.0) -> np.ndarray:
    """Keep time-frequency bins that are panned centre (|L|~|R|, in phase). Returns stereo."""
    n = y.shape[1]
    out = np.zeros(n, dtype=np.float32)
    step = int(chunk_s * SR)
    pad = 4096
    for a in range(0, n, step):
        lo, hi = max(0, a - pad), min(n, a + step + pad)
        Ls = librosa.stft(y[0, lo:hi], n_fft=4096, hop_length=1024)
        Rs = librosa.stft(y[1, lo:hi], n_fft=4096, hop_length=1024)
        sim = 2 * np.real(Ls * np.conj(Rs)) / (np.abs(Ls) ** 2 + np.abs(Rs) ** 2 + EPS)
        c = librosa.istft(np.clip(sim, 0, 1) ** 4 * (Ls + Rs) / 2, hop_length=1024, length=hi - lo)
        out[a:min(n, a + step)] = c[a - lo:a - lo + min(step, n - a)]
    return np.vstack([out, out])


THIRD_OCT = [63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500,
             3150, 4000, 5000, 6300, 8000]


def _psd(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    f, pl = welch(y[0], fs=SR, nperseg=8192)
    _, pr = welch(y[1], fs=SR, nperseg=8192)
    return f, (pl + pr) / 2


def _band_db(f: np.ndarray, p: np.ndarray, lo: float, hi: float) -> float:
    sel = (f >= lo) & (f < hi)
    return _db(p[sel].mean())


def _listening(y: np.ndarray) -> tuple[dict[str, float], dict[str, float]]:
    """1/3-octave spectrum (rel. to 320 Hz-2.5 kHz) + descriptors a tone engineer listens for."""
    f, p = _psd(y)
    third = {c: _band_db(f, p, c / 2 ** (1 / 6), c * 2 ** (1 / 6)) for c in THIRD_OCT}
    ref = np.mean([v for c, v in third.items() if 320 <= c <= 2500])
    third_rel = {(f"{c}Hz" if c < 1000 else f"{c / 1000:g}kHz"): round(v - ref, 1) for c, v in third.items()}
    b = lambda lo, hi: _band_db(f, p, lo, hi)  # noqa: E731
    desc = {
        # >0: deep/loose low end, <0: tight (palm-mute thump lives at 100-200 Hz)
        "low_depth_db": round(b(60, 110) - b(110, 220), 1),
        # <0: scooped mids (V curve), >0: mid-forward
        "mid_scoop_db": round(b(400, 1200) - (b(150, 350) + b(1800, 4000)) / 2, 1),
        # upper-mid bite / presence vs core mids
        "presence_db": round(b(2000, 4500) - b(700, 1600), 1),
        # fizz/air above the presence region (cab-sim / mic darkness)
        "fizz_db": round(b(5000, 8000) - b(2000, 4500), 1),
        # low-mid body / boxiness
        "body_db": round(b(200, 450) - b(700, 1600), 1),
    }
    return third_rel, desc


def _bands(y: np.ndarray) -> tuple[dict[str, float], float]:
    f, p = _psd(y)
    vals = []
    for fc in BAND_CENTERS:
        sel = (f >= fc / np.sqrt(2)) & (f < fc * np.sqrt(2))
        vals.append(_db(p[sel].mean()))
    vals = np.array(vals)
    ref = vals[2:6].mean()  # 320 Hz - 2.5 kHz
    rel = vals - ref
    oct_idx = np.arange(len(BAND_CENTERS))
    sel = (np.array(BAND_CENTERS) >= 160) & (np.array(BAND_CENTERS) <= 5120)
    tilt = float(np.polyfit(oct_idx[sel], rel[sel], 1)[0])
    return {f"{fc}Hz" if fc < 1000 else f"{fc / 1000:g}kHz": round(float(v), 1)
            for fc, v in zip(BAND_CENTERS, rel)}, round(tilt, 2)


def detect_delay(y: np.ndarray, segs: list[tuple[float, float]], tempo: float) -> DelayEstimate:
    """Coherent echoes give sharp waveform-autocorrelation peaks; human repetition does not."""
    from scipy.signal import find_peaks

    # Calibrated on reference stems: real echoes (Run Like Hell, 389 ms) reach h~0.016, while
    # dry stems only show separation-model artefacts (~86 / ~223 ms) at h<=0.003.
    lo_ms, hi_ms = 70, 1200
    lags = np.arange(int(lo_ms * SR / 1000), int(hi_ms * SR / 1000))
    acc = np.zeros(len(lags))
    wsum = 0.0
    sos = butter(4, [300, 3000], btype="bandpass", fs=SR, output="sos")

    def whiten(X: np.ndarray) -> np.ndarray:
        return X / (np.convolve(np.abs(X), np.ones(64) / 64, mode="same") + EPS)

    for a, b in segs:
        if b - a < 2.0:
            continue
        for s0 in np.arange(a, b - 2.0, 6.0):
            s1 = min(s0 + 8.0, b)
            seg = sosfiltfilt(sos, y[:, int(s0 * SR):int(s1 * SR)], axis=-1)
            n = seg.shape[1]
            if n <= lags[-1] + SR // 4:
                continue
            nfft = 1 << int(np.ceil(np.log2(2 * n)))
            for ch in (seg[0], seg[1], seg[0] + seg[1]):  # mid catches ping-pong echoes
                X = whiten(np.fft.rfft(ch, nfft))
                r = np.fft.irfft(np.abs(X) ** 2, nfft)[:lags[-1] + 1]
                acc += r[lags] / (r[0] + EPS)
                wsum += 1
    est = DelayEstimate()
    if wsum == 0:
        return est
    acc /= wsum
    excl, nb = int(0.002 * SR), int(0.03 * SR)

    def isolated_peaks(curve: np.ndarray) -> list[tuple[float, int, float]]:
        """(isolation ratio, index, height) of the strongest peaks; echoes are lone spikes,
        pitch periodicity produces a comb of similar peaks."""
        pk, _ = find_peaks(curve, distance=excl)
        top = pk[np.argsort(curve[pk])[::-1][:12]]
        res = []
        for i in top:
            neigh = np.r_[curve[max(0, i - nb):max(0, i - excl)], curve[i + excl:i + nb]]
            base = np.median(curve[max(0, i - nb):i + nb])
            if len(neigh) == 0:
                continue
            ratio = (curve[i] - base) / (neigh.max() - base + EPS)
            res.append((float(ratio), int(i), float(curve[i] - base)))
        return sorted(res, reverse=True)

    cands = [c for c in isolated_peaks(acc) if c[2] > 0.004]
    if not cands:
        return est
    ratio, i, height = max(cands, key=lambda c: c[0] * np.sqrt(c[2]))
    curve = acc
    est.strength = round(height, 4)
    est.time_ms = round(float(lags[i] * 1000 / SR), 1)
    est.detected = bool(ratio > 1.8 and height > 0.012)
    est.possible = bool(not est.detected and ratio > 1.5 and height > 0.006)
    if est.detected or est.possible:
        j = 2 * lags[i] - lags[0]
        if j < len(curve):
            near = curve[max(0, j - excl): j + excl + 1]
            est.feedback = round(float(np.clip(near.max() / (curve[i] + EPS), 0, 0.9)), 2)
        beat_ms = 60000 / max(tempo, 40)
        subs = {"1/4": 1, "dotted 1/8": 0.75, "1/8": 0.5, "1/4 triplet": 2 / 3, "1/8 triplet": 1 / 3,
                "dotted 1/4": 1.5, "1/16": 0.25, "1/2": 2}
        name, ratio = min(subs.items(), key=lambda kv: abs(kv[1] * beat_ms - est.time_ms))
        if abs(ratio * beat_ms - est.time_ms) / est.time_ms < 0.04:
            est.note = name
    return est


def estimate_reverb(mono: np.ndarray) -> ReverbEstimate:
    hop = 256
    env = librosa.feature.rms(y=mono, frame_length=1024, hop_length=hop)[0]
    env_db = 20 * np.log10(env + 1e-9)
    fps = SR / hop
    med = np.median(env_db)
    d60 = int(0.05 * fps)
    tails, slopes = [], []
    i = d60
    while i < len(env_db) - int(0.3 * fps):
        pre = env_db[i - d60]
        a, b = i + int(0.08 * fps), i + int(0.25 * fps)
        after = env_db[i:i + int(0.3 * fps)]
        # a real release: big drop and no new note right after (the next chord is not a tail)
        if pre > med and env_db[i] < pre - 10 and env_db[i - 1] >= pre - 10 and \
                np.max(after - np.minimum.accumulate(after)) < 3:
            tails.append(np.mean(env_db[a:b]) - pre)
            seg = env_db[i:b]
            slopes.append(np.polyfit(np.arange(len(seg)) / fps, seg, 1)[0])
            i = b
        else:
            i += 1
    est = ReverbEstimate()
    if len(tails) >= 4:
        est.tail_db = round(float(np.median(tails)), 1)
        sl = float(np.median(slopes))
        est.decay_s = round(float(np.clip(-60 / sl if sl < -1 else 5.0, 0.1, 5.0)), 2)
        est.amount = ("dry" if est.tail_db < -34 else "small" if est.tail_db < -27
                      else "medium" if est.tail_db < -20 else "large")
    return est


def build_profile(name: str, ws: list[Window], y: np.ndarray, tempo: float, center: bool) -> GroupProfile:
    ws_sorted = sorted(ws, key=lambda w: -w.rms_db)
    pick, total = [], 0.0
    for w in ws_sorted:  # loudest (least-bleed) windows, up to 60 s
        pick.append(w)
        total += w.end - w.start
        if total > 60:
            break
    segs = _merge_segments(pick)
    audio = np.concatenate([y[:, int(a * SR):int(b * SR)] for a, b in segs], axis=1)
    if center:
        audio = center_extract(audio)
    bands, tilt = _bands(audio)
    third, desc = _listening(audio)
    med = lambda k: float(np.median([getattr(w, k) for w in ws]))  # noqa: E731
    gain = med("gain")
    flat = med("flat_mid")
    # crunch vs high gain is only a rough hint (dense crunch chords also read as flat)
    gc = "clean" if gain < 0.42 else "crunch" if flat < 0.22 else "high_gain"
    width = med("width")
    stereo = ("wide/double-tracked" if width > 0.5 and med("corr") < 0.6 else
              "stereo" if width > 0.25 else "mono/centre")
    prof = GroupProfile(
        name=name, seconds=round(sum(w.end - w.start for w in ws), 1), segments=_merge_segments(ws),
        gain=round(gain, 2), gain_class=gc, flatness=round(flat, 3), width=round(width, 2), periodicity=round(med("periodicity"), 2),
        f0_median=round(med("f0"), 1), crest_db=round(med("crest_db"), 1), sustain=round(med("sustain"), 2),
        bands_db=bands, tilt_db_per_oct=tilt, third_oct_db=third, descriptors=desc, stereo=stereo)
    prof.delay = detect_delay(y, segs, tempo)
    prof.reverb = estimate_reverb(audio.mean(axis=0))
    if center:
        prof.notes.append("lead analysed on centre-extracted signal (rhythm guitars are wide)")
    return prof


# ------------------------------------------------------------------------------------------- track
@dataclass
class TrackAnalysis:
    tempo: float
    duration: float
    guitar_presence: float
    groups: dict[str, GroupProfile]
    windows: list[dict]

    def to_dict(self) -> dict:
        return {"tempo": self.tempo, "duration": self.duration, "guitar_presence": self.guitar_presence,
                "groups": {k: v.to_dict() for k, v in self.groups.items()}, "windows": self.windows}


def analyze(guitar_wav: Path, mix_wav: Path) -> TrackAnalysis:
    y = load_stereo(guitar_wav)
    mix = load_stereo(mix_wav)
    dur = y.shape[1] / SR
    mono_mix = librosa.resample(mix.mean(0), orig_sr=SR, target_sr=22050)
    tempo, beats = librosa.beat.beat_track(y=mono_mix, sr=22050, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    wins = make_windows(dur, np.asarray(beats), tempo)
    window_features(y, wins)
    mix_db = np.array([20 * np.log10(_rms(mix[:, int(w.start * SR):int(w.end * SR)].mean(0))) for w in wins])
    top = np.percentile([w.rms_db for w in wins], 95)
    for w, mdb in zip(wins, mix_db):
        # guitar must be clearly present: near its own loud level and not buried in the mix
        w.active = w.rms_db > top - 18 and w.rms_db > mdb - 20 and w.rms_db > -55
    presence = float(np.mean([w.active for w in wins])) if wins else 0.0
    clusters = cluster_windows(wins)
    named = name_groups(clusters)
    rhythm_wide = "rhythm" in named and np.median([w.width for w in named["rhythm"]]) > 0.35
    groups = {n: build_profile(n, ws, y, tempo, center=(n == "lead" and rhythm_wide))
              for n, ws in named.items() if sum(w.end - w.start for w in ws) >= 6}
    return TrackAnalysis(tempo=round(tempo, 1), duration=round(dur, 1), guitar_presence=round(presence, 2),
                         groups=groups, windows=[asdict(w) for w in wins])
