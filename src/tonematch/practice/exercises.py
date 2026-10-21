"""Exercises: generated note lists (tab) with tempo, subdivision and a teacher's notes.

Every exercise is built from an id: "<family>/<param>/<param>..." (e.g. "pent/A/1" = A minor pentatonic box 1).
The family decides the notes; the params pick key / shape / pattern. Progress is kept per *skill* (the id without
the key): speed on a shape does not depend on which fret it starts on, so moving the key keeps the record.

Notes are dicts the UI draws as tab: {"beat", "dur", "string", "fret", "midi", "tech"}; tech is "" (picked),
"h" (hammer-on), "p" (pull-off), "d"/"u" (down / up stroke where the direction is the point: sweeps).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import permutations

from .theory import (CIRCLE, SCALE_NAMES, SCALES, STANDARD, Pos, arpeggio_shape, chord_name, midi_of,
                     scale_position)

BEATS_PER_BAR = 4


@dataclass
class Exercise:
    id: str
    skill: str
    family: str
    group: str            # menu section (Isınma, Alternate picking, ...)
    title: str
    subtitle: str
    per_beat: int         # notes per beat (2 = 8ths, 3 = triplets, 4 = 16ths, 6 = sextuplets)
    bpm: int              # suggested starting tempo
    goal_bpm: int         # a sensible "this is fluent" tempo
    notes: list[dict]
    beats: int            # loop length; the UI draws a bar line every BEATS_PER_BAR
    level: int            # 1 easy .. 5 hard
    tips: list[str] = field(default_factory=list)
    focus: str = ""       # one line shown while playing
    key: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _line(positions: list[Pos | None], per_beat: int, techs: list[str] | None = None) -> tuple[list[dict], int]:
    """Place notes one per subdivision step (None = rest). Returns (notes, loop length in whole beats)."""
    dur = 1 / per_beat
    notes = []
    for i, p in enumerate(positions):
        if p is None:
            continue
        notes.append({"beat": round(i * dur, 4), "dur": round(dur, 4), "string": p.string, "fret": p.fret,
                      "midi": p.midi, "tech": techs[i] if techs else ""})
    return notes, max(1, -(-len(positions) // per_beat))


def _pos(string: int, fret: int) -> Pos:
    return Pos(string, fret, midi_of(string, fret))


def _up_down(seq: list[Pos]) -> list[Pos]:
    """Up and back down without repeating the top note; the loop returns to the first note."""
    return seq + seq[-2:0:-1]


def _pad(seq: list, per_beat: int) -> list:
    """Rests up to the end of the beat, so the next loop starts on a beat."""
    return seq + [None] * (-len(seq) % per_beat)


def _groups(seq: list[Pos], n: int) -> list[Pos]:
    """Scale sequence in groups of n: 1234 2345 3456 ..."""
    return [p for i in range(len(seq) - n + 1) for p in seq[i:i + n]]


# ------------------------------------------------------------------------------------------------- families
FINGER_TIPS = [
    "Parmakları perdeye dik bas, hemen tel telin arkasına; basmadığın parmaklar telin üstünde 1–2 mm beklesin.",
    "Hız değil temizlik: her nota ayrı ayrı ve eşit sesle duyulmalı. Hatasız çalabildiğin en hızlı tempo senin temponun.",
]
PICK_TIPS = [
    "Pena hareketi küçük: bilekten, telin 2–3 mm ötesine kadar. Büyük hareket hızın tavanıdır.",
    "Aşağı-yukarı hiç bozulmasın (alternate). İlk notayı aşağı başla, tel değişiminde de sırayı koru.",
    "Sol el ile pena aynı anda inmeli; ses 'tık' değil 'tak' gibi tek vuruş gelmeli. Senkron kaçınca tempo düşür.",
]


def chromatic(pattern: str = "1234", fret: int = 1) -> Exercise:
    """Chromatic walk: the finger pattern on each string, up to string 1, one fret higher and back down."""
    offs = [int(c) - 1 for c in pattern]
    up = [_pos(s, fret + o) for s in range(6, 0, -1) for o in offs]
    down = [_pos(s, fret + 1 + o) for s in range(1, 7) for o in offs]
    notes, beats = _line(up + down, 4)
    perm = pattern != "1234"
    return Exercise(
        id=f"chromatic/{pattern}/{fret}", skill=f"chromatic/{pattern}", family="chromatic",
        group="Isınma", title=f"Kromatik {'permütasyon ' if perm else ''}{'-'.join(pattern)}",
        subtitle=f"{fret}. perdeden, 16'lık, her telde 4 parmak", per_beat=4, bpm=60, goal_bpm=120,
        notes=notes, beats=beats, level=1 if not perm else 2,
        tips=FINGER_TIPS + ([f"{pattern} sırası zayıf parmakları (3 ve 4) bağımsız çalıştırır; yavaşken bile atlama."]
                            if perm else ["Her gün ilk iş: 2–3 dakika, rahat tempoda. Ellerin ısınmadan hız deneme."]),
        focus="Parmak ekonomisi: kalkan parmak telin üstünde beklesin")


def tremolo(string: int = 3, fret: int = 7, per_beat: int = 4) -> Exercise:
    """One note, continuous alternate picking: the picking hand alone, the base of every fast run."""
    notes, beats = _line([_pos(string, fret)] * (per_beat * 8), per_beat)
    sub = {4: "16'lık", 6: "6'lık (sextuplet)"}[per_beat]
    return Exercise(
        id=f"tremolo/{per_beat}", skill=f"tremolo/{per_beat}", family="tremolo", group="Alternate picking",
        title=f"Tek nota tremolo · {sub}", subtitle=f"{string}. tel {fret}. perde, 2 ölçü, sürekli aşağı-yukarı",
        per_beat=per_beat, bpm=80 if per_beat == 4 else 60, goal_bpm=160 if per_beat == 4 else 120,
        notes=notes, beats=beats, level=1,
        tips=PICK_TIPS[:1] + ["Vuruşu ayağınla say, her vuruşun ilk notasına hafif aksan ver: el saati içselleştirir.",
                              "Omuz ve önkol gevşek kalsın; sertleşince dur, silkele, sonra devam."],
        focus="Eşit vuruşlar, ilk notaya hafif aksan")


def three_nps(key: str = "A", scale: str = "natural_minor", degree: int = 0, legato: bool = False) -> Exercise:
    """A 3-note-per-string shape up and down in triplets (one string per beat)."""
    shape = scale_position(key, scale, 3, degree, low_fret=_low_fret(key, scale, degree))
    seq = _pad(_up_down(shape), 3)
    techs = None
    if legato:
        # pick the first note on each string; the rest hammer (up) or pull (down)
        techs = []
        prev = None
        for p in seq:
            techs.append("" if p is None or prev is None or p.string != prev.string
                         else ("h" if p.midi > prev.midi else "p"))
            prev = p
    notes, beats = _line(seq, 3, techs)
    fam = "legato3nps" if legato else "3nps"
    return Exercise(
        id=f"{fam}/{key}/{scale}/{degree}", skill=f"{fam}/{scale}/{degree}", family=fam,
        group="Legato" if legato else "Gam & pozisyon",
        title=f"{key} {SCALE_NAMES[scale]} · 3 nota/tel{' legato' if legato else ''}",
        subtitle=f"{degree + 1}. dereceden başlayan şekil, triplet: her vuruş bir tel", per_beat=3,
        bpm=60 if legato else 70, goal_bpm=140, notes=notes, beats=beats, level=3 if legato else 2, key=key,
        tips=(["Sadece telin ilk notasını penala; çekiç (h) sert ve perdenin hemen arkasına, çekme (p) teli hafif "
               "aşağı çekerek. Üç nota aynı yükseklikte duyulmalı.",
               "Sağ elin avucu veya sol elin boştaki parmakları çalmadığın telleri sustursun."]
              if legato else
              PICK_TIPS[1:2] + ["Her vuruş yeni bir tel: aksanı telin ilk notasına koy, kulağın teli değil vuruşu duysun.",
                                f"Notaları söyleyerek çal (A B C ...): parmak şekli ile notanın adı birlikte ezberlenir."]),
        focus="Üç nota eşit, tel geçişinde boşluk yok")


def sequence(key: str = "A", scale: str = "natural_minor", n: int = 4, degree: int = 0) -> Exercise:
    """Scale sequence (groups of 3 or 4) up the shape on the lower four strings, then back down."""
    shape = [p for p in scale_position(key, scale, 3, degree, low_fret=_low_fret(key, scale, degree)) if p.string >= 3]
    up = _groups(shape, n)
    down = _groups(shape[::-1], n)
    per_beat = 3 if n == 3 else 4
    notes, beats = _line(_pad(up + down, per_beat), per_beat)
    return Exercise(
        id=f"seq/{key}/{scale}/{n}/{degree}", skill=f"seq/{scale}/{n}/{degree}", family="seq",
        group="Alternate picking", title=f"{key} {SCALE_NAMES[scale]} · {n}'lü sekans",
        subtitle=f"{'1-2-3, 2-3-4' if n == 3 else '1-2-3-4, 2-3-4-5'} ... alt 4 tel, çık-in",
        per_beat=per_beat, bpm=70, goal_bpm=150, notes=notes, beats=beats, level=3, key=key,
        tips=PICK_TIPS[1:] + ["Sekanslar gam ezberini kalıptan müziğe çevirir: sololardaki 'koşuların' çoğu bu gruplardır."],
        focus="Grubun ilk notası vuruşa otursun")


def pentatonic(key: str = "A", box: int = 1, sixes: bool = False) -> Exercise:
    """Minor pentatonic box 1..5 up and down (triplets), or the classic descending 'sixes' run (sextuplets)."""
    shape = scale_position(key, "minor_pentatonic", 2, box - 1, low_fret=_low_fret(key, "minor_pentatonic", box - 1))
    if sixes:
        down = shape[::-1]
        seq = [p for i in range(0, len(down) - 4, 2) for p in down[i:i + 6]]
        notes, beats = _line(_pad(seq, 6), 6)
        return Exercise(
            id=f"pent6/{key}/{box}", skill=f"pent6/{box}", family="pent6", group="Pentatonik",
            title=f"{key} minör pentatonik · 6'lık iniş (kutu {box})",
            subtitle="Altı notalık gruplar halinde iniş, her grup bir tel aşağı", per_beat=6, bpm=50, goal_bpm=110,
            notes=notes, beats=beats, level=4, key=key,
            tips=["Rock/blues sololarının en çok kullanılan hız kalıbı (Page, Slash, Wylde). Önce yavaş, gruplar "
                  "kulağında 'altılı' gibi sallanana kadar.",
                  "Aynı perdedeki iki teli parmak ucunu yuvarlayarak (roll) geç; parmak kaldırırsan notalar birbirine girer."]
            + PICK_TIPS[:1], focus="Her grubun ilk notası vuruşta")
    notes, beats = _line(_pad(_up_down(shape), 3), 3)
    return Exercise(
        id=f"pent/{key}/{box}", skill=f"pent/{box}", family="pent", group="Pentatonik",
        title=f"{key} minör pentatonik · kutu {box}", subtitle="Tel başına 2 nota, çık-in, triplet",
        per_beat=3, bpm=70, goal_bpm=150, notes=notes, beats=beats, level=1 if box == 1 else 2, key=key,
        tips=["Beş kutu klavyeyi zincir gibi kaplar: bir kutunun üst notaları sonrakinin alt notalarıdır. Kutuları "
              "birbirine bağlayarak öğren, tek tek değil.",
              "Kök notaları (tonik) çalarken içinden söyle; doğaçlamada nereye döneceğini kökler gösterir."],
        focus="Kök notaları duy")


def trill(pair: str = "13", string: int = 3, fret: int = 5) -> Exercise:
    """Hammer-on / pull-off trill on one string (pick only the first note)."""
    a, b = (fret + int(c) - 1 for c in pair)
    seq = [_pos(string, a if i % 2 == 0 else b) for i in range(32)]
    techs = [""] + ["h" if i % 2 else "p" for i in range(1, 32)]
    notes, beats = _line(seq, 4, techs)
    return Exercise(
        id=f"trill/{pair}", skill=f"trill/{pair}", family="trill", group="Legato",
        title=f"Legato tril · parmak {pair[0]}-{pair[1]}", subtitle=f"{string}. tel, sadece ilk nota penalı, 16'lık",
        per_beat=4, bpm=60, goal_bpm=140, notes=notes, beats=beats, level=2,
        tips=["Çekiçte (h) parmak yüksekten değil, yakından ama hızlı insin; güç hızdan gelir, yükseklikten değil.",
              "Çekmede (p) parmak teli yana hafifçe çekip bıraksın: alttaki nota ancak böyle çınlar.",
              "Ses pena ile çalınmış kadar yüksek olmalı. Kısılıyorsa tempo yüksek."],
        focus="Çekiç ve çekme aynı ses seviyesinde")


# Standard sweep shapes: (string, fret offset from the root's fret on the first string), ascending.
# 3 strings: root on the G string (A minor at 14: G14 B13 e12 e17). 5 strings: root on the A string (A minor at 12).
SWEEP_SHAPES = {
    ("min", 3): [(3, 0), (2, -1), (1, -2), (1, 3)],
    ("maj", 3): [(3, 0), (2, 0), (1, -2), (1, 3)],
    ("min", 5): [(5, 0), (4, 2), (3, 2), (2, 1), (1, 0), (1, 5)],
    ("maj", 5): [(5, 0), (4, 2), (3, 2), (2, 2), (1, 0), (1, 5)],
}


def sweep(key: str = "A", quality: str = "min", strings: int = 3) -> Exercise:
    """Arpeggio sweep over the top 3 or 5 strings, up and down (triplets / sextuplets)."""
    from .theory import pc

    first = 3 if strings == 3 else 5
    root = (pc(key) - STANDARD[first - 1]) % 12
    root += 12 if root < 3 else 0  # the shape reaches 2 frets below the root
    shape = [_pos(s, root + o) for s, o in SWEEP_SHAPES[(quality, strings)]]
    seq = _up_down(shape)
    per_beat = 3 if strings == 3 else 5
    techs = []
    prev = None
    for p in seq:  # sweep: down strokes going up in pitch across strings, up strokes coming down
        techs.append("d" if prev is None or p.midi > prev.midi else "u")
        prev = p
    notes, beats = _line(seq, per_beat, techs)
    return Exercise(
        id=f"sweep/{key}/{quality}/{strings}", skill=f"sweep/{quality}/{strings}", family="sweep", group="Arpej",
        title=f"{chord_name(key, quality)} arpej · {strings} tel sweep",
        subtitle="Pena tek hareketle tellerden geçer, " + ("triplet" if strings == 3 else "5'lik (quintuplet)"),
        per_beat=per_beat, bpm=50, goal_bpm=120, notes=notes, beats=beats, level=3 if strings == 3 else 4, key=key,
        tips=["Sweep 'hızlı strum' değil: pena tek, kesintisiz bir hareketle iner ama her nota ayrı duyulur. Sol el her "
              "notadan sonra parmağı kaldırıp sesi keser (yoksa akor gibi çınlar).",
              "En yaygın hata ilk ve son notada acele: bu tempoda arpejin şeklini eşit gruplar olarak say."],
        focus="Notalar birbirine karışmasın: çaldıktan sonra sustur")


def arp7(key: str = "A", quality: str = "min7") -> Exercise:
    """Two-octave seventh-chord arpeggio, two notes per string where they fit (16ths)."""
    low = _arp_low_fret(key, quality, (6,))
    shape = arpeggio_shape(key, quality, low, per_string_max=2, span=4)
    notes, beats = _line(_pad(_up_down(shape), 4), 4)
    return Exercise(
        id=f"arp7/{key}/{quality}", skill=f"arp7/{quality}", family="arp7", group="Arpej",
        title=f"{chord_name(key, quality)} arpej · iki oktav", subtitle="Akor tonları 1-3-5-7, 16'lık",
        per_beat=4, bpm=60, goal_bpm=120, notes=notes, beats=beats, level=3, key=key,
        tips=["Akorun tonlarını gam içinden ayırmak doğaçlamanın anahtarı: akor değişirken bu notalara inersen solo "
              "'altyapıyı takip ediyor' gibi duyulur.",
              "Çalarken derece say: bir-üç-beş-yedi. 3'lü ve 7'li akorun rengidir."],
        focus="Akor tonlarını duy: 1, 3, 5, 7")


def skip(key: str = "A", quality: str = "min") -> Exercise:
    """String skipping: a triad climbing on strings 5-3-1 / 4-2 shapes (8ths)."""
    low = _arp_low_fret(key, quality, (5, 3, 1))
    a = arpeggio_shape(key, quality, low, strings=(5, 3, 1), per_string_max=2, span=5)
    seq = _pad(_up_down(a), 2)
    notes, beats = _line(seq, 2)
    return Exercise(
        id=f"skip/{key}/{quality}", skill=f"skip/{quality}", family="skip", group="Alternate picking",
        title=f"{chord_name(key, quality)} · tel atlamalı", subtitle="5., 3. ve 1. tel, 8'lik",
        per_beat=2, bpm=80, goal_bpm=170, notes=notes, beats=beats, level=3, key=key,
        tips=["Tel atlarken pena atladığın telin üstünden 'kavis' çizmesin, kısa yoldan geçsin.",
              "Atlanan teli sağ elin avuç kenarı ya da sol elin işaret parmağı sustursun."],
        focus="Atlanan tel çınlamasın")


def subdivisions(string: int = 6, fret: int = 0) -> Exercise:
    """Rhythm ladder: one bar each of quarters, 8ths, triplets, 16ths on one muted note."""
    notes = []
    beat = 0.0
    for per_beat in (1, 2, 3, 4):
        for i in range(4 * per_beat):
            notes.append({"beat": round(beat + i / per_beat, 4), "dur": round(1 / per_beat, 4), "string": string,
                          "fret": fret, "midi": midi_of(string, fret), "tech": ""})
        beat += 4
    return Exercise(
        id="subdiv", skill="subdiv", family="subdiv", group="Ritim", title="Bölüm merdiveni",
        subtitle="Dörtlük → 8'lik → triplet → 16'lık, her ölçü bir basamak", per_beat=4, bpm=70, goal_bpm=120,
        notes=notes, beats=16, level=1,
        tips=["Hızlı çalanların sırrı saat: notalar metronoma göre değil, vuruşun içindeki yerine göre konur.",
              "Bölüm değişirken (8'lik → triplet) ilk nota tam vuruşa düşmeli; bu ölçü geçişleri en çok kayılan yer.",
              "Palm mute ile çal: yanlış zamanlama çınlamanın içinde saklanmasın."],
        focus="Bölüm geçişlerinde vuruşa otur")


def burst(base: str = "pent/A/1") -> Exercise:
    """Speed bursts on the first 4 notes of another exercise: short fast bursts with rests between (16ths).

    The motion is learned in short bursts at a speed the hand cannot yet hold for long; the rests keep the burst
    relaxed. Bar 1-2: 1 beat on, 1 off; bar 3: 2 on, 2 off; bar 4: 4 on."""
    src = build(base)
    cell = [Pos(n["string"], n["fret"], n["midi"]) for n in src.notes[:4]]
    seq: list[Pos | None] = []
    for on, off in ((1, 1), (1, 1), (1, 1), (1, 1), (2, 2), (4, 0)):
        seq += cell * on + [None] * (4 * off)
    notes, beats = _line(seq, 4)
    return Exercise(
        id=f"burst/{base}", skill=f"burst/{src.skill}", family="burst", group="Hız patlaması",
        title=f"Hız patlaması · {src.title}", subtitle="Kısa patlama + dinlenme; dinlenmede eli tamamen gevşet",
        per_beat=4, bpm=max(60, src.bpm + 20), goal_bpm=src.goal_bpm + 20, notes=notes, beats=beats, level=3,
        key=src.key,
        tips=["Patlama tempoyu senin rahat tempondan %10–20 yukarıda tutar: el hareketi hızlı versiyonu böyle öğrenir.",
              "Dinlenme kısmı egzersizin yarısıdır: sertleşmeden yeniden başla. Gerginlik hızın düşmanı."],
        focus="Patla, gevşe, tekrar")


# ---------------------------------------------------------------------------------------------- positions
def _low_fret(key: str, scale: str, degree: int) -> int:
    """The fret on string 6 where the shape starting on that scale degree begins: 1..12 (an open-string start moves
    up an octave, so every shape is played fretted)."""
    from .theory import pc

    ivs = SCALES[scale]
    first = (pc(key) + ivs[degree % len(ivs)]) % 12
    return (first - STANDARD[5]) % 12 or 12


def _arp_low_fret(key: str, quality: str, strings: tuple[int, ...]) -> int:
    """A box that starts on the root on the lowest string used, frets 2..14."""
    from .theory import pc

    s = strings[0]
    f = (pc(key) - STANDARD[s - 1]) % 12
    return f + 12 if f < 2 else f


# ------------------------------------------------------------------------------------------------ catalog
FAMILIES = {
    "chromatic": lambda p: chromatic(*(p[:1] or ["1234"]), *[int(x) for x in p[1:2]]),
    "tremolo": lambda p: tremolo(per_beat=int(p[0]) if p else 4),
    "3nps": lambda p: three_nps(p[0], p[1], int(p[2])),
    "legato3nps": lambda p: three_nps(p[0], p[1], int(p[2]), legato=True),
    "seq": lambda p: sequence(p[0], p[1], int(p[2]), int(p[3])),
    "pent": lambda p: pentatonic(p[0], int(p[1])),
    "pent6": lambda p: pentatonic(p[0], int(p[1]), sixes=True),
    "trill": lambda p: trill(p[0]),
    "sweep": lambda p: sweep(p[0], p[1], int(p[2])),
    "arp7": lambda p: arp7(p[0], p[1]),
    "skip": lambda p: skip(p[0], p[1]),
    "subdiv": lambda p: subdivisions(),
}


def solo_phrase(track_id: str, index: int) -> Exercise:
    """One phrase of a transcribed solo (practice/solo.py), at the song's tempo as the goal."""
    from .solo import load_solo

    doc = load_solo(track_id)
    ph = doc["phrases"][index]
    tempo = float(doc["tempo"]) or 100.0
    who = " - ".join(x for x in (doc.get("artist"), doc.get("title")) if x)
    return Exercise(
        id=f"solo/{track_id}/{index}", skill=f"solo/{track_id}/{index}", family="solo", group="Solo",
        title=f"{who or 'Solo'} · cümle {index + 1}/{len(doc['phrases'])}",
        subtitle=f"Kayıtta {tempo:.0f} BPM · {ph['count']} nota · otomatik transkripsiyon (taslak)",
        per_beat=4, bpm=max(40, round(tempo * 0.6)), goal_bpm=round(tempo), notes=ph["notes"], beats=ph["beats"],
        level=4,
        tips=["Önce dinle: kaydı yavaşlatıp (Dinle) cümleyi içinden söyleyebilene kadar. Kulağın bilmediğini parmak "
              "hızla çalamaz.",
              "En zor ölçüyü ayrı döngüye al; cümlenin geri kalanı zaten akar. Sonra bütünü %60'tan başlatıp tempo "
              "merdiveniyle kayıt hızına çık.",
              "Bend (b) işaretli notada perdeye basıp hedef sese kadar it; doğruluk ilk (basılan) notaya göre ölçülür. "
              "Transkripsiyon taslaktır: yanlış görünen notayı kulağınla düzelt."],
        focus="Önce kulak, sonra parmak")


def build(ex_id: str) -> Exercise:
    fam, *params = ex_id.split("/")
    if fam == "burst":
        return burst("/".join(params))
    if fam == "solo":
        return solo_phrase(params[0], int(params[1]))
    if fam not in FAMILIES:
        raise ValueError(f"bilinmeyen egzersiz: {ex_id}")
    return FAMILIES[fam](params)


SPIDER = ["".join(p) for p in permutations("1234")][1:]  # 23 permutations after the plain 1234


def catalog(key: str = "A") -> list[Exercise]:
    """The menu: every family in a sensible default (key for the scale ones)."""
    ids = (["chromatic/1234/1", "chromatic/1324/1", "chromatic/1423/5", "tremolo/4", "tremolo/6", "subdiv"]
           + [f"pent/{key}/{b}" for b in range(1, 6)] + [f"pent6/{key}/1"]
           + [f"3nps/{key}/natural_minor/{d}" for d in (0, 2, 4)] + [f"3nps/{key}/major/0"]
           + [f"seq/{key}/natural_minor/3/0", f"seq/{key}/natural_minor/4/0"]
           + ["trill/12", "trill/13", "trill/14", "trill/34", f"legato3nps/{key}/natural_minor/0"]
           + [f"sweep/{key}/min/3", f"sweep/{key}/maj/3", f"sweep/{key}/min/5", f"arp7/{key}/min7", f"arp7/{key}/maj7",
              f"skip/{key}/min"]
           + [f"burst/pent/{key}/1", f"burst/3nps/{key}/natural_minor/0"])
    return [build(i) for i in ids]


def key_of_day(day_index: int) -> str:
    """The circle of fifths, one key a week: long enough to own it, every key within a season."""
    return CIRCLE[(day_index // 7) % len(CIRCLE)]


def spider_of_day(day_index: int) -> str:
    return SPIDER[day_index % len(SPIDER)]
