import numpy as np
import pytest

from tonematch.practice import exercises as exs
from tonematch.practice import theory as th
from tonematch.practice.listen import SR, detect
from tonematch.practice.score import Scorer
from tonematch.practice.session import Take
from tonematch.practice.synth import render


# ------------------------------------------------------------------------------------------------ theory
def test_pentatonic_box_one_in_a_is_the_classic_shape():
    box = th.scale_position("A", "minor_pentatonic", 2, 0, low_fret=5)
    assert [(p.string, p.fret) for p in box] == [(6, 5), (6, 8), (5, 5), (5, 7), (4, 5), (4, 7), (3, 5), (3, 7),
                                                 (2, 5), (2, 8), (1, 5), (1, 8)]
    assert [th.note_name(p.midi) for p in box[:5]] == ["A", "C", "D", "E", "G"]


def test_three_note_per_string_shape_climbs_the_scale():
    sh = th.scale_position("A", "natural_minor", 3, 0, low_fret=5)
    assert len(sh) == 18 and all(b.midi > a.midi for a, b in zip(sh, sh[1:]))
    assert {p.midi % 12 for p in sh} == set(th.scale_pcs("A", "natural_minor"))
    assert all(sum(p.string == s for p in sh) == 3 for s in range(1, 7))


def test_note_spelling_and_flat_keys():
    assert th.pc("Db") == th.pc("C#") == 1 and th.note_name(61, octave=True) == "C#4"
    assert th.uses_flats("F") and th.uses_flats("D", "natural_minor") and not th.uses_flats("A", "natural_minor")


# --------------------------------------------------------------------------------------------- exercises
def test_catalog_builds_playable_exercises():
    for e in exs.catalog("A") + exs.catalog("F#"):
        assert e.notes and e.beats >= 1
        assert all(0 <= n["fret"] <= th.MAX_FRET and 1 <= n["string"] <= 6 for n in e.notes)
        assert all(n["midi"] == th.midi_of(n["string"], n["fret"]) for n in e.notes)
        assert all(n["beat"] < e.beats for n in e.notes)
        assert exs.build(e.id).notes == e.notes  # the id is enough to rebuild it
        assert e.tips and e.focus


def test_skill_ignores_the_key_and_sweeps_alternate_direction():
    assert exs.build("pent/A/2").skill == exs.build("pent/C/2").skill
    sw = exs.build("sweep/A/min/3")
    assert [(n["string"], n["fret"]) for n in sw.notes[:4]] == [(3, 14), (2, 13), (1, 12), (1, 17)]
    assert [n["tech"] for n in sw.notes] == ["d", "d", "d", "d", "u", "u"]
    leg = exs.build("legato3nps/A/natural_minor/0")
    assert [n["tech"] for n in leg.notes[:3]] == ["", "h", "h"]


# ---------------------------------------------------------------------------------------------- detector
@pytest.mark.parametrize("bpm,per_beat,drive", [(100, 4, 0), (160, 4, 8), (140, 6, 8)])
def test_detector_finds_fast_notes_on_time(bpm, per_beat, drive):
    rng = np.random.default_rng(bpm)
    gap = 60 / bpm / per_beat
    notes = [(0.3 + i * gap, 45 + int(m), gap) for i, m in enumerate(rng.integers(0, 30, 32))]
    y = render(notes, 0.6 + 32 * gap, drive=drive, seed=2) + 1e-4 * rng.standard_normal(int((0.6 + 32 * gap) * SR))
    det = detect(y.astype(np.float32))
    for t0, m, _ in notes:
        d = min(det, key=lambda d: abs(d.sample / SR - t0))
        assert abs(d.sample / SR - t0) < 0.012 and d.note is not None and (d.note - m) % 12 == 0


def test_detector_hears_legato_without_pick_attacks():
    gap = 60 / 90 / 4
    notes = [(0.3 + i * gap, 57 + (2 if i % 2 else 0), gap) for i in range(16)]
    det = detect(render(notes, 0.6 + 16 * gap, drive=3, legato=set(range(1, 16))))
    assert len([d for d in det if d.note is not None]) >= 14


# ------------------------------------------------------------------------------------------------ scorer
def test_scorer_verdicts():
    notes = [{"beat": b, "midi": 60 + b} for b in range(4)]
    s = Scorer.for_take(notes, 0.5, 4, 1, 0.0)
    assert s.note(0.005, 60)["status"] == "hit"
    assert s.note(0.5 + 0.06, 61)["status"] == "late"
    assert s.note(1.0, 51)["status"] == "wrong"
    assert s.note(1.25, 50)["status"] == "extra"
    assert s.note(1.27, 50)["status"] == "extra"
    assert [e["status"] for e in s.misses(2.0)] == ["miss"]
    sm = s.summary()
    assert sm["accuracy"] == 0.5 and sm["counts"]["miss"] == 1 and sm["extras"] == 2


def test_scorer_ignores_a_ringing_retrigger():
    s = Scorer.for_take([{"beat": 0, "midi": 64}, {"beat": 2, "midi": 65}], 0.5, 4, 1, 0.0)
    s.note(0.0, 64)
    assert s.note(0.4, 64)["status"] == "ring" and s.extras == 0


# -------------------------------------------------------------------------------------------------- take
def _play_take(ex, bpm, loops, mistakes=(), late_ms=0.0, drive=6):
    take = Take(ex, bpm, loops, count_in=4, latency_frames=0)
    events = []
    played = []
    for k in range(loops):
        for j, n in enumerate(ex.notes):
            i = k * len(ex.notes) + j
            if i in mistakes:
                continue
            t = (take.beat_frame(k * ex.beats + n["beat"])) / SR + late_ms / 1000
            played.append((t, n["midi"], n["dur"] * take.beat_s))
    y = render(played, take.end_frame / SR + 0.2, drive=drive, seed=4)
    for a in range(0, len(y), 256):
        events += take.process(y[a:a + 256])
    events += take.finish()
    return take, events


def test_take_scores_a_clean_and_a_sloppy_run():
    ex = exs.build("pent/A/1")
    take, events = _play_take(ex, 90, 2)
    sm = take.scorer.summary()
    assert sm["accuracy"] == 1.0 and sm["on_time"] > 0.9 and abs(sm["mean_ms"]) < 10
    beats = [e["beat"] for e in events if e["kind"] == "beat"]
    assert beats[0] == -4 and beats[-1] == ex.beats * 2 - 1
    take, _ = _play_take(ex, 90, 2, mistakes={3, 10, 30})
    sm = take.scorer.summary()
    assert sm["counts"]["miss"] == 3 and sm["accuracy"] == pytest.approx(1 - 3 / 44, abs=0.01)


def test_take_sees_a_player_behind_the_beat():
    take, _ = _play_take(exs.build("tremolo/4"), 80, 1, late_ms=40)
    sm = take.scorer.summary()
    assert 30 < sm["mean_ms"] < 50 and sm["counts"]["late"] > 20


# ------------------------------------------------------------------------------------------------- solo
def test_solo_notes_split_legato_and_mark_bends():
    from tonematch.practice.solo import notes_from_pitch

    fps = 100.0
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    track = [hz(64)] * 20 + [hz(67)] * 20 + list(np.linspace(hz(69), hz(71), 15)) + [hz(71)] * 15 + [np.nan] * 5
    f0 = np.array(track, float)
    notes = notes_from_pitch(f0, ~np.isnan(f0), np.array([0.0]), 0.0, fps)
    assert [n["midi"] for n in notes] == [64, 67, 69]
    assert notes[2]["bend"] and not notes[0]["bend"]


def test_solo_rhythm_and_frets():
    from tonematch.practice.solo import assign_frets, phrases, snap, to_beats

    beats = np.arange(0, 10, 0.5)  # 120 bpm
    assert list(to_beats(np.array([0.25, 1.0, 10.5]), beats)) == pytest.approx([0.5, 2.0, 21.0])
    assert snap(1.26) == 1.25 and snap(1.335) == pytest.approx(4 / 3)
    # an A minor pentatonic run stays in box 1 (frets 5-8), no open strings
    run = [45, 48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72]
    sf = assign_frets(run)
    assert all(5 <= f <= 8 for _, f in sf)
    notes = [{"beat": b, "dur": 0.25} for b in (0, 0.25, 0.5, 3, 3.25)]
    assert [len(p) for p in phrases(notes)] == [3, 2]


# ------------------------------------------------------------------------------------------------- quiz
def test_quiz_questions_and_judging():
    import random

    from tonematch.practice import quiz

    rng = random.Random(1)
    for kind in quiz.KINDS:
        for _ in range(20):
            q = quiz.question(kind, rng, level=2)
            assert q["prompt"] and q["answer"] and q["count"] >= 1
    q = quiz.question("fretboard", random.Random(3))
    assert quiz.judge(q, [q["accept"][0]]) and not quiz.judge(q, [q["accept"][0] + 1])
    e = {"kind": "echo", "count": 3, "sequence": [60, 64, 67]}
    assert quiz.judge(e, [72, 64, 55]) and not quiz.judge(e, [60, 67, 64])
    stats = {}
    quiz.update_stats(stats, q, False, None)
    assert quiz._weight(q["item"], stats) > quiz._weight("unseen-but-right", {"unseen-but-right": {"seen": 5, "right": 5, "ms": 900}})


# --------------------------------------------------------------------------------------------- progress
def test_ladder_asks_after_two_clean_takes_and_backs_off(tmp_path, monkeypatch):
    from tonematch.practice import progress

    monkeypatch.setattr(progress, "PRACTICE_DIR", tmp_path)
    good = {"accuracy": 0.97, "on_time": 0.8, "notes": 40}
    d1 = progress.record_take("pent/A/1", 90, good, 30)
    assert d1["suggest"] == "again" and d1["clean"]
    d2 = progress.record_take("pent/C/1", 90, good, 30)  # same skill in another key
    assert d2["suggest"] == "faster" and d2["to_bpm"] == 94
    bad = progress.record_take("pent/A/1", 94, {"accuracy": 0.6, "on_time": 0.3, "notes": 40}, 30)
    assert bad["suggest"] == "slower" and bad["to_bpm"] == 90
    assert progress.load_state()["skills"]["pent/1"]["best"] == 90
    assert progress.streak_days() == 1
    r = progress.routine(30)
    assert sum(b["minutes"] for b in r["blocks"]) in range(28, 33)
    assert all(b["exercises"] or b["id"] == "theory" for b in r["blocks"])
    assert "pent/A/1" in r["done_ids"]
    st = progress.stats()
    assert st["skills"][0]["skill"] == "pent/1" and st["takes"] == 3
