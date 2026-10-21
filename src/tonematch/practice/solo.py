"""Solo trainer: a song's lead guitar -> tab phrases to practise slow-to-fast.

From the cached analysis (the "lead" group's segments) and the separated guitar stem:
  1. pitch   - pYIN on the stem (centre-extracted: the solo usually sits in the middle, rhythm guitars wide);
  2. notes   - split at onsets and at stable pitch changes (legato), short blips dropped; a pitch that glides
               more than a semitone inside one note is marked as a bend ("b", the fretted note is the start);
  3. rhythm  - onsets placed on the song's beat grid (beat tracking on the mix), snapped to 16ths or triplets;
  4. frets   - a Viterbi pass picks string/fret for every note: stay in one hand position, small moves, no open
               strings unless the line needs them;
  5. phrases - cut at rests of a beat or more, long ones halved at their largest gap (2-8 bars to loop).
Automatic transcription is a draft: the UI says so, and a wrong note costs one red mark, nothing else.

Saved to DATA_DIR/practice/solos/<track>.json; exercises "solo/<track>/<phrase>" are built from it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .theory import STANDARD

SR_T = 22050
HOP = 256
MIN_NOTE_S = 0.06
LEGATO_SEMIS = 0.7
BEND_SEMIS = 1.2
REST_BEATS = 1.0
MAX_PHRASE_BEATS = 16


def solos_dir() -> Path:
    from .progress import _dir

    d = _dir() / "solos"
    d.mkdir(exist_ok=True)
    return d


def solo_path(track_id: str) -> Path:
    return solos_dir() / f"{track_id}.json"


def load_solo(track_id: str) -> dict:
    p = solo_path(track_id)
    if not p.exists():
        raise ValueError(f"'{track_id}' için solo yok: önce `practice solo <şarkı>` ile çıkar")
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------- notes
def notes_from_pitch(f0: np.ndarray, voiced: np.ndarray, onsets: np.ndarray, t0: float, fps: float) -> list[dict]:
    """Frame pitch track (Hz, nan = unvoiced) + onset times -> notes {t, end, midi, bend}."""
    midi = np.where(voiced & ~np.isnan(f0), 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0), np.nan)
    onset_frames = set(int(round((t - t0) * fps)) for t in onsets)
    notes: list[dict] = []
    cur: list[float] = []
    start = None

    def close(end_i: int) -> None:
        if start is None or not cur:
            return
        dur = (end_i - start) / fps
        if dur < MIN_NOTE_S:
            return
        arr = np.array(cur)
        head = float(np.median(arr[: max(3, len(arr) // 4)]))
        bend = float(np.max(arr) - head) >= BEND_SEMIS
        notes.append({"t": t0 + start / fps, "end": t0 + end_i / fps, "midi": int(round(head if bend else np.median(arr))),
                      "bend": bend})

    for i, m in enumerate(midi):
        if np.isnan(m):
            close(i)
            start, cur = None, []
            continue
        if start is None:
            start, cur = i, [m]
            continue
        ref = float(np.median(cur[-6:]))
        new_onset = i in onset_frames and i - start > 2
        # a stable jump (3 frames) is a new note; a glide is a bend and stays in the note
        jump = abs(m - ref) >= LEGATO_SEMIS and i + 2 < len(midi) and not np.isnan(midi[i + 2]) \
            and abs(midi[i + 2] - m) < 0.5 and abs(midi[i + 1] - m) < 0.5 and not _gliding(cur)
        if new_onset or jump:
            close(i)
            start, cur = i, [m]
        else:
            cur.append(m)
    close(len(midi))
    return notes


def _gliding(cur: list[float]) -> bool:
    """The last frames move steadily one way: a bend or slide in progress, not a new fretted note."""
    if len(cur) < 4:
        return False
    d = np.diff(cur[-4:])
    return bool(np.all(d > 0.08) or np.all(d < -0.08))


# --------------------------------------------------------------------------------------------- rhythm
def to_beats(times: np.ndarray, beat_times: np.ndarray) -> np.ndarray:
    """Seconds -> beat positions along the tracked beats (tempo drift follows), extrapolated at the ends."""
    idx = np.arange(len(beat_times), dtype=float)
    if len(beat_times) < 2:
        return times * 2.0
    spb0 = beat_times[1] - beat_times[0]
    spb1 = beat_times[-1] - beat_times[-2]
    out = np.interp(times, beat_times, idx)
    out = np.where(times < beat_times[0], (times - beat_times[0]) / spb0, out)
    out = np.where(times > beat_times[-1], idx[-1] + (times - beat_times[-1]) / spb1, out)
    return out


def snap(beat: float) -> float:
    """To the nearest 16th or triplet, preferring 16ths unless the triplet is clearly closer."""
    q4 = round(beat * 4) / 4
    q3 = round(beat * 3) / 3
    return q3 if abs(beat - q3) + 0.02 < abs(beat - q4) else q4


# ----------------------------------------------------------------------------------------------- frets
def assign_frets(midis: list[int], tuning: tuple[int, ...] = STANDARD, max_fret: int = 20) -> list[tuple[int, int]]:
    """(string, fret) per note by Viterbi over hand positions: the index finger sits at fret p and covers p..p+3,
    so a line stays in one position until it has to shift (a shift costs; small shifts less). Open strings only
    when nothing fretted is near, frets above 17 discouraged."""
    states = []
    for m in midis:
        st = []
        for s in range(1, 7):
            f = m - tuning[s - 1]
            if not 0 <= f <= max_fret:
                continue
            for p in (range(1, 15) if f == 0 else range(max(1, f - 3), f + 1)):
                st.append((s, f, p))
        states.append(st or [(1, max(0, min(max_fret, m - tuning[0]))) + (1,)])

    def own(x: tuple[int, int, int]) -> float:
        s, f, p = x
        return (1.5 if f == 0 else 0.0) + (0.4 * (f - 17) if f > 17 else 0.0) + 0.02 * p

    def move(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
        return (0.0 if a[2] == b[2] else 1.0 + 0.25 * abs(a[2] - b[2])) + 0.05 * abs(a[0] - b[0])

    cost = [own(x) for x in states[0]]
    back: list[list[int]] = []
    for i in range(1, len(states)):
        new, bk = [], []
        for x in states[i]:
            opts = [cost[j] + move(y, x) for j, y in enumerate(states[i - 1])]
            j = int(np.argmin(opts))
            new.append(opts[j] + own(x))
            bk.append(j)
        cost, back = new, back + [bk]
    j = int(np.argmin(cost))
    path = [j]
    for bk in reversed(back):
        j = bk[j]
        path.append(j)
    path.reverse()
    return [states[i][k][:2] for i, k in enumerate(path)]


# --------------------------------------------------------------------------------------------- phrases
def phrases(notes: list[dict]) -> list[list[dict]]:
    """Split at rests >= REST_BEATS; halve phrases longer than MAX_PHRASE_BEATS at their largest gap."""
    if not notes:
        return []
    out, cur = [], [notes[0]]
    for a, b in zip(notes, notes[1:]):
        if b["beat"] - (a["beat"] + a["dur"]) >= REST_BEATS:
            out.append(cur)
            cur = [b]
        else:
            cur.append(b)
    out.append(cur)
    done = []
    stack = out[::-1]
    while stack:
        ph = stack.pop()
        span = ph[-1]["beat"] + ph[-1]["dur"] - ph[0]["beat"]
        if span <= MAX_PHRASE_BEATS or len(ph) < 8:
            done.append(ph)
            continue
        gaps = [ph[i + 1]["beat"] - ph[i]["beat"] for i in range(2, len(ph) - 3)]
        k = 2 + int(np.argmax(gaps)) + 1
        stack += [ph[k:], ph[:k]]
    return done


def build_phrase_notes(ph: list[dict]) -> tuple[list[dict], int, float]:
    """Phrase notes relative to the bar line before it: (notes, loop beats, start beat in the song)."""
    start = math.floor(ph[0]["beat"])
    notes = []
    for n in ph:
        notes.append({"beat": round(n["beat"] - start, 4), "dur": round(n["dur"], 4), "string": n["string"],
                      "fret": n["fret"], "midi": n["midi"], "tech": n["tech"]})
    beats = int(math.ceil(ph[-1]["beat"] + ph[-1]["dur"] - start))
    return notes, max(1, beats), start


# ------------------------------------------------------------------------------------------------- run
def transcribe(source: str, role: str = "lead", say=None) -> dict:
    """Transcribe the song's lead parts (cached analysis + stems; downloads/separates on first use)."""
    import librosa

    from ..analysis import center_extract, load_stereo
    from ..ingest import track_dir
    from ..pipeline import prepare

    say = say or (lambda msg: None)
    tid, meta, ana = prepare(source)
    if role not in ana.groups:
        raise RuntimeError(f"bu şarkıda '{role}' bölümü bulunamadı; mevcut: {', '.join(ana.groups)}")
    d = track_dir(tid)
    stems = json.loads((d / "stems" / "model.json").read_text())["stems"]
    say("vuruşlar bulunuyor ...")
    mix = librosa.load(str(d / "source.wav"), sr=SR_T, mono=True)[0]
    tempo, beat_times = librosa.beat.beat_track(y=mix, sr=SR_T, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    y = load_stereo(Path(stems["guitar"]))
    segs = ana.groups[role].segments
    raw: list[dict] = []
    for a, b in segs:
        say(f"{a // 60:.0f}:{a % 60:04.1f}-{b // 60:.0f}:{b % 60:04.1f} notalar çıkarılıyor ...")
        lo, hi = max(0, int((a - 0.2) * 44100)), int((b + 0.2) * 44100)
        part = center_extract(y[:, lo:hi])[0]
        part = librosa.resample(part, orig_sr=44100, target_sr=SR_T)
        f0, voiced, prob = librosa.pyin(part, fmin=75, fmax=1400, sr=SR_T, frame_length=2048, hop_length=HOP)
        voiced = voiced & (prob > 0.4)
        ons = librosa.onset.onset_detect(y=part, sr=SR_T, hop_length=HOP, units="time", backtrack=True)
        raw += notes_from_pitch(f0, voiced, lo / 44100 + ons, lo / 44100, SR_T / HOP)
    raw.sort(key=lambda n: n["t"])
    if not raw:
        raise RuntimeError("lead bölümünde nota bulunamadı")
    beats = to_beats(np.array([n["t"] for n in raw]), beat_times)
    ends = to_beats(np.array([n["end"] for n in raw]), beat_times)
    frets = assign_frets([n["midi"] for n in raw])
    notes = []
    for n, b, e, (s, f) in zip(raw, beats, ends, frets):
        bs = snap(float(b))
        if notes and bs <= notes[-1]["beat"]:  # two onsets on one grid step: keep the first
            continue
        dur = max(0.25, round((float(e) - float(b)) * 4) / 4)
        notes.append({"beat": bs, "dur": dur, "string": s, "fret": f, "midi": n["midi"],
                      "tech": "b" if n["bend"] else "", "t": round(n["t"], 3)})
    for a, b in zip(notes, notes[1:]):  # a note lasts until the next one at most
        a["dur"] = round(min(a["dur"], b["beat"] - a["beat"]), 4)
    out_phrases = []
    for i, ph in enumerate(phrases(notes)):
        pn, nbeats, start = build_phrase_notes(ph)
        out_phrases.append({"index": i, "notes": pn, "beats": nbeats, "start_beat": start,
                            "start_s": ph[0]["t"], "end_s": round(ph[-1]["t"] + 0.5, 2), "count": len(pn)})
    doc = {"track_id": tid, "title": meta.get("title", ""), "artist": meta.get("artist", ""), "role": role,
           "tempo": round(tempo, 1), "phrases": out_phrases, "guitar": stems["guitar"]}
    solo_path(tid).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def list_solos() -> list[dict]:
    out = []
    for p in sorted(solos_dir().glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({k: d[k] for k in ("track_id", "title", "artist", "tempo", "role")}
                   | {"phrases": [{"index": ph["index"], "beats": ph["beats"], "count": ph["count"],
                                   "start_s": ph["start_s"]} for ph in d["phrases"]]})
    return out


def reference(track_id: str, index: int, speed: float) -> np.ndarray:
    """The phrase as played on the record (centre of the guitar stem), slowed to `speed` (pitch kept)."""
    import librosa

    from ..analysis import center_extract, load_stereo

    doc = load_solo(track_id)
    ph = doc["phrases"][index]
    y = load_stereo(Path(doc["guitar"]))
    lo, hi = int(max(0, ph["start_s"] - 0.1) * 44100), int(ph["end_s"] * 44100)
    part = center_extract(y[:, lo:hi])[0]
    if abs(speed - 1) > 0.01:
        part = librosa.effects.time_stretch(part, rate=speed)
    return (0.8 * part / (np.max(np.abs(part)) + 1e-9)).astype(np.float32)
