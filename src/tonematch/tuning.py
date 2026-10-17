"""Song tuning -> GT-1 pitch shift.

The user names the song's tuning (`parse_tuning`, CLI `--tuning`); without it the song is taken as
E standard (no shifter). Automatic detection below is OFF in the app (user decision 2026-10-17) and is
kept only for the dev tools (tools/tuning_evidence.py).

Guitar tuning detection: which tuning the recording's guitar is in, and how far the user's guitar
(EADGBE or DADGBE) must be pitch-shifted on the GT-1 to match it.

Evidence (all from the isolated guitar stem + the mix):
  1. lowest notes  - per frame, the lowest salient pitch (CQT + harmonic summation). Riffs keep coming
                     back to the open low string; nothing can sound below it.
  2. open strings  - pitches of a tuning's open strings stand out (ringing, pedal tones).
  3. key           - songs sit in keys that are comfortable on the tuning (E/A/D/G/C shapes).
  4. A4 reference  - fine detune of the whole recording (cents), applied with the shifter's FINE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import librosa
import numpy as np

SR_T = 22050
FMIN_MIDI = 33          # A1: lowest note we look at (7-string / drop A territory)
N_OCT = 4              # A1..A5 searched for notes; +3 octaves above for the 5 harmonics (7 kHz < Nyquist)
BPO = 36                # 3 bins per semitone

# name -> (open strings low..high as MIDI, user tuning to use, semitone shift for the GT-1)
TUNINGS: dict[str, tuple[list[int], str, int]] = {
    "E standard":  ([40, 45, 50, 55, 59, 64], "EADGBE", 0),
    "Eb standard": ([39, 44, 49, 54, 58, 63], "EADGBE", -1),
    "D standard":  ([38, 43, 48, 53, 57, 62], "EADGBE", -2),
    "C# standard": ([37, 42, 47, 52, 56, 61], "EADGBE", -3),
    "C standard":  ([36, 41, 46, 51, 55, 60], "EADGBE", -4),
    "B standard":  ([35, 40, 45, 50, 54, 59], "EADGBE", -5),
    "Drop D":      ([38, 45, 50, 55, 59, 64], "DADGBE", 0),
    "Drop C#":     ([37, 44, 49, 54, 58, 63], "DADGBE", -1),
    "Drop C":      ([36, 43, 48, 53, 57, 62], "DADGBE", -2),
    "Drop B":      ([35, 42, 47, 52, 56, 61], "DADGBE", -3),
    "Drop A#":     ([34, 41, 46, 51, 55, 60], "DADGBE", -4),
    "Drop A":      ([33, 40, 45, 50, 54, 59], "DADGBE", -5),
}
# tonic pitch classes (in "shape" terms, i.e. as played in E standard / drop D) that guitarists favour
FRIENDLY_MAJOR = {4: 1.0, 9: 1.0, 2: 0.9, 7: 0.9, 0: 0.6}          # E A D G C
FRIENDLY_MINOR = {4: 1.0, 9: 1.0, 2: 0.8, 11: 0.7, 6: 0.6, 7: 0.5}  # Em Am Dm Bm F#m Gm

KRUMHANSL_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KRUMHANSL_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTE = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


@dataclass
class TuningEstimate:
    name: str
    user_tuning: str          # "EADGBE" or "DADGBE"
    semitones: int            # GT-1 pitch shift
    cents: int                # GT-1 fine (recording's deviation from A440)
    confidence: float         # 0..1 (score margin to the runner-up)
    key: str
    lowest_note: str
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    uncertain: bool = False   # detection not trustworthy -> no shift applied, user is warned
    best_guess: str = ""      # what the detector would have picked when uncertain

    @property
    def needs_shift(self) -> bool:
        # user's guitar is EADGBE or DADGBE: those tunings never get a pitch shifter (user rule)
        return self.semitones != 0

    def to_dict(self) -> dict:
        return asdict(self)


STANDARD = [40, 45, 50, 55, 59, 64]   # EADGBE
DROP_D = [38, 45, 50, 55, 59, 64]     # DADGBE
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _parse_notes(text: str) -> list[int]:
    """'EADGBE', 'D#G#C#F#A#D#', 'Eb Ab Db Gb Bb Eb', 'C G C F A D' -> 6 pitch classes, low to high."""
    import re

    t = text.strip().replace("♯", "#").replace("♭", "b")
    if not any(c.isupper() for c in t):
        t = t.upper()          # 'eadgbe': no flats possible to tell apart from B, read as note names
    notes = re.findall(r"([A-G])([#b]?)", t)
    if "".join(a + b for a, b in notes) != re.sub(r"[\s,/-]", "", t):
        raise ValueError(f"akort okunamadı: {text!r} (örnek: EADGBE, DADGBE, D#G#C#F#A#D#, CGCFAD)")
    if len(notes) != 6:
        raise ValueError(f"6 tel bekleniyordu, {len(notes)} nota bulundu: {text!r}")
    return [(_PC[a] + (1 if b == "#" else -1 if b == "b" else 0)) % 12 for a, b in notes]


def parse_tuning(text: str) -> TuningEstimate:
    """User-given song tuning -> which tuning the user plays in (EADGBE / DADGBE) and the GT-1 shift.

    The song tuning must be EADGBE or DADGBE moved as a whole by k semitones (k = -9..+2, i.e. down to G
    standard / drop F, up to F# standard); open tunings etc. cannot be reached with one pitch shifter.
    """
    pcs = _parse_notes(text)
    for ref, user in ((STANDARD, "EADGBE"), (DROP_D, "DADGBE")):
        ks = {((p - r % 12) + 9) % 12 - 9 for p, r in zip(pcs, ref)}
        if len(ks) == 1:
            k = ks.pop()
            low = ref[0] + k
            name = "".join(c for c in text if not c.isspace() and c not in ",/-")
            return TuningEstimate(name=name, user_tuning=user, semitones=k, cents=0, confidence=1.0,
                                  key="", lowest_note=midi_name(low), evidence={"source": "user"})
    raise ValueError(f"{text!r}: EADGBE ya da DADGBE'nin tamamen kaydırılmış hali değil "
                     f"(açık akortlar tek pitch shifter ile yapılamaz)")


E_STANDARD = TuningEstimate("EADGBE", "EADGBE", 0, 0, 1.0, "", "E2", evidence={"source": "default"})


def midi_name(m: int) -> str:
    return f"{NOTE[m % 12]}{m // 12 - 1}"


def _salience(y: np.ndarray, tuning_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame salience per semitone (MIDI FMIN_MIDI..), harmonic summation over a CQT."""
    # start 1/3 semitone low so each semitone's 3 bins are centred on it: [-1/3, 0, +1/3]
    fmin = librosa.midi_to_hz(FMIN_MIDI) * 2 ** (-1 / BPO)
    C = np.abs(librosa.cqt(y, sr=SR_T, hop_length=1024, fmin=fmin, n_bins=BPO * (N_OCT + 3),
                           bins_per_octave=BPO, tuning=tuning_frac))
    C = C / (C.max() + 1e-12)
    n_bins = BPO * N_OCT
    # Geometric mean over harmonics 1..4: a real guitar note needs its whole harmonic series. Bass-guitar
    # bleed in the stem is mostly a bare fundamental and must not count as a low guitar note
    # (calibration: Master of Puppets showed B1/C2 "notes" below the E standard low string).
    logsum = np.zeros((n_bins, C.shape[1]))
    for h in range(1, 5):
        off = int(round(BPO * np.log2(h)))
        logsum += np.log(C[off:off + n_bins] + 1e-4)
    sal = np.exp(logsum / 4)
    # collapse 3 bins -> 1 semitone (centre bin carries the tuned pitch)
    semis = sal.reshape(N_OCT * 12, 3, -1).max(axis=1)
    energy = C[:n_bins].sum(axis=0)
    return semis, energy


def _key(mix: np.ndarray) -> tuple[int, str, float]:
    chroma = librosa.feature.chroma_cqt(y=mix, sr=SR_T, hop_length=2048).mean(axis=1)
    best = (-np.inf, 0, "major")
    for t in range(12):
        for prof, mode in ((KRUMHANSL_MAJ, "major"), (KRUMHANSL_MIN, "minor")):
            r = np.corrcoef(chroma, np.roll(prof, t))[0, 1]
            if r > best[0]:
                best = (r, t, mode)
    return best[1], best[2], float(best[0])


def extract_features(guitar_wav: Path, mix_wav: Path, bass_wav: Path | None = None) -> dict:
    """The expensive part (CQT, key). JSON-serialisable so scoring can be calibrated offline."""
    y, _ = librosa.load(str(guitar_wav), sr=SR_T, mono=True)
    mix, _ = librosa.load(str(mix_wav), sr=SR_T, mono=True)
    yh = librosa.effects.harmonic(y, margin=2.0)
    tuning_frac = float(librosa.estimate_tuning(y=yh, sr=SR_T, bins_per_octave=36))
    sal, energy = _salience(yh, tuning_frac)
    keep = energy > np.percentile(energy, 40)
    S = sal[:, keep]
    B = None
    if bass_wav is not None and Path(bass_wav).exists():
        b, _ = librosa.load(str(bass_wav), sr=SR_T, mono=True)
        bsal, _ = _salience(librosa.effects.harmonic(b, margin=2.0), tuning_frac)
        n = min(bsal.shape[1], sal.shape[1])
        B = bsal[:, :n][:, keep[:n]]
    low_hist = np.zeros(S.shape[0])
    for j in range(S.shape[1]):
        col = S[:, j]
        # np.inf on the left: the lowest bin must not count as a peak just because it is the edge
        peaks = np.where((col >= 0.45 * col.max()) & (col >= np.r_[np.inf, col[:-1]]) & (col >= np.r_[col[1:], 0]))[0]
        if B is not None and j < B.shape[1]:
            bc = B[:, j]
            # bass-guitar bleed: a low "note" the bass plays loudly right now but the guitar only weakly
            peaks = [p for p in peaks if not (bc[p] >= 0.5 * (bc.max() + 1e-12) and col[p] < 0.6 * col.max())]
        if len(peaks):
            low_hist[peaks[0]] += 1
    total = S.mean(axis=1)
    tonic, mode, _ = _key(mix)
    return {"cents": int(round(tuning_frac * 100)), "tonic": tonic, "mode": mode,
            "low_share": (low_hist / max(low_hist.sum(), 1)).round(4).tolist(),
            "salience": (total / (total.max() + 1e-12)).round(4).tolist()}


# A "family" k = standard tuning moved by k semitones on strings 2..6. Its low string is either standard
# (40+k) or dropped a whole tone (38+k): e.g. k=-1 -> Eb standard / Drop C#. Strings 2..6 are identical
# within a family, so only low-string evidence can tell standard from drop - and when the song never
# plays the low string, both give the same notes (the choice does not matter for the pitch shift).
FAMILIES = {0: ("E standard", "Drop D"), -1: ("Eb standard", "Drop C#"), -2: ("D standard", "Drop C"),
            -3: ("C# standard", "Drop B"), -4: ("C standard", "Drop A#"), -5: ("B standard", "Drop A")}
# how common the families are; B standard / Drop A (k=-5) and C standard / Drop A# (k=-4) are rare, while
# Drop B (k=-3) is a metal staple - the deciding cue for Duality (Drop B), where both read B1 as low string
FAMILY_PRIOR = {0: 0.35, -1: 0.2, -2: 0.15, -3: 0.05, -4: -0.1, -5: -0.15}


def score_tunings(f: dict) -> TuningEstimate:
    low, sal = np.array(f["low_share"]), np.array(f["salience"])
    tonic, mode, cents = f["tonic"], f["mode"], f["cents"]
    ix = lambda m: m - FMIN_MIDI  # noqa: E731
    lowest_obs = int(np.argmax(low)) + FMIN_MIDI

    fam_scores: dict[int, float] = {}
    for k in FAMILIES:
        std_low, drop_low = 40 + k, 38 + k
        # ringing open strings 2..5 (A D G B moved by k); string 2 carries most power chords
        upper = float(np.average([sal[ix(n + k)] for n in (45, 50, 55, 59)], weights=(2.0, 1.0, 1.0, 0.5)))
        # the low string (either variant) showing up as the lowest note
        low_ev = float(max(low[ix(std_low)], low[ix(drop_low)]))
        # lowest notes 1..3 semitones under even the dropped string point to a lower family - but only
        # when they dominate this family's own low string (bass-guitar bleed sits there at a lower level:
        # Master of Puppets B1/C2 0.14 vs E2 0.32)
        below = max(0.0, float(low[max(0, ix(drop_low) - 3):ix(drop_low)].max(initial=0)) - low_ev)
        shape_tonic = (tonic - k) % 12
        friendly = (FRIENDLY_MAJOR if mode == "major" else FRIENDLY_MINOR).get(shape_tonic, 0.0)
        fam_scores[k] = round(2.0 * upper + 3.0 * low_ev + 0.5 * friendly - 4.0 * below + FAMILY_PRIOR[k], 3)
    ranked = sorted(fam_scores.items(), key=lambda kv: -kv[1])
    k, best = ranked[0]
    conf = float(np.clip((best - ranked[1][1]) / 0.5, 0, 1))
    if abs(cents) >= 40:
        # recording sits ~half way between semitones (e.g. sped-up tape): note names are ambiguous
        conf = min(conf, 0.3)

    # standard vs drop inside the family: low-string evidence only (default standard)
    std_low, drop_low = 40 + k, 38 + k
    drop_ev = low[ix(drop_low)] + 0.5 * low[ix(drop_low + 1)]   # fret 1 on a dropped string
    std_ev = low[ix(std_low)]
    is_drop = drop_ev >= 0.08 and drop_ev > 0.6 * std_ev
    name = FAMILIES[k][1 if is_drop else 0]
    _, user, semis = TUNINGS[name]
    if semis != 0 and (abs(cents) >= 40 or conf < 0.2):
        # Safety: a recording half way between semitones (Smoke on the Water, -48 c) or a near tie must not
        # silently retune the guitar. Fall back to the user's tuning family, no shifter, and say so.
        d2, e2 = low[ix(38)], low[ix(40)]
        fallback = "Drop D" if d2 >= 0.15 and d2 > e2 else "E standard"
        return TuningEstimate(name=fallback, user_tuning=TUNINGS[fallback][1], semitones=0, cents=0,
                              confidence=round(conf, 2), key=f"{NOTE[tonic]} {mode}",
                              lowest_note=midi_name(lowest_obs), uncertain=True, best_guess=name,
                              scores={FAMILIES[kk][0] + " fam": v for kk, v in ranked[:4]})
    return TuningEstimate(name=name, user_tuning=user, semitones=semis, cents=cents if abs(cents) >= 10 else 0,
                          confidence=round(conf, 2), key=f"{NOTE[tonic]} {mode}", lowest_note=midi_name(lowest_obs),
                          scores={FAMILIES[kk][0] + " fam": v for kk, v in ranked[:4]})


def detect_tuning(guitar_wav: Path, mix_wav: Path, bass_wav: Path | None = None) -> TuningEstimate:
    return score_tunings(extract_features(guitar_wav, mix_wav, bass_wav))
