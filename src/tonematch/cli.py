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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
