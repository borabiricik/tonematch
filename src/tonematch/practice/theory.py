"""Music theory for the practice system: notes, scales, chords, intervals, and where they sit on the fretboard.

Strings are numbered the guitarist's way: 1 = high E ... 6 = low E. Pitches are MIDI numbers (E2 = 40).
"""

from __future__ import annotations

from dataclasses import dataclass

SHARPS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLATS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
# keys written with flats (major-key name; a minor key uses its relative major)
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb"}

# open strings, string 1..6 (index 0 = string 1)
TUNINGS = {"EADGBE": (64, 59, 55, 50, 45, 40), "DADGBE": (64, 59, 55, 50, 45, 38)}
STANDARD = TUNINGS["EADGBE"]
MAX_FRET = 22

SCALES: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "natural_minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "major_pentatonic": (0, 2, 4, 7, 9),
    "blues": (0, 3, 5, 6, 7, 10),
}
SCALE_NAMES = {
    "major": "majör (iyonyen)", "natural_minor": "doğal minör (eolyen)", "dorian": "doryen", "phrygian": "frigyen",
    "lydian": "lidyen", "mixolydian": "miksolidyen", "locrian": "lokriyen", "harmonic_minor": "armonik minör",
    "melodic_minor": "melodik minör", "minor_pentatonic": "minör pentatonik", "major_pentatonic": "majör pentatonik",
    "blues": "blues",
}
CHORDS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7), "min": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
    "maj7": (0, 4, 7, 11), "min7": (0, 3, 7, 10), "dom7": (0, 4, 7, 10), "m7b5": (0, 3, 6, 10),
}
CHORD_SYMBOLS = {"maj": "", "min": "m", "dim": "dim", "aug": "+", "maj7": "maj7", "min7": "m7", "dom7": "7",
                 "m7b5": "m7♭5"}
# semitones -> (short, Turkish name)
INTERVALS = {
    1: ("m2", "küçük ikili"), 2: ("M2", "büyük ikili"), 3: ("m3", "küçük üçlü"), 4: ("M3", "büyük üçlü"),
    5: ("P4", "tam dörtlü"), 6: ("TT", "tritone"), 7: ("P5", "tam beşli"), 8: ("m6", "küçük altılı"),
    9: ("M6", "büyük altılı"), 10: ("m7", "küçük yedili"), 11: ("M7", "büyük yedili"), 12: ("P8", "oktav"),
}
# scale degree names for degree quizzes (semitones from the root)
DEGREES = {0: "1", 1: "♭2", 2: "2", 3: "♭3", 4: "3", 5: "4", 6: "♭5", 7: "5", 8: "♭6", 9: "6", 10: "♭7", 11: "7"}
# circle of fifths: the key of the day walks it, so every key comes round
CIRCLE = ("C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F")


def pc(name: str) -> int:
    """'C#' / 'Db' / 'c' -> pitch class 0..11."""
    n = name.strip()
    base = SHARPS.index(n[0].upper())
    for acc in n[1:]:
        base += {"#": 1, "♯": 1, "b": -1, "♭": -1}[acc]
    return base % 12


def note_name(midi_or_pc: int, flats: bool = False, octave: bool = False) -> str:
    n = (FLATS if flats else SHARPS)[midi_or_pc % 12]
    return f"{n}{midi_or_pc // 12 - 1}" if octave else n


def uses_flats(root: str, scale: str = "major") -> bool:
    """Spell a key with flats? A minor-ish scale is spelled like its relative major."""
    ivs = SCALES[scale]
    major_root = (pc(root) + 3) % 12 if 3 in ivs and 4 not in ivs else pc(root)  # A minor -> C major
    return note_name(major_root, flats=True) in FLAT_KEYS or root in FLAT_KEYS


def scale_pcs(root: str, scale: str) -> list[int]:
    r = pc(root)
    return [(r + i) % 12 for i in SCALES[scale]]


def fret_of(string: int, midi: int, tuning: tuple[int, ...] = STANDARD) -> int:
    return midi - tuning[string - 1]


def midi_of(string: int, fret: int, tuning: tuple[int, ...] = STANDARD) -> int:
    return tuning[string - 1] + fret


def frets_for_pc(string: int, pitch_class: int, lo: int = 0, hi: int = 12,
                 tuning: tuple[int, ...] = STANDARD) -> list[int]:
    return [f for f in range(lo, hi + 1) if (tuning[string - 1] + f) % 12 == pitch_class]


@dataclass(frozen=True)
class Pos:
    """One fretted note: string 1..6, fret, MIDI pitch."""
    string: int
    fret: int
    midi: int


def scale_position(root: str, scale: str, per_string: int, start_degree: int = 0, low_fret: int = 0,
                   tuning: tuple[int, ...] = STANDARD) -> list[Pos]:
    """A scale shape across all six strings, low E to high E, `per_string` notes on each string.

    Starts on string 6 at the first scale note of `start_degree` at or above `low_fret`, then simply keeps going
    up the scale, `per_string` notes per string. With 2 notes per string on a pentatonic scale this gives the five
    classic boxes (start_degree 0..4), with 3 per string on a 7-note scale the 3-note-per-string shapes; the
    major-third jump G -> B is handled by the pitches themselves."""
    ivs = SCALES[scale]
    r = pc(root)
    first_pc = (r + ivs[start_degree % len(ivs)]) % 12
    fret = next(f for f in range(low_fret, low_fret + 12) if (tuning[5] + f) % 12 == first_pc)
    midi = tuning[5] + fret
    # all scale pitches from that note upward
    deg = start_degree % len(ivs)
    pitches = []
    m = midi
    while len(pitches) < per_string * 6:
        pitches.append(m)
        nxt = (deg + 1) % len(ivs)
        step = (ivs[nxt] - ivs[deg]) % 12
        m += step
        deg = nxt
    out = []
    for i, p in enumerate(pitches):
        s = 6 - i // per_string
        out.append(Pos(s, p - tuning[s - 1], p))
    return out


def chord_tones(root: str, quality: str) -> list[int]:
    r = pc(root)
    return [(r + i) % 12 for i in CHORDS[quality]]


def chord_name(root: str, quality: str) -> str:
    return f"{root}{CHORD_SYMBOLS[quality]}"


def arpeggio_shape(root: str, quality: str, low_fret: int, strings: tuple[int, ...] = (6, 5, 4, 3, 2, 1),
                   per_string_max: int = 2, span: int = 5, tuning: tuple[int, ...] = STANDARD) -> list[Pos]:
    """Chord tones ascending across `strings` inside the fret box [low_fret, low_fret + span]: on each string the
    chord tones in the box that are above the previous note (at most per_string_max), giving the usual sweep /
    arpeggio fingerings (1 note per string on the middle strings, 2 on the outer ones when they fit)."""
    tones = set(chord_tones(root, quality))
    out: list[Pos] = []
    last = -1
    for s in strings:
        on = [f for f in range(low_fret, low_fret + span + 1) if (tuning[s - 1] + f) % 12 in tones
              and tuning[s - 1] + f > last][:per_string_max]
        for f in on:
            out.append(Pos(s, f, tuning[s - 1] + f))
            last = tuning[s - 1] + f
    return out
