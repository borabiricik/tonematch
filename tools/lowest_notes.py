"""Dev tool: lowest-note histogram + per-note salience/contrast of a cached track (tuning calibration)."""

import sys

import librosa
import numpy as np

from tonematch.config import TRACKS_DIR
from tonematch.tuning import FMIN_MIDI, SR_T, _salience, midi_name

d = TRACKS_DIR / sys.argv[1]
y, _ = librosa.load(str(d / "stems" / "guitar.wav"), sr=SR_T, mono=True)
yh = librosa.effects.harmonic(y, margin=2.0)
tf = float(librosa.estimate_tuning(y=yh, sr=SR_T, bins_per_octave=36))
sal, energy = _salience(yh, tf)
act = energy > np.percentile(energy, 40)
S = sal[:, act]
for thr_rel in (0.45, 0.7):
    h = np.zeros(S.shape[0])
    for j in range(S.shape[1]):
        col = S[:, j]
        pk = np.where((col >= thr_rel * col.max()) & (col >= np.r_[np.inf, col[:-1]]) & (col >= np.r_[col[1:], 0]))[0]
        if len(pk):
            h[pk[0]] += 1
    h /= h.sum()
    top = np.argsort(h)[::-1][:8]
    print(f"thr {thr_rel}: lowest-note share", ", ".join(f"{midi_name(i + FMIN_MIDI)} {h[i]:.2f}" for i in sorted(top)))
if (d / "stems" / "bass.wav").exists():
    b, _ = librosa.load(str(d / "stems" / "bass.wav"), sr=SR_T, mono=True)
    bs, be = _salience(librosa.effects.harmonic(b, margin=2.0), tf)
    bt = bs[:, be > np.percentile(be, 40)].mean(axis=1)
    print("bass stem salience:", " ".join(f"{midi_name(i + FMIN_MIDI)}:{bt[i] / bt.max():.2f}" for i in range(0, 20)))
tot = S.mean(axis=1)
print("tuning", round(tf * 100), "c | mean salience 33..60:",
      " ".join(f"{midi_name(i + FMIN_MIDI)}:{tot[i] / tot.max():.2f}" for i in range(0, 28)))
