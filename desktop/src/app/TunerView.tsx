import * as React from "react";
import * as cli from "../cli";
import { Button, CentsMeter, Notice, Segmented, StringMeter, cx, signed, tunerTone, type TunerReading } from "../ds";
import { friendly, typing, useStored, type Device } from "./state";

// The GT-1's own tuner (`tonematch gt1 tuner --json`): the unit measures, we only draw its @@TUNER readings.
// Stop goes through cli.stop() so the CLI puts the unit back into play mode before it exits.
// Stage mode: read from where you sit with the guitar; Space opens and closes the tuner.

type Mode = "single" | "multi";
type TunerLine = ({ kind: "single" } & TunerReading) | ({ kind: "multi"; string: number } & TunerReading) | { kind: "start"; mode: Mode };
type Ref = "EADGBE" | "DADGBE";

const STRINGS = [6, 5, 4, 3, 2, 1];
const TARGETS: Record<Ref, string[]> = { EADGBE: ["E", "A", "D", "G", "B", "E"], DADGBE: ["D", "A", "D", "G", "B", "E"] };

type Props = { device: Device; busy: boolean };
type Msg = { tone: "ok" | "warn" | "danger"; title: string; text?: string } | null;

export function TunerView({ device, busy }: Props) {
  const [mode, setMode] = useStored<Mode>("tuner-mode", "single");
  const [ref, setRef] = useStored<Ref>("tuner-ref", "EADGBE");
  const [running, setRunning] = React.useState(false);
  const [live, setLive] = React.useState(false);       // the unit confirmed tuner mode (first @@TUNER line)
  const [single, setSingle] = React.useState<TunerReading | null>(null);
  const [strings, setStrings] = React.useState<Record<number, TunerReading>>({});
  const [msg, setMsg] = React.useState<Msg>(null);
  const runningRef = React.useRef(false);

  // leaving the page must not leave the unit in tuner mode
  React.useEffect(() => () => { if (runningRef.current) cli.stop(); }, []);

  function onLine(l: cli.Line) {
    if (!l.text.startsWith("@@TUNER ")) return;
    const ev = JSON.parse(l.text.slice(8)) as TunerLine;
    if (ev.kind === "start") setLive(true);
    else if (ev.kind === "single") setSingle(ev);
    else setStrings((s) => ({ ...s, [ev.string]: ev }));
  }

  async function start() {
    setMsg(null); setSingle(null); setStrings({}); setLive(false);
    setRunning(true); runningRef.current = true;
    const args = ["gt1", "tuner", "--json", ...(mode === "multi" ? ["--multi"] : [])];
    const r = await cli.run<{ reason: string }>(args, onLine, true);
    setRunning(false); setLive(false); runningRef.current = false;
    if (r.error) {
      const f = friendly(r.error.message);
      setMsg({ tone: f.kind, title: f.title, text: f.text });
    } else if (r.result?.reason === "device") {
      setMsg({ tone: "ok", title: "Tuner cihazdan kapatıldı" });
    } else if (r.code !== 0 && !r.cancelled) {
      setMsg({ tone: "danger", title: "Tuner durdu", text: "Ayrıntı çıktıda." });
    }
  }
  const toggle = () => (running ? cli.stop() : start());
  const canStart = !busy && !device.refreshing;

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || typing(e) || (e.target as HTMLElement)?.tagName === "BUTTON") return;
      e.preventDefault();
      if (running || canStart) toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const r = running ? single : null;
  const has = !!r && r.note !== null;
  const tone = tunerTone(r);
  const status = !running ? "Kapalı" : !live ? "GT-1'e bağlanıyor…" : mode === "multi" ? "Tüm telleri birlikte çal" : has ? (r!.in_tune ? "Akortta" : r!.cents < 0 ? "Pes: teli sıkıştır" : "Tiz: teli gevşet") : "Bir teli çal";

  return (
    <section className="page tuner">
      <header className="page__head">
        <div>
          <h1 className="t-title">Tuner</h1>
          <p className="t-small page__sub">GT-1'in kendi tuner'ı: ölçümü cihaz yapar. Kapatınca cihaz çalma moduna döner.</p>
        </div>
        <div className="page__actions">
          <Segmented<Mode> name="tuner-mode" value={mode} onChange={setMode}
            options={[{ value: "single", label: "Tek tel", disabled: running }, { value: "multi", label: "Çoklu", disabled: running }]} />
          <Button variant={running ? "secondary" : "primary"} icon={running ? "stop" : "play"} kbd="Space"
            onClick={toggle} disabled={!running && !canStart}>
            {running ? "Kapat" : "Tuner'ı aç"}
          </Button>
        </div>
      </header>

      {msg && <Notice tone={msg.tone} title={msg.title}>{msg.text}</Notice>}

      {mode === "single" ? (
        <div className={cx("tuner-stage", `is-${tone}`, !running && "is-off")}>
          <div className="tuner-stage__note t-stage" aria-live="polite">{has ? r!.note : <span className="tuner-stage__rest" aria-hidden="true" />}</div>
          <div className="tuner-stage__cents t-readout-lg">{has ? `${signed(r!.cents)} cent` : " "}</div>
          <div className="tuner-stage__meter"><CentsMeter reading={r} /></div>
          <p className="t-title tuner-stage__status" role="status">{status}</p>
          {!running && <p className="t-small tuner-stage__hint">Açmak için <strong>Space</strong>.</p>}
        </div>
      ) : (
        <div className={cx("tuner-poly", !running && "is-off")}>
          {STRINGS.map((n) => <StringMeter key={n} n={n} reading={running ? strings[n] ?? null : null} target={TARGETS[ref][6 - n]} />)}
          <p className="t-title tuner-poly__status" role="status">{status}</p>
        </div>
      )}

      <footer className="tuner__ref">
        <Segmented<Ref> name="tuner-ref" label="Gitarının akordu" value={ref} onChange={setRef}
          hint="Şarkı farklı akortta olsa da gitarın bu ikisinden birinde kalır; gerisini patch'teki pitch shifter yapar."
          options={[{ value: "EADGBE", label: "E standart" }, { value: "DADGBE", label: "Drop D" }]} />
        <ol className="tuner__targets" aria-label="Teller, kalından inceye">
          {TARGETS[ref].map((note, i) => <li key={i}><span className="t-small">{6 - i}.</span><strong>{note}</strong></li>)}
        </ol>
      </footer>
    </section>
  );
}
