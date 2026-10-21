"""`tonematch practice ...`: the practice system's commands (desktop app: `--json`, live `@@PRACTICE` events)."""

from __future__ import annotations

import os
import sys
import threading

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="Daily practice: metronome, tab, live right/wrong, speed ladder")
console = Console()


def _stopper(as_json: bool):
    stop = threading.Event()

    def watch_stdin() -> None:
        # desktop app: any line or a closed pipe (app gone) stops; terminal: Enter stops
        line = sys.stdin.readline()
        if line or as_json:
            stop.set()

    threading.Thread(target=watch_stdin, daemon=True).start()
    return stop


def _fail(e: Exception, as_json: bool):
    from ..report import ERROR, emit
    from .session import AudioOpenTimeout

    if as_json:
        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
    else:
        console.print(f"[red]{e}[/]", highlight=False)
    if isinstance(e, AudioOpenTimeout):  # PortAudio is stuck in the OS: a normal exit would wait on it
        sys.stdout.flush()
        os._exit(1)
    raise typer.Exit(1)


def _result(as_json: bool, payload) -> bool:
    if as_json:
        from ..report import RESULT, emit

        emit(RESULT, payload)
    return as_json


@app.command("catalog")
def catalog_cmd(key: str = typer.Option(None, "--key", help="key for the scale exercises (default: key of the week)"),
                as_json: bool = typer.Option(False, "--json")) -> None:
    """Every exercise, grouped (tab included)."""
    from .exercises import catalog, key_of_day
    from .progress import day_index, load_state

    k = key or key_of_day(day_index())
    st = load_state()
    out = []
    for e in catalog(k):
        sk = st["skills"].get(e.skill, {})
        out.append({**e.to_dict(), "working": sk.get("bpm", e.bpm), "best": sk.get("best", 0)})
    if _result(as_json, {"key": k, "exercises": out}):
        return
    group = None
    for e in out:
        if e["group"] != group:
            group = e["group"]
            console.print(f"\n[bold]{group}[/]")
        console.print(f"  {e['id']:34s} {e['title']}  [dim]{e['working']} BPM, rekor {e['best'] or '-'}[/]",
                      highlight=False)


@app.command("exercise")
def exercise_cmd(ex_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """One exercise (any id, e.g. a solo phrase or another key)."""
    from .exercises import build
    from .progress import load_state

    try:
        e = build(ex_id)
    except Exception as err:
        _fail(err, as_json)
    sk = load_state()["skills"].get(e.skill, {})
    payload = {**e.to_dict(), "working": sk.get("bpm", e.bpm), "best": sk.get("best", 0)}
    if not _result(as_json, payload):
        console.print_json(data=payload)


@app.command("today")
def today_cmd(minutes: int = typer.Option(None, "--minutes", help="practice time (default: settings, 30)"),
              as_json: bool = typer.Option(False, "--json")) -> None:
    """Today's routine: warm-up, technique, bursts, scales, theory / ear, solo."""
    from .progress import routine
    from .solo import list_solos

    solos = list_solos()
    solo_item = None
    if solos:  # rotate through the transcribed solos' phrases, one a day
        from .progress import day_index

        flat = [(s, ph) for s in solos for ph in s["phrases"]]
        s, ph = flat[day_index() % len(flat)]
        solo_item = {"id": f"solo/{s['track_id']}/{ph['index']}", "title": s["title"], "artist": s["artist"]}
    r = routine(minutes, solo_item=solo_item)
    if _result(as_json, r):
        return
    console.print(f"[bold]Bugün[/] · {r['minutes']} dk · ton {r['key']} · odak {r['focus']} · seri {r['streak']} gün")
    for b in r["blocks"]:
        console.print(f"\n[bold]{b['title']}[/] ({b['minutes']} dk)  [dim]{b['why']}[/]", highlight=False)
        for e in b["exercises"]:
            mark = "✓" if e["id"] in r["done_ids"] else "·"
            console.print(f"  {mark} {e['title']}  {e['bpm']} BPM  [dim]{e['id']}[/]", highlight=False)
        if b.get("quiz"):
            console.print(f"  · quiz: {b['quiz']}  [dim]tonematch practice quiz {b['quiz']}[/]", highlight=False)


@app.command("play")
def play_cmd(ex_id: str = typer.Argument(..., help="exercise id (see `practice catalog`)"),
             bpm: int = typer.Option(None, "--bpm", help="tempo (default: your working tempo)"),
             loops: int = typer.Option(0, "--loops", help="repeats (default: about 30 s)"),
             as_json: bool = typer.Option(False, "--json", help="@@PRACTICE events + one @@RESULT (desktop app)")) -> None:
    """Play an exercise with the metronome; every note is judged live. Stop with Enter (app: stdin line)."""
    from ..report import PRACTICE, emit
    from .exercises import build
    from .progress import load_state, record_take, working_bpm
    from .session import device_warnings, play

    stop = _stopper(as_json)
    try:
        ex = build(ex_id)
        st = load_state()
        bpm = int(bpm or working_bpm(ex.skill, ex.bpm, st))
        loop_s = ex.beats * 60 / bpm
        loops = int(loops or max(1, min(12, round(30 / loop_s))))
        warnings = device_warnings()
        say = (lambda ev: emit(PRACTICE, ev)) if as_json else _printer(ex)
        say({"kind": "ready", "id": ex.id, "title": ex.title, "bpm": bpm, "loops": loops, "warnings": warnings})
        res = play(ex, bpm, loops, say, stop.is_set, st["settings"])
        decision = record_take(ex.id, bpm, res, res["seconds"]) if res["notes"] else None
    except Exception as e:
        _fail(e, as_json)
    out = {**res, "id": ex.id, "skill": ex.skill, "bpm": bpm, "loops": loops, "decision": decision,
           "warnings": warnings}
    if _result(as_json, out):
        return
    console.print(f"\n[bold]%{res['accuracy'] * 100:.0f}[/] doğru ({res['correct']}/{res['notes']}), "
                  f"vuruşta %{res['on_time'] * 100:.0f}, ortalama {res['mean_ms'] or 0:+.0f} ms, "
                  f"yayılım {res['spread_ms'] or 0:.0f} ms, fazla nota {res['extras']}", highlight=False)
    if decision:
        console.print(decision["message"], highlight=False)
        if decision["suggest"] == "faster" and typer.confirm(f"{decision['to_bpm']} BPM'e geçilsin mi?", default=True):
            from .progress import set_bpm

            set_bpm(ex.skill, decision["to_bpm"])


def _printer(ex):
    marks = {"hit": "[green]●[/]", "early": "[yellow]◀[/]", "late": "[yellow]▶[/]", "wrong": "[red]✕[/]",
             "miss": "[red]○[/]", "extra": "[dim]+[/]"}

    def say(ev: dict) -> None:
        k = ev["kind"]
        if k == "ready":
            console.print(f"[bold]{ev['title']}[/] · {ev['bpm']} BPM · {ev['loops']} tur — durdurmak için Enter")
            for w in ev["warnings"]:
                console.print(f"[yellow]uyarı:[/] {w}", highlight=False)
        elif k == "beat" and ev["count_in"]:
            console.print(f"{-ev['beat']} ...", end=" ")
        elif k == "beat" and ev["beat"] % ex.beats == 0:
            console.print(f"\n[dim]tur {ev['loop'] + 1}[/] ", end="")
        elif k == "note" and ev["status"] in marks:
            console.print(marks[ev["status"]], end="")
    return say


@app.command("set-bpm")
def set_bpm_cmd(ex_id: str, bpm: int, as_json: bool = typer.Option(False, "--json")) -> None:
    """Set the working tempo of an exercise's skill (the app calls this when you accept the ladder's suggestion)."""
    from .exercises import build
    from .progress import set_bpm

    try:
        sk = set_bpm(build(ex_id).skill, bpm)
    except Exception as e:
        _fail(e, as_json)
    if not _result(as_json, sk):
        console.print(f"{ex_id}: {bpm} BPM")


@app.command("settings")
def settings_cmd(minutes: int = typer.Option(None, "--minutes"),
                 threshold: float = typer.Option(None, "--threshold", help="clean take accuracy, 0.8..1 (0.95)"),
                 latency_ms: float = typer.Option(None, "--latency-ms", help="your timing offset (practice latency)"),
                 click_level: float = typer.Option(None, "--click-level", help="metronome volume 0..1"),
                 count_in: int = typer.Option(None, "--count-in", help="count-in beats"),
                 as_json: bool = typer.Option(False, "--json")) -> None:
    """Show or change the practice settings."""
    from .progress import set_settings

    s = set_settings(minutes=minutes, threshold=threshold, latency_ms=latency_ms, click_level=click_level,
                     count_in=count_in)
    if not _result(as_json, s):
        console.print_json(data=s)


@app.command("stats")
def stats_cmd(as_json: bool = typer.Option(False, "--json")) -> None:
    """Progress: tempo per skill over time, quiz scores, minutes per day, streak."""
    from .progress import stats

    s = stats()
    if _result(as_json, s):
        return
    console.print(f"seri {s['streak']} gün · {s['takes']} tur · {s['total_minutes']} dk")
    for sk in s["skills"][:20]:
        console.print(f"  {sk['title']}: çalışma {sk['working']} BPM, rekor {sk['best'] or '-'} ({sk['takes']} tur)",
                      highlight=False)


@app.command("quiz")
def quiz_cmd(kind: str = typer.Argument("mix", help="fretboard / interval / degree / chord / echo / mix"),
             count: int = typer.Option(10, "--count"),
             level: int = typer.Option(1, "--level", help="1 = basics, 2 = all notes / intervals"),
             as_json: bool = typer.Option(False, "--json")) -> None:
    """Theory and ear drills answered on the guitar."""
    from ..report import PRACTICE, emit
    from .progress import load_state
    from .quiz import run_quiz

    stop = _stopper(as_json)

    def say(ev: dict) -> None:
        if as_json:
            return emit(PRACTICE, ev)
        if ev["kind"] == "question":
            console.print(f"\n[bold]{ev['n']}.[/] {ev['prompt']}", highlight=False)
        elif ev["kind"] == "answer":
            ok = "[green]doğru[/]" if ev["right"] else "[red]yanlış[/]"
            console.print(f"   {ok} — {ev['answer']}" + (f" ({ev['ms']} ms)" if ev["ms"] else ""), highlight=False)

    try:
        res = run_quiz(kind, count, say, stop.is_set, load_state()["settings"], level)
    except Exception as e:
        _fail(e, as_json)
    if not _result(as_json, res):
        console.print(f"\n{res['right']}/{res['asked']} doğru")


@app.command("latency")
def latency_cmd(as_json: bool = typer.Option(False, "--json")) -> None:
    """Timing calibration: 16 clicks at 80 BPM, play one (muted) note on each; the median offset is saved."""
    from ..report import PRACTICE, emit
    from .progress import load_state, set_settings
    from .session import measure_latency

    stop = _stopper(as_json)
    say = (lambda ev: emit(PRACTICE, ev)) if as_json else (lambda ev: None)
    try:
        st = load_state()["settings"]
        res = measure_latency(say, stop.is_set, st)
        if res["offset_ms"] is not None:
            set_settings(latency_ms=res["offset_ms"])
    except Exception as e:
        _fail(e, as_json)
    if not _result(as_json, res):
        console.print(f"gecikme: {res['offset_ms']} ms ({res['used']} vuruş)" if res["offset_ms"] is not None
                      else "yeterli vuruş algılanmadı")


@app.command("solo")
def solo_cmd(source: str = typer.Argument(..., help="the song (URL / search / file, as in `run`)"),
             role: str = typer.Option("lead", "--role"),
             as_json: bool = typer.Option(False, "--json")) -> None:
    """Transcribe a song's lead guitar into tab phrases to practise."""
    from ..report import PRACTICE, emit
    from .solo import transcribe

    say = (lambda m: emit(PRACTICE, {"kind": "info", "message": m})) if as_json else (lambda m: console.print(m))
    try:
        doc = transcribe(source, role, say)
    except Exception as e:
        _fail(e, as_json)
    payload = {k: doc[k] for k in ("track_id", "title", "artist", "tempo", "role")} | {
        "phrases": [{"index": p["index"], "beats": p["beats"], "count": p["count"], "start_s": p["start_s"],
                     "id": f"solo/{doc['track_id']}/{p['index']}"} for p in doc["phrases"]]}
    if not _result(as_json, payload):
        console.print(f"{len(doc['phrases'])} cümle; çalmak için: tonematch practice play solo/{doc['track_id']}/0")


@app.command("solos")
def solos_cmd(as_json: bool = typer.Option(False, "--json")) -> None:
    """Transcribed solos."""
    from .solo import list_solos

    s = list_solos()
    if not _result(as_json, {"solos": s}):
        for x in s:
            console.print(f"{x['track_id']}  {x['artist']} - {x['title']}  {len(x['phrases'])} cümle", highlight=False)


@app.command("reference")
def reference_cmd(ex_id: str = typer.Argument(..., help="a solo phrase id: solo/<track>/<n>"),
                  bpm: int = typer.Option(None, "--bpm", help="play it at this tempo (default: the record's)"),
                  as_json: bool = typer.Option(False, "--json")) -> None:
    """Play a solo phrase from the record (slowed down if asked) through the GT-1."""
    from .session import play_sound
    from .solo import load_solo, reference

    try:
        _, tid, idx = ex_id.split("/")
        tempo = float(load_solo(tid)["tempo"])
        speed = (bpm or tempo) / tempo
        y = reference(tid, int(idx), speed)
        play_sound(y)
    except Exception as e:
        _fail(e, as_json)
    _result(as_json, {"id": ex_id, "speed": round(speed, 2), "seconds": round(len(y) / 44100, 1)})
