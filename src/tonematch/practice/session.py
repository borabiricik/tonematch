"""A practice take: the metronome and the guitar on one audio clock.

The GT-1 is a duplex USB audio device: one stream plays the click (USB out -> the unit's MIX -> amp) and records the
guitar (USB in = the end of the effect chain), sample-locked. A note played on a click heard from output frame F
is captured at input frame F + (output latency + input latency), which the stream reports per callback
(outputBufferDacTime - inputBufferAdcTime); the player's own offset (`latency_ms`, set by `practice latency`) is
added on top. Everything below is in *take time*: seconds from the first note's beat as the player hears it.

`Take` is the clock + detector + scorer without any audio I/O (the tests feed it rendered audio); `play` runs it on
the device.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

import numpy as np

from .exercises import BEATS_PER_BAR, Exercise
from .listen import SR, NoteDetector
from .score import Scorer
from .synth import click

OPEN_TIMEOUT_S = 6.0
MIC_HELP = ("GT-1 ses aygıtı açılamadı (bekleme süresi doldu). macOS'te en olası neden mikrofon izni: Sistem Ayarları → "
            "Gizlilik ve Güvenlik → Mikrofon'da uygulamaya (ya da terminale) izin ver; ekranda bekleyen bir izin "
            "penceresi varsa onayla. Sonra GT-1'in USB kablosunu çıkarıp tak ve tekrar dene.")
LEAD_S = 0.4                # silence before the count-in (stream start-up)
TAIL_S = 0.5                # listening after the last beat (a late last note still counts)
BLOCK = 256


class AudioOpenTimeout(RuntimeError):
    """The audio device did not open: PortAudio is stuck inside the OS (the process should exit hard)."""


@dataclass
class Take:
    ex: Exercise
    bpm: float
    loops: int
    count_in: int = 4
    latency_frames: int = 0          # output -> input, from the stream
    user_ms: float = 0.0             # the player's own offset (latency test)
    detector: NoteDetector = field(default_factory=NoteDetector)

    def __post_init__(self):
        self.beat_s = 60.0 / self.bpm
        self.first = int(LEAD_S * SR) + int(round(self.count_in * self.beat_s * SR))  # output frame of beat 0
        self.scorer = Scorer.for_take(self.ex.notes, self.beat_s, self.ex.beats, self.loops, 0.0)
        self.total_beats = self.ex.beats * self.loops
        self.end_frame = self.first + int((self.total_beats * self.beat_s + TAIL_S) * SR)
        self._beat_sent = -self.count_in - 1
        self.frame = 0

    # -- clock ------------------------------------------------------------------------------------
    def beat_frame(self, b: float) -> int:
        """Output frame of beat b (b < 0 = count-in)."""
        return self.first + int(round(b * self.beat_s * SR))

    def take_time(self, in_frame: int) -> float:
        return (in_frame - self.latency_frames - self.first) / SR - self.user_ms / 1000

    def clicks(self) -> list[tuple[int, np.ndarray]]:
        """(output frame, sound) for the count-in and every beat of the take."""
        acc, norm = click(True), click(False)
        out = []
        for b in range(-self.count_in, int(np.ceil(self.total_beats))):
            out.append((self.beat_frame(b), acc if b % BEATS_PER_BAR == 0 else norm))
        return out

    # -- input ------------------------------------------------------------------------------------
    def process(self, block: np.ndarray) -> list[dict]:
        """One input block (mono). Returns events: notes judged, misses, beats reached."""
        out = []
        for n in self.detector.feed(block):
            ev = self.scorer.note(self.take_time(n.sample), None if n.note is None else n.midi)
            out.append(ev)
        self.frame += len(block)
        now = self.take_time(self.frame)
        out += self.scorer.misses(now - 0.12)  # the detector reports a note ~60-100 ms after its onset
        # beats as the player hears them (count-in included), for the UI's cursor
        b_now = int(np.floor((self.frame - self.latency_frames - self.first) / SR / self.beat_s + 1e-9))
        while self._beat_sent < min(b_now, int(np.ceil(self.total_beats)) - 1):
            self._beat_sent += 1
            b = self._beat_sent
            out.append({"kind": "beat", "beat": b, "loop": max(0, b) // self.ex.beats if b >= 0 else -1,
                        "count_in": b < 0})
        return out

    def done(self) -> bool:
        return self.frame >= self.end_frame + self.latency_frames

    def finish(self) -> list[dict]:
        out = []
        for n in self.detector.flush():
            out.append(self.scorer.note(self.take_time(n.sample), None if n.note is None else n.midi))
        out += self.scorer.misses(self.take_time(self.frame))
        return out


# ------------------------------------------------------------------------------------------- device
def find_device(hint: str = "GT-1") -> tuple[int, str]:
    """The GT-1's duplex audio device (index, label). WASAPI first on Windows (no resampling at 44.1 kHz)."""
    import sounddevice as sd

    found = [(i, d) for i, d in enumerate(sd.query_devices())
             if hint in d["name"] and d["max_input_channels"] > 0 and d["max_output_channels"] > 0]
    if not found:
        raise RuntimeError(f"'{hint}' ses aygıtı bulunamadı (GT-1 USB ile bağlı mı?)")
    apis = [a["name"] for a in sd.query_hostapis()]
    order = ["Windows WASAPI", "Core Audio", "MME", "Windows DirectSound"]
    rank = lambda it: order.index(apis[it[1]["hostapi"]]) if apis[it[1]["hostapi"]] in order else len(order)
    i, d = min(found, key=rank)
    return i, f"{d['name']} ({apis[d['hostapi']]})"


def device_warnings() -> list[str]:
    """What would make the take fail silently, read from the unit (never written: SYSTEM area, docs/01)."""
    from ..device.gt1.client import GT1Error, connect

    out = []
    try:
        with connect() as g:
            if g.read_system("USB: PRIMARY MIX LEVEL") == 0:
                out.append("GT-1 USB MIX LEVEL 0: metronom amfiden duyulmaz. BOSS TONE STUDIO → USB → MIX LEVEL'ı aç "
                           "(program sistem ayarına yazmaz).")
            if g.read_system("LOOP BACK"):
                out.append("GT-1 LOOP BACK açık: metronom kayda karışır ve nota sanılabilir. Cihazdan LOOP BACK'i kapat.")
    except (GT1Error, RuntimeError, OSError) as e:
        out.append(f"cihaz ayarları okunamadı ({e}); metronom duyulmuyorsa USB MIX LEVEL'ı kontrol et.")
    return out


class Duplex:
    """Plays scheduled sounds and hands input blocks to the caller, on the GT-1's clock."""

    def __init__(self, device: int, level: float = 0.7, sounds: list[tuple[int, np.ndarray]] | None = None):
        self.device = device
        self.level = level
        self.sounds = sorted(sounds or [], key=lambda s: s[0])
        self.q: queue.Queue = queue.Queue()
        self.frame = 0
        self.lat: list[float] = []
        self.stream = None

    def add(self, frame: int, sound: np.ndarray) -> None:
        self.sounds.append((frame, sound))
        self.sounds.sort(key=lambda s: s[0])

    def _cb(self, indata, outdata, frames, t, status):
        a = self.frame
        out = np.zeros(frames, np.float32)
        for f, s in self.sounds:
            if f >= a + frames:
                break
            if f + len(s) <= a:
                continue
            lo, hi = max(a, f), min(a + frames, f + len(s))
            out[lo - a:hi - a] += s[lo - f:hi - f]
        outdata[:] = (self.level * out)[:, None]
        try:
            d = t.outputBufferDacTime - t.inputBufferAdcTime
            if 0 < d < 1:
                self.lat.append(d)
        except Exception:
            pass
        self.q.put((a, indata.mean(axis=1).astype(np.float32).copy()))
        self.frame += frames
        if len(self.sounds) > 64:  # drop what has played
            self.sounds = [s for s in self.sounds if s[0] + len(s[1]) > a]

    def __enter__(self):
        import threading

        import sounddevice as sd

        # Opening an input on macOS waits for the microphone permission (TCC); without a visible prompt (a shell, a
        # child process) it can wait forever. Open on a thread and give up with an explanation instead.
        box: dict = {}

        def go():
            try:
                st = sd.Stream(device=(self.device, self.device), samplerate=SR, blocksize=BLOCK, dtype="float32",
                               channels=(2, 2), latency="low", callback=self._cb)
                st.start()
                box["stream"] = st
            except Exception as e:  # reported below
                box["error"] = e

        th = threading.Thread(target=go, daemon=True)
        th.start()
        th.join(OPEN_TIMEOUT_S)
        if th.is_alive():
            raise AudioOpenTimeout(MIC_HELP)
        if "error" in box:
            raise RuntimeError(f"GT-1 ses aygıtı açılamadı: {box['error']}")
        self.stream = box["stream"]
        return self

    def __exit__(self, *exc):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()

    def latency_frames(self) -> int:
        """Output -> input round trip in frames: the stream's own report (median of callbacks), else its latency."""
        if len(self.lat) >= 4:
            return int(round(float(np.median(self.lat)) * SR))
        try:
            i, o = self.stream.latency
            return int(round((i + o) * SR))
        except Exception:
            return 0


def play(ex: Exercise, bpm: float, loops: int, emit, should_stop, settings: dict) -> dict:
    """Run a take on the GT-1. emit(event) gets every event; returns the summary."""
    take = Take(ex, bpm, loops, count_in=int(settings.get("count_in", 4)), user_ms=float(settings.get("latency_ms", 0)))
    info = _run(take, settings, emit, should_stop)
    return {**take.scorer.summary(), **info}


def _run(take: Take, settings: dict, emit, should_stop, on_note=None) -> dict:
    """The device loop shared by takes and the latency test. on_note(take_time) sees every detected onset."""
    dev, label = find_device()
    level_t = 0.0
    with Duplex(dev, float(settings.get("click_level", 0.7)), take.clicks()) as io:
        t_start = time.monotonic()
        emit({"kind": "start", "bpm": take.bpm, "loops": take.loops, "beat_s": take.beat_s, "beats": take.ex.beats,
              "count_in": take.count_in, "device": label})
        while not take.done() and not should_stop():
            try:
                _, block = io.q.get(timeout=0.5)
            except queue.Empty:
                raise RuntimeError("GT-1'den ses gelmiyor (USB ses akışı durdu)")
            if take.frame < LEAD_S * SR:  # settle the round trip during the lead-in, then the clock stays fixed
                take.latency_frames = io.latency_frames()
            if on_note is not None:
                for n in take.detector.feed(block):
                    on_note(take.take_time(n.sample))
                take.frame += len(block)
                for ev in [e for e in take.process(np.zeros(0, np.float32)) if e["kind"] == "beat"]:
                    emit(ev)
            else:
                for ev in take.process(block):
                    emit(ev)
            if time.monotonic() - level_t > 0.1:
                level_t = time.monotonic()
                emit({"kind": "level", "db": round(take.detector.level_db, 1)})
        if on_note is None:
            for ev in take.finish():
                emit(ev)
    return {"seconds": round(time.monotonic() - t_start, 1), "latency_ms": round(take.latency_frames / SR * 1000, 1),
            "stopped": bool(should_stop()), "device": label}


def measure_latency(emit, should_stop, settings: dict, bpm: float = 80, beats: int = 16) -> dict:
    """The player's own offset: one note on each of `beats` clicks; the median distance to the beat (ms).

    The stream's round trip is already removed; what is left is the amp/air and the player's habit, which the
    takes then subtract (so 'on the beat' means on the beat as this player hears it)."""
    ex = Exercise(id="latency", skill="latency", family="latency", group="", title="Gecikme testi", subtitle="",
                  per_beat=1, bpm=int(bpm), goal_bpm=int(bpm), beats=beats, level=1,
                  notes=[{"beat": b, "dur": 1, "string": 6, "fret": 0, "midi": 40, "tech": ""} for b in range(beats)])
    take = Take(ex, bpm, 1, count_in=4, user_ms=0.0)
    hits: list[float] = []

    def on_note(t: float) -> None:
        b = round(t / take.beat_s)
        dt = (t - b * take.beat_s) * 1000
        if 0 <= b < beats and abs(dt) < 200:
            hits.append(dt)
            emit({"kind": "tap", "beat": b, "dt_ms": round(dt, 1)})

    info = _run(take, settings, emit, should_stop, on_note)
    used = len(hits)
    off = round(float(np.median(hits)), 1) if used >= beats // 2 else None
    return {"offset_ms": off, "used": used, "taps": [round(h, 1) for h in hits], **info}


def play_sound(y: np.ndarray, hint: str = "GT-1") -> None:
    """Play a mono sound through the GT-1 (to the amp) and wait for it to finish."""
    import threading

    import sounddevice as sd

    dev, _ = find_device(hint)
    box: dict = {}

    def go():
        try:
            sd.play(np.column_stack([y, y]), SR, device=dev, blocking=True)
            box["ok"] = True
        except Exception as e:  # reported below
            box["error"] = e

    th = threading.Thread(target=go, daemon=True)
    th.start()
    th.join(OPEN_TIMEOUT_S + len(y) / SR)
    if th.is_alive():
        raise AudioOpenTimeout(MIC_HELP)
    if "error" in box:
        raise RuntimeError(f"GT-1'e ses gönderilemedi: {box['error']}")
