import * as React from "react";
import * as cli from "../../cli";
import { Button, Notice, Segmented, Sheet, signed } from "../../ds";
import { friendly, typing } from "../state";
import { Fretboard } from "./Tab";
import { QUIZ_HINTS, QUIZ_NAMES, type PracticeEvent, type QuizEvent, type QuizKind, type QuizResult } from "./types";

// Theory / ear drills answered on the guitar (`tonematch practice quiz <kind> --json`, interactive) and the
// timing calibration (`practice latency --json`). The CLI asks, listens and judges; we show its events.

type Q = Extract<QuizEvent, { kind: "question" }>;
type A = Extract<QuizEvent, { kind: "answer" }>;
type State =
  | { kind: "idle" } | { kind: "connecting" }
  | { kind: "ask"; q: Q; heard: string[]; answer?: A }
  | { kind: "done"; result: QuizResult } | { kind: "error"; title: string; text: string };

const COUNTS = [{ value: "5", label: "5" }, { value: "10", label: "10" }, { value: "20", label: "20" }];

export function QuizSheet({ kind, onClose, onDone }: { kind: QuizKind | null; onClose: () => void; onDone?: () => void }) {
  const [count, setCount] = React.useState("10");
  const [level, setLevel] = React.useState("1");
  const [state, setState] = React.useState<State>({ kind: "idle" });
  const [log, setLog] = React.useState<A[]>([]);
  const runningRef = React.useRef(false);
  React.useEffect(() => () => { if (runningRef.current) cli.stop(); }, []);
  React.useEffect(() => { setState({ kind: "idle" }); setLog([]); }, [kind]);
  const running = state.kind === "connecting" || state.kind === "ask";

  React.useEffect(() => {
    if (!kind) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || typing(e) || (e.target as HTMLElement)?.tagName === "BUTTON") return;
      e.preventDefault();
      if (running) cli.stop(); else start();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  if (!kind) return null;

  async function start() {
    setLog([]); setState({ kind: "connecting" }); runningRef.current = true;
    const r = await cli.run<QuizResult>(["practice", "quiz", kind!, "--count", count, "--level", level, "--json"], (l) => {
      if (!l.text.startsWith("@@PRACTICE ")) return;
      const ev = JSON.parse(l.text.slice(11)) as PracticeEvent;
      if (ev.kind === "question") setState({ kind: "ask", q: ev, heard: [] });
      else if (ev.kind === "heard") setState((s) => (s.kind === "ask" ? { ...s, heard: [...s.heard, ev.note] } : s));
      else if (ev.kind === "answer") {
        setState((s) => (s.kind === "ask" ? { ...s, answer: ev } : s));
        setLog((g) => [...g, ev]);
      }
    }, true);
    runningRef.current = false;
    if (r.result) { setState({ kind: "done", result: r.result }); onDone?.(); }
    else if (r.cancelled) setState({ kind: "idle" });
    else { const f = friendly(r.error?.message ?? ""); setState({ kind: "error", title: f.title, text: f.text }); }
  }

  const right = log.filter((a) => a.right).length;
  return (
    <Sheet open title={`Teori ve kulak · ${QUIZ_NAMES[kind]}`} sub={QUIZ_HINTS[kind]} onClose={onClose} locked={running}
      actions={running ? <Button variant="danger" icon="stop" kbd="Space" onClick={() => cli.stop()}>Durdur</Button> : undefined}>
      <div className="quiz">
        {(state.kind === "idle" || state.kind === "error" || state.kind === "done") && (
          <div className="quiz__intro">
            {state.kind === "error" && <Notice tone="danger" title={state.title}>{state.text}</Notice>}
            {state.kind === "done" && (
              <div className="quiz__done">
                <span className="t-stage">{state.result.right}/{state.result.asked}</span>
                <p className="t-title">doğru{state.result.mean_ms ? ` · ortalama ${(state.result.mean_ms / 1000).toFixed(1)} sn` : ""}</p>
                <p className="t-small quiz__muted">Kaçırdıkların bir sonraki turda daha sık gelecek.</p>
              </div>
            )}
            <div className="quiz__opts">
              <Segmented name="quiz-count" label="Soru" value={count} onChange={setCount} options={COUNTS} />
              <Segmented name="quiz-level" label="Seviye" value={level} onChange={setLevel}
                options={[{ value: "1", label: "Temel" }, { value: "2", label: "Hepsi" }]} />
              <Button variant="primary" size="lg" icon="play" kbd="Space" onClick={start}>{state.kind === "done" ? "Tekrar" : "Başla"}</Button>
            </div>
            <p className="t-small quiz__muted">Soruyu cevaplamak için gitarda çal; temiz, tek nota. Kulaktan tekrarda notalar amfiden çalar.</p>
          </div>
        )}
        {state.kind === "connecting" && <div className="quiz__center"><span className="tm-spinner" /><p className="t-title">GT-1'e bağlanıyor…</p></div>}
        {state.kind === "ask" && (
          <div className={`quiz__card ${state.answer ? (state.answer.right ? "is-right" : "is-wrong") : ""}`}>
            <span className="t-label">Soru {state.q.n}</span>
            <p className="t-display quiz__prompt">{state.q.prompt}</p>
            {state.q.string && <Fretboard notes={[]} highlightString={state.q.string} />}
            <div className="quiz__heard">
              {state.heard.length === 0 && !state.answer && <span className="t-body quiz__muted">{state.q.play ? "Dinle…" : "Çal…"}</span>}
              {state.heard.map((n, i) => <span key={i} className="quiz__note t-readout-lg">{n}</span>)}
            </div>
            {state.answer && (
              <div className="quiz__answer">
                <span className="t-title">{state.answer.right ? "Doğru" : "Yanlış"}</span>
                <span className="t-body">{state.answer.answer}{state.answer.ms ? ` · ${(state.answer.ms / 1000).toFixed(1)} sn` : ""}</span>
                {state.q.frets && state.q.string && (
                  <Fretboard notes={state.q.frets.map((f) => ({ string: state.q.string!, fret: f, midi: 0 }))} highlightString={state.q.string} compact />
                )}
              </div>
            )}
          </div>
        )}
        {log.length > 0 && (
          <div className="quiz__log" aria-label="Cevaplar">
            {log.map((a) => <span key={a.n} className={a.right ? "is-right" : "is-wrong"} title={a.answer}>{a.n}</span>)}
            <span className="t-small quiz__muted">{right}/{log.length}</span>
          </div>
        )}
      </div>
    </Sheet>
  );
}

/** Timing calibration: play one muted note on each of 16 clicks; the median offset becomes the player's latency. */
export function LatencySheet({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: (ms: number) => void }) {
  const [taps, setTaps] = React.useState<number[]>([]);
  const [beat, setBeat] = React.useState<number | null>(null);
  const [state, setState] = React.useState<"idle" | "run" | "done" | "error">("idle");
  const [msg, setMsg] = React.useState("");
  const [result, setResult] = React.useState<number | null>(null);
  if (!open) return null;

  async function start() {
    setTaps([]); setBeat(null); setResult(null); setState("run");
    const r = await cli.run<{ offset_ms: number | null; used: number }>(["practice", "latency", "--json"], (l) => {
      if (!l.text.startsWith("@@PRACTICE ")) return;
      const ev = JSON.parse(l.text.slice(11)) as PracticeEvent;
      if (ev.kind === "beat") setBeat(ev.beat);
      else if (ev.kind === "tap") setTaps((t) => [...t, ev.dt_ms]);
    }, true);
    if (r.result) {
      setState("done");
      setResult(r.result.offset_ms);
      if (r.result.offset_ms !== null) onSaved(r.result.offset_ms);
      else setMsg(`Sadece ${r.result.used} vuruş duyuldu; her tıkta bir nota çal.`);
    } else if (r.cancelled) setState("idle");
    else { setState("error"); setMsg(friendly(r.error?.message ?? "").text); }
  }

  return (
    <Sheet open title="Gecikme testi" sub="16 tık, 80 BPM: her tıkta tek bir (susturulmuş) nota çal. Ortalama farkın kaydedilir; zamanlama sonra buna göre ölçülür."
      onClose={onClose} locked={state === "run"}
      actions={state === "run" ? <Button variant="danger" icon="stop" onClick={() => cli.stop()}>Durdur</Button> : undefined}>
      <div className="quiz">
        <div className="quiz__center">
          {state === "run" && <span className="t-stage">{beat === null ? "…" : beat < 0 ? -beat : beat + 1}</span>}
          {state === "done" && result !== null && <><span className="t-stage">{signed(Math.round(result))} ms</span><p className="t-title">kaydedildi</p></>}
          {(state === "error" || (state === "done" && result === null)) && <Notice tone="warn" title="Ölçülemedi">{msg}</Notice>}
          <div className="timing__strip timing__strip--wide">
            <span className="timing__zone" /><span className="timing__mid" />
            {taps.map((t, i) => <span key={i} className="timing__dot is-hit" style={{ left: `${50 + Math.max(-100, Math.min(100, t)) / 2}%` }} />)}
          </div>
          {state !== "run" && <Button variant="primary" size="lg" icon="play" onClick={start}>{state === "idle" ? "Başla" : "Tekrar"}</Button>}
        </div>
      </div>
    </Sheet>
  );
}
