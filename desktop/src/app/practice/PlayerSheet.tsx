import * as React from "react";
import * as cli from "../../cli";
import { Button, Chip, Dialog, Icon, IconButton, LevelMeter, Notice, Segmented, Sheet, Sparkline, signed, toast } from "../../ds";
import { friendly, typing } from "../state";
import { Fretboard, Tab, type TabClock } from "./Tab";
import type { Exercise, NoteStatus, PracticeEvent, TakeResult } from "./types";

// One exercise on the stage (`tonematch practice play <id> --json`, interactive: Stop = cli.stop()).
// The CLI clicks the metronome through the GT-1 and judges every note; we draw its @@PRACTICE events:
// the count-in, the cursor (beat events), each note's colour, a timing strip, then the result and the
// speed ladder's question ("Sor, sonra geç": two clean takes -> "X BPM'e geçelim mi?").

type Props = {
  id: string | null;
  onClose: () => void;
  /** in a routine: the next exercise */
  next?: { title: string; go: () => void } | null;
  onTake?: (r: TakeResult) => void;
};

type Phase =
  | { kind: "loading" } | { kind: "idle" } | { kind: "connecting" }
  | { kind: "count"; n: number } | { kind: "play" }
  | { kind: "done"; result: TakeResult } | { kind: "error"; title: string; text: string; tone: "warn" | "danger" };

const LOOPS = [{ value: "0", label: "≈30 sn" }, { value: "2", label: "2 tur" }, { value: "4", label: "4 tur" }, { value: "8", label: "8 tur" }];
const STATUS_TEXT: Record<string, string> = { hit: "Vuruşta", early: "Erken", late: "Geç", wrong: "Yanlış nota", miss: "Kaçtı" };

export function PlayerSheet({ id, onClose, next, onTake }: Props) {
  const [ex, setEx] = React.useState<Exercise | null>(null);
  const [bpm, setBpm] = React.useState(80);
  const [loops, setLoops] = React.useState("0");
  const [phase, setPhase] = React.useState<Phase>({ kind: "loading" });
  const [status, setStatus] = React.useState<Record<number, NoteStatus>>({});
  const [previous, setPrevious] = React.useState<Record<number, NoteStatus>>({});
  const [loop, setLoop] = React.useState(0);
  const [live, setLive] = React.useState({ right: 0, judged: 0, extras: 0 });
  const [timing, setTiming] = React.useState<{ dt: number; st: NoteStatus }[]>([]);
  const [level, setLevel] = React.useState(-90);
  const [active, setActive] = React.useState<number | null>(null);
  const [warnings, setWarnings] = React.useState<string[]>([]);
  const [ask, setAsk] = React.useState<TakeResult | null>(null);
  const [history, setHistory] = React.useState<number[]>([]);
  const clock = React.useRef<TabClock>({ beat: -99, at: 0, beatMs: 750, loopBeats: 4, running: false });
  const runningRef = React.useRef(false);

  React.useEffect(() => () => { if (runningRef.current) cli.stop(); }, []);
  React.useEffect(() => {
    if (!id) return;
    setPhase({ kind: "loading" }); setEx(null); setHistory([]); resetLive();
    cli.run<Exercise>(["practice", "exercise", id, "--json"]).then((r) => {
      if (r.result) { setEx(r.result); setBpm(r.result.working || r.result.bpm); setPhase({ kind: "idle" }); }
      else { const f = friendly(r.error?.message ?? ""); setPhase({ kind: "error", title: f.title, text: f.text, tone: f.kind === "warn" ? "warn" : "danger" }); }
    });
  }, [id]);

  const running = ["connecting", "count", "play"].includes(phase.kind);
  React.useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => {
      if (typing(e) || ask) return;
      if (e.code === "Space" && (e.target as HTMLElement)?.tagName !== "BUTTON") {
        e.preventDefault();
        if (running) cli.stop(); else if (ex) start();
      } else if (!running && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
        e.preventDefault();
        nudge((e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 5 : 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!id) return null;

  function resetLive() {
    setStatus({}); setPrevious({}); setLoop(0); setLive({ right: 0, judged: 0, extras: 0 }); setTiming([]); setActive(null);
  }
  const nudge = (d: number) => setBpm((b) => Math.max(30, Math.min(300, b + d)));

  async function start(at?: number) {
    if (!ex) return;
    const tempo = at ?? bpm;
    resetLive(); setWarnings([]); setPhase({ kind: "connecting" });
    runningRef.current = true;
    let curLoop = 0;
    const r = await cli.run<TakeResult>(["practice", "play", ex.id, "--bpm", String(tempo), "--loops", loops, "--json"], (l) => {
      if (!l.text.startsWith("@@PRACTICE ")) return;
      const ev = JSON.parse(l.text.slice(11)) as PracticeEvent;
      if (ev.kind === "ready") setWarnings(ev.warnings);
      else if (ev.kind === "start") {
        clock.current = { beat: -ev.count_in - 1, at: performance.now(), beatMs: ev.beat_s * 1000, loopBeats: ev.beats, running: true };
      } else if (ev.kind === "beat") {
        clock.current = { ...clock.current, beat: ev.beat, at: performance.now() };
        if (ev.count_in) setPhase({ kind: "count", n: -ev.beat });
        else {
          if (ev.beat === 0) setPhase({ kind: "play" });
          if (ev.loop !== curLoop) {
            curLoop = ev.loop;
            setLoop(ev.loop);
            setStatus((s) => { setPrevious(s); return {}; });
          }
        }
      } else if (ev.kind === "note") {
        if (ev.status === "ring") return;
        if (ev.status === "extra") { setLive((v) => ({ ...v, extras: v.extras + 1 })); return; }
        if (ev.j === undefined) return;
        const j = ev.j;
        if (ev.loop === curLoop) setStatus((s) => ({ ...s, [j]: ev.status }));
        else setPrevious((s) => ({ ...s, [j]: ev.status }));
        if (ev.status !== "miss") setActive(j);
        setLive((v) => ({ ...v, judged: v.judged + 1, right: v.right + (["hit", "early", "late"].includes(ev.status) ? 1 : 0) }));
        if (ev.dt_ms !== undefined && ev.status !== "wrong") setTiming((t) => [...t.slice(-23), { dt: ev.dt_ms!, st: ev.status }]);
      } else if (ev.kind === "level") setLevel(ev.db);
    }, true);
    runningRef.current = false;
    clock.current = { ...clock.current, running: false };
    if (r.result) {
      const res = r.result;
      setPhase({ kind: "done", result: res });
      if (res.notes) setHistory((h) => [...h, Math.round(res.accuracy * 100)]);
      onTake?.(res);
      if (res.decision?.suggest === "faster") setAsk(res);
    } else if (r.cancelled) {
      setPhase({ kind: "idle" });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setPhase({ kind: "error", title: f.title, text: f.text, tone: f.kind === "warn" ? "warn" : "danger" });
    }
  }

  async function accept(to: number, andPlay: boolean) {
    setAsk(null);
    if (!ex) return;
    const r = await cli.run(["practice", "set-bpm", ex.id, String(to), "--json"]);
    if (r.error) { toast({ tone: "danger", title: "Tempo kaydedilemedi", text: r.error.message }); return; }
    setBpm(to);
    if (andPlay) start(to);
  }

  async function listen() {
    if (!ex) return;
    const r = await cli.run(["practice", "reference", ex.id, "--bpm", String(bpm), "--json"]);
    if (r.error) { const f = friendly(r.error.message); toast({ tone: "danger", title: f.title, text: f.text }); }
  }

  const acc = live.judged ? Math.round((live.right / live.judged) * 100) : null;
  const root = ex?.key ? keyPc(ex.key) : null;
  const activeNote = active !== null && ex ? ex.notes[active] : null;

  return (
    <Sheet open title={ex ? ex.title : "Egzersiz"} sub={ex ? `${ex.group} · ${ex.subtitle}` : undefined}
      onClose={onClose} locked={running}
      actions={<>
        {running && <Button variant="danger" icon="stop" kbd="Space" onClick={() => cli.stop()}>Durdur</Button>}
      </>}>
      <div className="prac">
        <div className="prac__stage">
          {ex && (
            <div className="prac__controls">
              <div className="bpm" aria-label="Tempo">
                <IconButton icon="minus" label="Tempo −1 (←, Shift: −5)" onClick={() => nudge(-1)} disabled={running} />
                <div className="bpm__value"><span className="t-stage">{bpm}</span><span className="t-label">BPM</span></div>
                <IconButton icon="plus" label="Tempo +1 (→, Shift: +5)" onClick={() => nudge(1)} disabled={running} />
              </div>
              <div className="prac__meta">
                <Chip tone="neutral">Rekor {ex.best || "—"}</Chip>
                <Chip tone="neutral">Hedef {ex.goal_bpm}</Chip>
                <Segmented name="loops" label="Uzunluk" value={loops} onChange={setLoops} options={LOOPS.map((o) => ({ ...o, disabled: running }))} size="sm" />
              </div>
              <div className="prac__go">
                {ex.family === "solo" && !running && <Button icon="ear" onClick={listen}>Dinle ({bpm})</Button>}
                {!running && phase.kind !== "done" && <Button variant="primary" size="lg" icon="play" kbd="Space" onClick={() => start()}>Başla</Button>}
              </div>
            </div>
          )}

          {warnings.map((w) => <Notice key={w} tone="warn" title="Dikkat">{w}</Notice>)}
          {phase.kind === "error" && <Notice tone={phase.tone} title={phase.title}>{phase.text}</Notice>}

          <div className={`prac__board is-${phase.kind}`}>
            {phase.kind === "loading" && <div className="prac__center"><span className="tm-spinner" /><p className="t-title">Egzersiz hazırlanıyor…</p></div>}
            {(phase.kind === "connecting") && <div className="prac__overlay"><span className="tm-spinner" /><p className="t-title">GT-1'e bağlanıyor…</p></div>}
            {phase.kind === "count" && <div className="prac__overlay"><span className="t-stage prac__count" key={phase.n}>{phase.n}</span></div>}
            {ex && <Tab notes={ex.notes} beats={ex.beats} perBeat={ex.per_beat} status={status} previous={previous} clock={clock}
              trouble={phase.kind === "done" ? phase.result.trouble : undefined} />}
          </div>

          {ex && (
            <div className="prac__live">
              <div className="prac__stat"><span className="t-label">Doğru</span><span className="t-readout-lg">{acc === null ? "—" : `%${acc}`}</span></div>
              <div className="prac__stat"><span className="t-label">Tur</span><span className="t-readout-lg">{running || phase.kind === "done" ? loop + 1 : "—"}</span></div>
              <div className="prac__stat"><span className="t-label">Fazla nota</span><span className="t-readout-lg">{live.extras}</span></div>
              <TimingStrip points={timing} />
              <div className="prac__level"><span className="t-label">Seviye</span><LevelMeter db={running ? level : -90} /></div>
            </div>
          )}

          {phase.kind === "done" && <Result r={phase.result} history={history} onAgain={() => start()} next={next}
            onSlower={(to) => accept(to, false)} />}
        </div>

        {ex && (
          <aside className="prac__side">
            <section>
              <h3 className="t-heading">Odak</h3>
              <p className="t-body prac__focus">{ex.focus}</p>
            </section>
            <section>
              <h3 className="t-heading">Şekil</h3>
              <Fretboard notes={ex.notes} root={root} active={activeNote} compact />
              {root !== null && <p className="t-small prac__muted">Dolu noktalar kök ({ex.key}).</p>}
            </section>
            <section>
              <h3 className="t-heading">Hocanın notu</h3>
              <ul className="prac__tips">{ex.tips.map((t) => <li key={t} className="t-small">{t}</li>)}</ul>
            </section>
            <section className="prac__keys t-small">
              <Icon name="keyboard" /><span>Space başlat/durdur · ←/→ tempo (Shift ±5)</span>
            </section>
          </aside>
        )}
      </div>

      <Dialog open={!!ask} title={ask?.decision?.message ?? ""} confirmLabel={`Evet, ${ask?.decision?.to_bpm} BPM`}
        cancelLabel={`Hayır, ${ask?.bpm} BPM'de kal`} onCancel={() => setAsk(null)}
        onConfirm={() => ask?.decision && accept(ask.decision.to_bpm, true)}>
        <p>Son tur %{Math.round((ask?.accuracy ?? 0) * 100)} doğru, notaların %{Math.round((ask?.on_time ?? 0) * 100)}'i vuruşta.
          Evet dersen yeni tempo kaydedilir ve hemen başlar.</p>
        {next && <p className="t-small">Ya da bu egzersizi bırakıp sıradakine geç: <strong>{next.title}</strong>.</p>}
        {next && <Button variant="ghost" icon="arrow-right" onClick={() => { setAsk(null); next.go(); }}>Sonraki egzersize geç</Button>}
      </Dialog>
    </Sheet>
  );
}

function Result({ r, history, onAgain, next, onSlower }: {
  r: TakeResult; history: number[]; onAgain: () => void; next?: Props["next"]; onSlower: (to: number) => void;
}) {
  const d = r.decision;
  const lean = r.mean_ms === null ? "" : Math.abs(r.mean_ms) < 8 ? "tam vuruşta" : r.mean_ms < 0 ? `${Math.abs(r.mean_ms).toFixed(0)} ms önde (acele)` : `${r.mean_ms.toFixed(0)} ms geride`;
  return (
    <div className="prac__result">
      <div className="prac__score">
        <div>
          <span className="t-label prac__muted">{r.bpm} BPM · {r.per_loop.length} tur{r.stopped ? " (durduruldu)" : ""}</span>
          <div className="prac__big"><span className="t-stage">%{Math.round(r.accuracy * 100)}</span><span className="t-title">doğru</span></div>
          <p className="t-body">Vuruşta %{Math.round(r.on_time * 100)} · {lean}{r.spread_ms !== null ? ` · yayılım ±${r.spread_ms.toFixed(0)} ms` : ""} · fazla nota {r.extras}</p>
        </div>
        <div className="prac__score-actions">
          <Button variant="primary" size="lg" icon="play" kbd="Space" onClick={onAgain}>Tekrar</Button>
          {next && <Button icon="arrow-right" onClick={next.go}>Sonraki: {next.title}</Button>}
        </div>
      </div>
      {d && <Notice tone={d.suggest === "slower" ? "warn" : d.clean ? "ok" : "info"} title={d.clean ? "Temiz tur" : d.suggest === "slower" ? "Yavaşlayalım" : "Devam"}
        action={d.suggest === "slower" ? <Button size="sm" onClick={() => onSlower(d.to_bpm)}>{d.to_bpm} BPM'e in</Button> : undefined}>{d.message}</Notice>}
      <div className="prac__counts">
        {(["hit", "early", "late", "wrong", "miss"] as const).map((k) => (
          <span key={k} className={`prac__count-chip is-${k}`}><b>{r.counts[k] ?? 0}</b> {STATUS_TEXT[k]}</span>
        ))}
      </div>
      {r.per_loop.length > 1 && <div className="prac__loops"><span className="t-label">Tur tur doğruluk</span>
        <Sparkline rising values={r.per_loop.map((v) => v * 100)} width={260} height={44} label={`Turlar: ${r.per_loop.map((v) => Math.round(v * 100)).join(", ")}`} /></div>}
      {history.length > 1 && <p className="t-small prac__muted">Bu oturumdaki turlar: {history.map((h) => `%${h}`).join(" → ")}</p>}
      {r.trouble && r.trouble.length > 0 && <p className="t-small">Kırmızı çerçeveli notalar birden fazla turda kaçtı: o geçişi yavaşta ayrıca çalış.</p>}
    </div>
  );
}

/** The last notes' timing on a -60..+60 ms strip: left = early, right = late. */
function TimingStrip({ points }: { points: { dt: number; st: NoteStatus }[] }) {
  const pos = (dt: number) => 50 + (Math.max(-60, Math.min(60, dt)) / 60) * 50;
  const mean = points.length ? points.reduce((a, p) => a + p.dt, 0) / points.length : null;
  return (
    <div className="timing" aria-label={mean === null ? "Zamanlama" : `Zamanlama ortalama ${signed(Math.round(mean))} ms`}>
      <span className="t-label">Zamanlama</span>
      <div className="timing__strip">
        <span className="timing__zone" />
        <span className="timing__mid" />
        {points.map((p, i) => <span key={i} className={`timing__dot is-${p.st}`} style={{ left: `${pos(p.dt)}%`, opacity: 0.35 + (0.65 * (i + 1)) / points.length }} />)}
        {mean !== null && <span className="timing__mean" style={{ left: `${pos(mean)}%` }} />}
      </div>
      <div className="timing__ends t-small"><span>erken</span><span>{mean === null ? "" : `${signed(Math.round(mean))} ms`}</span><span>geç</span></div>
    </div>
  );
}

const PCS: Record<string, number> = { C: 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, F: 5, "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11 };
const keyPc = (k: string) => PCS[k] ?? null;
