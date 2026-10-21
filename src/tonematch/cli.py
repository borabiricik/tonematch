"""tonematch CLI."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=True, help="YouTube guitar tone -> BOSS GT-1 patch")
gt1 = typer.Typer(no_args_is_help=True, help="GT-1 device commands")
app.add_typer(gt1, name="gt1")
from .practice.cli import app as practice  # noqa: E402  (light: every command imports lazily)

app.add_typer(practice, name="practice")
console = Console()


@app.callback()
def _main(verbose: bool = typer.Option(False, "-v", "--verbose")) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s",
                        handlers=[RichHandler(console=console, show_path=False, show_time=False)])
    for noisy in ("numba", "urllib3", "httpx", "matplotlib", "audio_separator"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------------------------- run
@app.command()
def run(source: str = typer.Argument(..., help="YouTube URL, 'ytsearch1:artist song', or a local audio file"),
        slot: str = typer.Option(None, "--slot", "-s",
                                 help="first user slot to write (U05 or 5). Groups go to consecutive slots."),
        only: str = typer.Option(None, "--only", help="comma list of groups: rhythm,lead,clean,crunch"),
        no_device: bool = typer.Option(False, "--no-device", help="analyse + export .tsl only"),
        separate: bool = typer.Option(False, "--separate",
                                      help="one patch per tone group instead of a CTL-switchable dual-tone patch"),
        tuning: str = typer.Option(None, "--tuning", "-t",
                                   help="song tuning, low to high, e.g. EADGBE, DADGBE, D#G#C#F#A#D#, CGCFAD. "
                                        "Not given = E standard (no pitch shifter)"),
        yes: bool = typer.Option(False, "--yes", "-y", help="do not ask before overwriting slots"),
        claude: bool = typer.Option(False, "--claude/--no-claude",
                                    help="Claude mode: Claude reviews the engine's patches with what it knows about "
                                         "the recording (API key or logged-in `claude` CLI). Off = algorithm only"),
        as_json: bool = typer.Option(False, "--json", help="also print one @@RESULT / @@ERROR line (desktop app)")) -> None:
    """Analyse a song and build GT-1 patches for its guitar parts (rhythm / lead / clean ...).

    By default two tone groups go into ONE patch: CTL off = main tone, CTL on = second tone."""
    from .device.gt1.client import parse_slot, slot_label
    from .match import pick_dual
    from .pipeline import GROUP_ORDER, prepare, run as do_run
    from .tuning import parse_tuning

    try:
        tu_in = parse_tuning(tuning) if tuning else None
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--tuning")
    start = parse_slot(slot) if slot else None
    groups = [g.strip() for g in only.split(",")] if only else None
    if start is not None and not no_device and not yes:
        _, _, ana = prepare(source)  # cached; lets us show exactly which slots will change
        chosen = [g for g in (groups or GROUP_ORDER) if g in ana.groups]
        n = len(chosen) - (1 if not separate and pick_dual(ana, chosen) else 0)
        typer.confirm(f"{n} patch -> {slot_label(start)}..{slot_label(start + n - 1)} üzerine yazılsın mı? "
                      f"(mevcut içerik yedeklenir)", abort=True)
    try:
        res = do_run(source, start, groups, device=not no_device, dual=not separate,
                     tuning=tu_in, claude=claude, progress=lambda s: console.print(s, highlight=False))
    except Exception as e:
        if not as_json:
            raise
        from .report import ERROR, emit

        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
        raise typer.Exit(1)

    ci = res.info.get("claude")
    if ci and ci.get("ok"):
        console.print(f"\n[bold]Claude modu[/] ({ci['model']}): {ci.get('song', '')}\n  {ci.get('rig_notes', '')}",
                      highlight=False)
    elif ci:
        console.print(f"\n[yellow]Claude modu çalışmadı, algoritmanın sonucu kullanıldı:[/] {ci.get('error')}",
                      highlight=False)
    tu = res.info.get("tuning")
    if tu and tu["semitones"]:
        console.print(f"\n[bold]Akort: {tu['name']}[/] → gitarını [bold]{tu['user_tuning']}[/] akortla; "
                      f"patch'te FX1 pitch shifter {tu['semitones']:+d} yarım ses", highlight=False)
    elif tu:
        console.print(f"\n[bold]Akort: {tu['name']}[/] → gitarını [bold]{tu['user_tuning']}[/] akortla, pitch shifter yok"
                      + (" (--tuning verilmedi: E standart)" if tu["evidence"].get("source") == "default" else ""),
                      highlight=False)

    seg = lambda g: ", ".join(f"{a // 60:.0f}:{a % 60:04.1f}-{b // 60:.0f}:{b % 60:04.1f}"  # noqa: E731
                              for a, b in res.analysis.groups[g].segments[:6])
    for m in res.matches:
        title = f"{m.group.upper()}  ->  {m.patch.name}   {res.written.get(m.group, '')}"
        if m.recipe.get("dual"):
            t = Table(title=title, show_header=False)
            t.add_row("CTL kapalı", f"{m.recipe['ctl_off']}: {seg(m.recipe['ctl_off'])}")
            t.add_row("CTL açık", f"{m.recipe['ctl_on']}: {seg(m.recipe['ctl_on'])}")
            t.add_row("CTL ile değişenler", "\n".join(m.recipe["assigns"]))
            t.add_row("karar", m.recipe["why"])
            console.print(t)
            continue
        g = res.analysis.groups[m.group]
        s = m.patch.summary()
        t = Table(title=title, show_header=False)
        t.add_row("bulunduğu yerler", seg(m.group))
        t.add_row("ölçüm", f"gain {g.gain} ({g.gain_class}), {g.stereo}, reverb {g.reverb.amount}"
                  + (f", delay {g.delay.time_ms:.0f} ms" if g.delay.detected else ""))
        t.add_row("preamp", f"{s['preamp_a_type']}  G{s['preamp_a_gain']} B{s['preamp_a_bass']} M{s['preamp_a_middle']} "
                            f"T{s['preamp_a_treble']} P{s['preamp_a_presence']}  SP {s['preamp_a_sp_type']}")
        if s["od_ds_on_off"]:
            t.add_row("od/ds", f"{s['od_ds_type']} drive {s['od_ds_drive']} level {s['od_ds_effect_level']}")
        fx = []
        if s["delay_on_off"]:
            fx.append(f"delay {s['delay_type']} {s['delay_delay_time']}ms fb{s['delay_f_back']} lv{s['delay_effect_level']}")
        if s["reverb_on_off"]:
            fx.append(f"reverb {s['reverb_type']} {s['reverb_time']} lv{s['reverb_effect_level']}")
        if s["fx1_on_off"]:
            fx.append(f"fx1 {s['fx1_fx_type']}")
        if s["fx2_on_off"]:
            fx.append(f"fx2 {s['fx2_fx_type']}")
        if any(s[k] for k in ("master_eq_low_gain", "master_eq_mid_gain", "master_eq_high_gain")):
            fx.append(f"master eq L{s['master_eq_low_gain']:+d} M{s['master_eq_mid_gain']:+d}@{s['master_eq_mid_freq']} "
                      f"H{s['master_eq_high_gain']:+d}")
        t.add_row("efektler", ", ".join(fx) or "-")
        dv = m.recipe.get("deviation_db", {})
        t.add_row("ses karakteri", f"orta {dv.get('mid_scoop_db', 0):+.1f} dB, presence {dv.get('presence_db', 0):+.1f} dB, "
                                   f"gövde {dv.get('body_db', 0):+.1f} dB (referansa göre)")
        t.add_row("model adayları", ", ".join(f"{k} ({v})" for k, v in m.scores.items()))
        t.add_row("karar", str(m.recipe.get("why", "")))
        console.print(t)
    console.print(f"[green].tsl:[/] {res.tsl_path}")
    if res.info.get("backup"):
        console.print(f"[green]önceki slot yedeği:[/] {res.info['backup']}")
    if as_json:
        from .report import RESULT, emit, run_payload

        emit(RESULT, run_payload(res))


@app.command()
def analyze(source: str) -> None:
    """Only download/separate/analyse and print the detected guitar groups."""
    from .pipeline import prepare

    tid, meta, ana = prepare(source)
    console.print(f"[bold]{meta.get('artist', '')} - {meta.get('title', '')}[/]  tempo {ana.tempo}  ({tid})")
    for n, g in ana.groups.items():
        d = g.to_dict()
        d["segments"] = d["segments"][:8]
        console.print(f"[bold]{n}[/]", d)


# ---------------------------------------------------------------------------------------- calibrate
@app.command()
def calibrate(source: str = typer.Argument(..., help="the song (same URL / file as `run`)"),
              role: str = typer.Option(None, "--role", "-r", help="rhythm / lead / clean / crunch (default: first found)"),
              slot: str = typer.Option(None, "--slot", "-s", help="select this slot first (U20); default: current patch"),
              seconds: float = typer.Option(20, "--seconds", help="recording length"),
              countdown: int = typer.Option(3, "--countdown", help="seconds before recording starts"),
              apply: bool = typer.Option(False, "--apply", help="write the suggested knob moves to the edit buffer"),
              as_json: bool = typer.Option(False, "--json", help="@@CALIB stream + one @@RESULT line (desktop app)")) -> None:
    """Play the song's part through the patch; the GT-1's USB recording is compared with the song's guitar.

    Shows how the patch differs from the song and which knob moves would close the gap. With --apply the moves go
    to the edit buffer (no slot is written: keep them with `gt1 save`, take them back with `gt1 apply --undo`)."""
    from .report import CALIB, ERROR, RESULT, emit

    say = (lambda ev: emit(CALIB, ev)) if as_json else None
    try:
        out = _calibrate(source, role, slot, seconds, countdown, say)
        if apply and out["moves"]:
            try:
                out["applied"] = _apply_calib(Path(out["record"]))
            except Exception as e:  # the measurement still counts; the moves can be applied later
                out["apply_error"] = str(e)
    except Exception as e:
        if not as_json:
            raise
        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
        raise typer.Exit(1)
    if as_json:
        return emit(RESULT, out)
    c = out["compare"]
    t = Table(title=f"{out['title']} [{out['role']}]  ←→  {out['patch']['name']}  ({out['patch']['amp']})",
              show_header=True)
    t.add_column("eksen")
    t.add_column("şarkı", justify="right")
    t.add_column("senin çalımın", justify="right")
    t.add_column("fark", justify="right")
    for k, (a, b) in out["values"].items():
        ok = k in c["close"]
        t.add_row(k, f"{a:+.2f}" if k == "drive" else f"{a:+.1f}", f"{b:+.2f}" if k == "drive" else f"{b:+.1f}",
                  f"[{'green' if ok else 'yellow'}]{c['diff'][k]:+.2f}[/]" if k == "drive"
                  else f"[{'green' if ok else 'yellow'}]{c['diff'][k]:+.1f}[/]")
    console.print(t)
    console.print("1/3 oktav farkı (patch − şarkı, dB): "
                  + "  ".join(f"{b} {v:+.0f}" for b, v in c["third_oct_diff"].items()), highlight=False)
    console.print(f"spektral mesafe: [bold]{c['spectral_distance_db']} dB[/] (küçük = daha yakın; turlar arasında izle)")
    for h in c["hints"]:
        console.print(f"  • {h['text']}  ({h['value']:+.2f})" if h["axis"] == "drive" else f"  • {h['text']}  ({h['value']:+.1f} dB)",
                      highlight=False)
    if not c["hints"]:
        console.print("[green]  tüm eksenler yakın[/]")
    (ds, dp), (rs, rp) = out["fx"]["delay_ms"], out["fx"]["reverb"]
    if ds != dp:
        console.print(f"  • delay: şarkı {f'{ds:.0f} ms' if ds else 'yok'}, patch {f'{dp:.0f} ms' if dp else 'yok'}",
                      highlight=False)
    console.print(f"  reverb: şarkı {rs}, patch {rp}", highlight=False)
    for w in out["warnings"]:
        console.print(f"[yellow]uyarı:[/] {w}", highlight=False)
    if out["moves"]:
        console.print("önerilen düzeltme: " + ", ".join(f"{m['label']} {m['from']} → {m['to']}" for m in out["moves"]),
                      highlight=False)
    for n in out["move_notes"]:
        console.print(f"  [dim]• {n}[/]", highlight=False)
    if "applied" in out:
        _print_applied(out["applied"])
    elif "apply_error" in out:
        console.print(f"[red]uygulanamadı:[/] {out['apply_error']}", highlight=False)
    elif out["moves"]:
        console.print(f"[dim]uygulamak için: tonematch gt1 apply \"{out['record']}\"[/]", highlight=False)
    console.print(f"[dim]kayıt: {out['wav']}[/]", highlight=False)


def _calibrate(source: str, role: str | None, slot: str | None, seconds: float, countdown: int, say) -> dict:
    import time
    from datetime import datetime

    import soundfile as sf

    from . import calibrate as cal
    from .device.gt1.client import connect, parse_slot, slot_label
    from .ingest import track_dir
    from .pipeline import GROUP_ORDER, prepare
    from .report import ctl_on_patch, tone_view

    def note(msg: str, **ev) -> None:
        if say:
            say({"kind": "info", "message": msg, **ev})
        else:
            console.print(msg, highlight=False)

    tid, meta, ana = prepare(source)
    found = [g for g in GROUP_ORDER if g in ana.groups]
    role = role or (found[0] if found else None)
    if role not in ana.groups:
        raise RuntimeError(f"'{role}' bu şarkıda yok; mevcut: {', '.join(found)}")
    d = track_dir(tid)
    warnings: list[str] = []

    # which side of a dual (CTL) patch this role is
    ctl_on = False
    rep = d / "report.json"
    if rep.exists():
        for p in json.loads(rep.read_text(encoding="utf-8")).get("patches", {}).values():
            r = p.get("recipe", {})
            if r.get("dual") and role in (r.get("ctl_off"), r.get("ctl_on")):
                ctl_on = role == r["ctl_on"]

    with connect() as g:
        if slot:
            g.select_patch(parse_slot(slot))
            time.sleep(0.3)
        if g.read_system("LOOP BACK"):
            warnings.append("GT-1 LOOP BACK açık: bilgisayarda çalan ses kayda karışır. Kalibrasyon sırasında "
                            "bilgisayarda ses çalma (ya da cihazdan LOOP BACK'i kapat).")
        if g.read_system("PREFERENCE: PREAMP"):
            warnings.append("PREFERENCE: PREAMP = SYSTEM: cihaz patch'in preamp ayarlarını yok sayıyor.")
        patch = g.read_patch()
        current = g.current_patch_number()
    knobs = cal.side_values(patch, ctl_on)  # before the CTL view: a dual patch keeps that side in its assigns
    mid_freq = str(patch.get("master_eq_mid_freq"))
    if ctl_on:
        patch = ctl_on_patch(patch)
    pview = {"name": patch.name.strip(), "slot": slot_label(current) if current < 99 else None,
             **tone_view(patch), "summary": patch.summary()}
    note(f"{meta.get('artist', '')} - {meta.get('title', '')} [{role}] ←→ {pview['name']} ({pview['amp']})")
    segs = ", ".join(f"{a // 60:.0f}:{a % 60:04.1f}-{b // 60:.0f}:{b % 60:04.1f}" for a, b in ana.groups[role].segments[:4])
    note(f"çalınacak yer: {segs}" + ("  —  CTL AÇIK olsun (ikinci ton)" if ctl_on else ""), phase="ready",
         patch=pview["name"], amp=pview["amp"], slot=pview["slot"], ctl_on=ctl_on, duration=ana.duration,
         segments=[[round(a, 1), round(b, 1)] for a, b in ana.groups[role].segments[:8]])

    dev, dev_label = cal.find_input()
    for n in range(countdown, 0, -1):
        note(f"{n} ...", phase="countdown", n=n)
        time.sleep(1)
    note(f"ÇAL! ({seconds:.0f} sn kayıt, {dev_label})", phase="record", seconds=seconds)
    if say:
        y = cal.record(seconds, dev, on_level=lambda db: say({"kind": "level", "db": db}))
    else:
        from rich.live import Live

        with Live("", console=console, refresh_per_second=15, transient=True) as live:
            def meter(db: float) -> None:
                n = int(max(0, min(40, (db + 60) * 40 / 60)))
                live.update(f"[{'red' if db > -3 else 'green'}]{'█' * n}[/]{'·' * (40 - n)} {db:6.1f} dBFS")
            y = cal.record(seconds, dev, on_level=meter)
    note("ölçülüyor ...", phase="measure")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cdir = d / "calib"
    cdir.mkdir(exist_ok=True)
    wav = cdir / f"{role}_{stamp}.wav"
    played = cal.measure(y, role, ana.tempo)  # raises on an unusable take: nothing is kept then
    sf.write(wav, y.T, cal.SR, subtype="FLOAT")
    if played.clipped:
        warnings.append(f"kayıt clip oldu (tepe {played.peak}): ölçüm bozulabilir; patch seviyesini ya da "
                        "USB kayıt seviyesini düşür.")
    if played.level_db < -40:
        warnings.append(f"kayıt seviyesi çok düşük ({played.level_db} dBFS): USB kayıt seviyesini kontrol et.")
    target = ana.groups[role]
    cmp = cal.compare(target, played.profile)
    values = {"drive": (round(cal._drive(target), 3), round(cal._drive(played.profile), 3)),
              **{k: (target.descriptors.get(k, 0.0), played.profile.descriptors.get(k, 0.0)) for k in cal.AXES}}
    fx = {"delay_ms": (target.delay.time_ms if target.delay.detected else None,
                       played.profile.delay.time_ms if played.profile.delay.detected else None),
          "reverb": (target.reverb.amount, played.profile.reverb.amount)}
    moves, move_notes = cal.corrections(cmp["diff"], knobs, mid_freq)
    record = cdir / f"{role}_{stamp}.json"
    out = {"track_id": tid, "title": meta.get("title", ""), "artist": meta.get("artist", ""), "role": role,
           "ctl_on": ctl_on, "patch": {k: v for k, v in pview.items() if k != "summary"}, "values": values,
           "fx": fx, "compare": cmp, "played_seconds": played.seconds, "level_db": played.level_db,
           "warnings": warnings, "wav": str(wav), "device": dev_label, "record": str(record),
           "moves": [{"field": f, "label": cal.LABELS[f], "from": knobs[f], "to": v} for f, v in moves.items()],
           "move_notes": move_notes}
    # kept for step 4 (learning the engine's systematic errors): what was played, through which knobs
    record.write_text(json.dumps({**out, "patch_summary": pview["summary"], "played_profile": played.profile.to_dict()},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out


def _apply_calib(record: Path, undo: bool = False) -> dict:
    """Put a calibration's knob moves into the edit buffer (or take them back), on the side of the patch it measured.

    Refused when another patch is selected; a knob the player has turned since is left alone. Edit buffer only:
    no slot is touched (no backup needed), `gt1 save` keeps the result. The record logs what was applied."""
    from datetime import datetime

    from . import calibrate as cal
    from .device.gt1.client import connect

    rec = json.loads(record.read_text(encoding="utf-8"))
    done = rec.get("applied_moves")
    if undo and not done:
        raise RuntimeError("bu kalibrasyonun düzeltmesi uygulanmamış; geri alınacak bir şey yok")
    if not undo and done:
        raise RuntimeError("bu kalibrasyonun düzeltmesi zaten uygulandı (geri almak için --undo)")
    moves = done if undo else rec.get("moves", [])
    ctl_on = bool(rec.get("ctl_on"))
    name = rec["patch"]["name"]
    with connect() as g:
        p = g.read_patch()
        if p.name.strip() != name.strip():
            raise RuntimeError(f"cihazda başka patch seçili ('{p.name.strip()}', beklenen '{name.strip()}'); "
                               "hiçbir şey yazılmadı")
        cur = cal.side_values(p, ctl_on)
        plan, done_now, skipped = {}, [], []
        for m in moves:
            expect, target = (m["to"], m["from"]) if undo else (m["from"], m["to"])
            if cur[m["field"]] != expect:
                skipped.append(f"{m['label']}: cihazda {cur[m['field']]} (beklenen {expect}), dokunulmadı")
                continue
            plan[m["field"]] = target
            done_now.append({**m, "from": expect, "to": target})
        q = p.copy()
        notes = cal.apply_moves(q, plan, ctl_on)
        noted = {n.split(":")[0] for n in notes}
        done_now = [m for m in done_now if m["label"] not in noted]
        changed = [k for k, v in q.params.items() if p.params.get(k) != v]
        if changed:
            try:
                g.write_fields(q, changed)
            except Exception:
                g.write_temp(p)  # back to what it was rather than half a correction
                raise
    dual = bool(cal._ctl_assigns(p))
    out = {"undo": undo, "patch": name, "ctl_on": ctl_on, "applied": done_now, "skipped": skipped, "notes": notes,
           "retoggle_ctl": ctl_on and dual and bool(done_now), "record": str(record)}
    rec.setdefault("apply_log", []).append({"at": datetime.now().isoformat(timespec="seconds"), **out})
    rec["applied_moves"] = None if undo else done_now
    record.write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out


def _print_applied(a: dict) -> None:
    verb = "geri alındı" if a["undo"] else "edit buffer'a yazıldı"
    if a["applied"]:
        console.print(f"[green]{verb}:[/] " + ", ".join(f"{m['label']} {m['from']} → {m['to']}" for m in a["applied"]),
                      highlight=False)
    else:
        console.print("[yellow]hiçbir knob değişmedi[/]")
    for n in a["skipped"] + a["notes"]:
        console.print(f"  [yellow]•[/] {n}", highlight=False)
    if a["retoggle_ctl"]:
        console.print("  CTL açık taraf: yeni değerin devreye girmesi için CTL'yi kapatıp tekrar aç.", highlight=False)
    if a["applied"]:
        console.print("[dim]slot değişmedi; tekrar çal, beğenirsen `gt1 save` ile kaydet.[/]", highlight=False)


# ---------------------------------------------------------------------------------------------- gt1
def _device_json(fn):
    """Run fn(g) on a connected GT-1 and print its result as one @@RESULT line (or @@ERROR)."""
    from .device.gt1.client import connect
    from .report import ERROR, RESULT, emit

    try:
        with connect() as g:
            emit(RESULT, fn(g))
    except Exception as e:
        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
        raise typer.Exit(1)


def _device_info(g) -> dict:
    from .device.gt1.client import slot_label

    n = g.current_patch_number()
    return {"connected": True, "current": slot_label(n) if n < 99 else f"P{n - 98:02d}",
            "edit_buffer": g.patch_summary()["name"],
            "output_select_from_system": bool(g.read_system("PREFERENCE: OUTPUT SELECT")),
            "preamp_from_system": bool(g.read_system("PREFERENCE: PREAMP"))}


def _device_slots(g) -> list[dict]:
    """All 99 slots by one small read each (~2.5 s), saved as the slot cache."""
    from .device.gt1 import slots as cache
    from .device.gt1.client import slot_label

    out = [{"slot": slot_label(s), **g.patch_summary(s)} for s in range(99)]
    cache.save(out)
    return out


@gt1.command("info")
def gt1_info(as_json: bool = typer.Option(False, "--json", help="one @@RESULT line (desktop app)")) -> None:
    """Identify the GT-1 and show the relevant system settings."""
    from .device.gt1.client import connect, slot_label

    if as_json:
        return _device_json(_device_info)
    with connect() as g:
        n = g.current_patch_number()
        console.print(f"GT-1 identity: {bytes(g.identity).hex(' ')}  (device id {g.dev:02X})")
        console.print(f"current patch: {slot_label(n) if n < 99 else f'P{n - 98:02d}'}  "
                      f"edit buffer: [bold]{g.patch_summary()['name']}[/]")
        outs = g.spec.options("output_select")
        pref_out, pref_pre = g.read_system("PREFERENCE: OUTPUT SELECT"), g.read_system("PREFERENCE: PREAMP")
        console.print(f"output select: {'SYSTEM' if pref_out else 'PATCH'}"
                      + (f" ({outs[g.read_system('OUTPUT SELECT')]})" if pref_out else ""))
        console.print(f"preamp preference: {'SYSTEM (patch preamp is ignored!)' if pref_pre else 'PATCH'}")


@gt1.command("status")
def gt1_status() -> None:
    """Device info + all 99 slots in one connection, as one @@RESULT line (desktop app)."""
    _device_json(lambda g: {**_device_info(g), "slots": _device_slots(g)})


@gt1.command("list")
def gt1_list(as_json: bool = typer.Option(False, "--json", help="one @@RESULT line (desktop app)"),
             cached: bool = typer.Option(False, "--cached", help="last known list, without touching the device")) -> None:
    """List names of all user patches (one small read per slot)."""
    from .device.gt1 import slots as cache
    from .device.gt1.client import connect

    if cached:
        from .report import RESULT, emit

        data = cache.load()
        if as_json:
            return emit(RESULT, {"slots": data["slots"], "updated": data["updated"], "cached": True})
        rows = data["slots"]
    elif as_json:
        return _device_json(lambda g: {"slots": _device_slots(g), "cached": False})
    else:
        with connect() as g:
            rows = _device_slots(g)
    t = Table("slot", "name", "preamp", "gain")
    for r in rows:
        t.add_row(r["slot"], r["name"], r["amp"], str(r["gain"]))
    console.print(t)


@gt1.command("show")
def gt1_show(slot: str = typer.Argument("temp", help="U01..U99 or 'temp' (edit buffer)")) -> None:
    """Show the main parameters of a patch."""
    from .device.gt1.client import connect, parse_slot

    with connect() as g:
        p = g.read_patch(None if slot.lower() == "temp" else parse_slot(slot))
        console.print(f"[bold]{p.name}[/]")
        console.print_json(json.dumps(p.summary()))


@gt1.command("select")
def gt1_select(slot: str = typer.Argument(..., help="U01..U99"),
               as_json: bool = typer.Option(False, "--json", help="one @@RESULT line (desktop app)")) -> None:
    """Switch the GT-1 to a user slot (loads it into the edit buffer). Writes no patch data."""
    from .device.gt1.client import connect, parse_slot, slot_label

    s = parse_slot(slot)

    def pick(g) -> dict:
        g.select_patch(s)
        return {"slot": slot_label(s), "name": g.patch_summary()["name"]}

    if as_json:
        return _device_json(pick)
    with connect() as g:
        r = pick(g)
    console.print(f"{r['slot']} seçildi: [bold]{r['name'].strip()}[/]", highlight=False)


@gt1.command("backup")
def gt1_backup() -> None:
    """Back up all 99 user patches to backups/<timestamp>_all_U01-U99.tsl (BTS-importable)."""
    from .device.gt1.backup import backup_all
    from .device.gt1.client import connect, slot_label

    with connect() as g:
        path = backup_all(g, progress=lambda s, p: console.print(f"  {slot_label(s)} {p.name}", highlight=False))
    console.print(f"[green]backup written:[/] {path}")


@gt1.command("restore")
def gt1_restore(tsl: Path, index: int = typer.Option(..., help="1-based patch index inside the .tsl"),
                slot: str = typer.Option(..., help="target slot U01..U99"),
                yes: bool = typer.Option(False, "--yes", "-y", help="do not ask for confirmation")) -> None:
    """Write one patch from a .tsl file into a user slot (current slot content is backed up first)."""
    from .device.gt1.backup import backup_slots
    from .device.gt1.client import connect, parse_slot, slot_label
    from .device.gt1.patch import read_tsl

    p = read_tsl(tsl)[index - 1]
    s = parse_slot(slot)
    if not yes:
        typer.confirm(f"Write '{p.name}' to {slot_label(s)}?", abort=True)
    with connect() as g:
        bk = backup_slots(g, [s], slot_label(s))
        g.store_patch(p, s)
    console.print(f"[green]{p.name} -> {slot_label(s)}[/] (previous content: {bk})")


@gt1.command("apply")
def gt1_apply(record: Path = typer.Argument(..., help="a calibration record (calibrate's 'record' path)"),
              undo: bool = typer.Option(False, "--undo", help="take the applied moves back"),
              as_json: bool = typer.Option(False, "--json", help="one @@RESULT line (desktop app)")) -> None:
    """Write a calibration's suggested knob moves to the edit buffer (no slot is written)."""
    from .report import ERROR, RESULT, emit

    try:
        out = _apply_calib(record, undo)
    except Exception as e:
        if not as_json:
            raise
        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
        raise typer.Exit(1)
    if as_json:
        return emit(RESULT, out)
    _print_applied(out)


@gt1.command("save")
def gt1_save(slot: str = typer.Argument(..., help="target slot U01..U99"),
             expect_name: str = typer.Option(None, "--expect-name",
                                             help="refuse unless the edit buffer holds this patch (name)"),
             yes: bool = typer.Option(False, "--yes", "-y", help="do not ask for confirmation"),
             as_json: bool = typer.Option(False, "--json", help="one @@RESULT line (desktop app)")) -> None:
    """Save the edit buffer (e.g. knobs turned on the unit while calibrating) to a user slot.

    The slot is backed up first, written, read back and verified; then selected."""
    from .device.gt1 import slots as slot_cache
    from .device.gt1.backup import backup_slots
    from .device.gt1.client import connect, parse_slot, slot_label
    from .report import ERROR, RESULT, emit

    s = parse_slot(slot)
    try:
        with connect() as g:
            buf = g.read_patch()
            name = buf.name.strip()
            if expect_name is not None and name != expect_name.strip():
                raise RuntimeError(f"cihazda başka patch seçili ('{name}', beklenen '{expect_name.strip()}'); "
                                   f"{slot_label(s)} yazılmadı")
            old = g.read_patch(s)
            changed = _changed_knobs(old, buf)
            if not g._diff(buf, old):
                out = {"slot": slot_label(s), "name": name, "saved": False, "changed": [], "backup": None}
            else:
                if not yes and not as_json:
                    console.print(f"{slot_label(s)} ({old.name.strip()}) üzerine edit buffer ({name}) yazılacak:")
                    for c in changed:
                        console.print(f"  {c['label']}: {c['from']} → {c['to']}", highlight=False)
                    typer.confirm("Kaydedilsin mi? (mevcut içerik yedeklenir)", abort=True)
                bk = backup_slots(g, [s], slot_label(s))
                g.store_patch(buf, s)  # edit buffer re-checked before the save, slot verified after
                slot_cache.remember_write(slot_label(s), buf)
                g.select_patch(s)
                out = {"slot": slot_label(s), "name": name, "saved": True, "changed": changed, "backup": str(bk)}
    except Exception as e:
        if not as_json:
            raise
        emit(ERROR, {"message": str(e), "kind": type(e).__name__})
        raise typer.Exit(1)
    if as_json:
        return emit(RESULT, out)
    if not out["saved"]:
        console.print(f"{out['slot']} zaten edit buffer ile aynı, yazılmadı.")
        return
    console.print(f"[green]{name} -> {out['slot']}[/] kaydedildi ve doğrulandı (önceki içerik: {out['backup']})")


_SAVE_FIELDS = [("preamp_a_type", "PREAMP"), ("preamp_a_gain", "GAIN"), ("preamp_a_bass", "BASS"),
                ("preamp_a_middle", "MIDDLE"), ("preamp_a_treble", "TREBLE"), ("preamp_a_presence", "PRESENCE"),
                ("preamp_a_level", "LEVEL"), ("od_ds_on_off", "OD/DS"), ("od_ds_drive", "OD DRIVE"),
                ("master_eq_low_gain", "M.EQ LOW"), ("master_eq_mid_gain", "M.EQ MID"),
                ("master_eq_high_gain", "M.EQ HIGH"), ("delay_effect_level", "DELAY LEVEL"),
                ("reverb_effect_level", "REVERB LEVEL"), ("patch_level", "PATCH LEVEL")]


def _changed_knobs(old, new) -> list[dict]:
    """The player-facing values that differ (what a guitarist turns), display units."""
    return [{"label": label, "from": str(old.get(f)), "to": str(new.get(f))}
            for f, label in _SAVE_FIELDS if old.get(f) != new.get(f)]


@gt1.command("tuner")
def gt1_tuner(multi: bool = typer.Option(False, "--multi", help="polyphonic tuner: all 6 strings at once"),
              seconds: float = typer.Option(0, "--seconds", help="stop after N seconds (0 = until Enter / Ctrl+C)"),
              as_json: bool = typer.Option(False, "--json",
                                           help="@@TUNER line per reading, stop on a stdin line or EOF (desktop app)")) -> None:
    """Live tuner from the GT-1 (the unit's own tuner, as in BOSS TONE STUDIO). The unit returns to play mode on exit."""
    import sys
    import threading
    import time

    from rich.live import Live

    from .device.gt1.client import connect
    from .device.gt1.tuner import run_tuner
    from .report import ERROR, RESULT, TUNER, emit

    stop = threading.Event()

    def watch_stdin() -> None:
        # desktop app: any line or a closed pipe (app gone) stops; terminal: Enter stops
        line = sys.stdin.readline()
        if line or as_json:
            stop.set()

    threading.Thread(target=watch_stdin, daemon=True).start()
    end = time.monotonic() + seconds if seconds > 0 else None
    should_stop = lambda: stop.is_set() or (end is not None and time.monotonic() > end)
    mode = "multi" if multi else "single"

    if as_json:
        try:
            with connect() as g:
                emit(TUNER, {"kind": "start", "mode": mode})
                reason = run_tuner(g, mode, lambda ev: emit(TUNER, ev), should_stop)
            emit(RESULT, {"reason": reason})
        except Exception as e:
            emit(ERROR, {"message": str(e), "kind": type(e).__name__})
            raise typer.Exit(1)
        return

    strings: dict[int, dict] = {}

    def render(ev: dict | None = None) -> str:
        if ev and ev["kind"] == "multi":
            strings[ev["string"]] = ev
        if multi:
            return "  ".join(_tuner_cell(strings.get(n)) for n in range(6, 0, -1))
        return _tuner_cell(ev, meter=True)

    console.print(f"[bold]GT-1 tuner[/] ({'çoklu' if multi else 'tek tel'}) — durdurmak için Enter / Ctrl+C")
    try:
        with connect() as g, Live(render(), console=console, refresh_per_second=30, transient=False) as live:
            reason = run_tuner(g, mode, lambda ev: live.update(render(ev)), should_stop)
    except KeyboardInterrupt:
        reason = "stopped"
    if reason == "device":
        console.print("tuner cihazdan kapatıldı")


def _tuner_cell(ev: dict | None, meter: bool = False) -> str:
    if not ev or ev["note"] is None:
        return "[dim]  --  [/]" + (" " * 24 if meter else "")
    color = "green" if ev["in_tune"] else "yellow" if abs(ev["cents"]) <= 15 else "red"
    text = f"[bold {color}]{ev['note']:<2}[/] {ev['cents']:+3d}"
    if meter:  # 21 cells, 5 cents each
        pos = round(ev["cents"] / 5) + 10
        text += "  [dim]♭[/]" + "".join(f"[{color}]█[/]" if i == pos else "[dim]·[/]" if i != 10 else "|"
                                         for i in range(21)) + "[dim]♯[/]"
    return text


def main() -> None:
    app()


if __name__ == "__main__":
    main()
