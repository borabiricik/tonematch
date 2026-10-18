import * as React from "react";
import * as cli from "../cli";
import { Button, Led, Notice, Segmented } from "../ds";
import type { Device } from "./App";
import { friendly } from "./store";

// The GT-1's own tuner (`tonematch gt1 tuner --json`): the unit measures, we only draw its @@TUNER readings.
// Stop goes through cli.stop() so the CLI puts the unit back into play mode before it exits.

type Mode = "single" | "multi";
type Reading = { note: string | null; cents: number; in_tune: boolean };
type TunerLine = ({ kind: "single" } & Reading) | ({ kind: "multi"; string: number } & Reading) | { kind: "start"; mode: Mode };

type Props = { device: Device; busy: boolean };
type Msg = { tone: "ok" | "warn" | "danger"; title: string; text?: string } | null;

const STRINGS = [6, 5, 4, 3, 2, 1];
const tone = (r: Reading | null) => (!r || r.note === null ? "idle" : r.in_tune ? "ok" : Math.abs(r.cents) <= 15 ? "near" : "far");
const signed = (c: number) => (c > 0 ? `+${c}` : c < 0 ? `−${-c}` : "0");

export function TunerView({ device, busy }: Props) {
  const [mode, setMode] = React.useState<Mode>("single");
  const [running, setRunning] = React.useState(false);
  const [live, setLive] = React.useState(false);       // the unit confirmed tuner mode (first @@TUNER line)
  const [single, setSingle] = React.useState<Reading | null>(null);
  const [strings, setStrings] = React.useState<Record<number, Reading>>({});
  const [msg, setMsg] = React.useState<Msg>(null);
  const runningRef = React.useRef(false);

  // leaving the tab must not leave the unit in tuner mode
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
    } else if (r.code !== 0) {
      setMsg({ tone: "danger", title: "Tuner durdu", text: "Ayrıntı çıktıda." });
    }
  }

  const status = !running ? "Kapalı" : live ? (mode === "multi" ? "Çoklu tuner açık · tüm telleri birlikte çal" : "Tuner açık · bir teli çal") : "GT-1'e bağlanıyor…";
  return (
    <main className="view view-tuner">
      <div className="tuner">
        <div className="device__head">
          <div>
            <h1>Tuner</h1>
            <p className="device__sub">
              {running && <Led state={live ? "on" : "busy"} />} {status}
            </p>
          </div>
          <div className="device__tools">
            <Segmented<Mode> name="tuner-mode" value={mode} onChange={setMode}
              options={[{ value: "single", label: "Tek tel", disabled: running }, { value: "multi", label: "Çoklu", disabled: running }]} />
            {running
              ? <Button variant="primary" onClick={() => cli.stop()}>Kapat</Button>
              : <Button variant="primary" onClick={start} disabled={busy || device.refreshing}>Tuner'ı aç</Button>}
          </div>
        </div>
        {msg && <Notice tone={msg.tone} title={msg.title}>{msg.text}</Notice>}

        {mode === "single" ? <SingleMeter r={running ? single : null} /> : <MultiMeter strings={running ? strings : {}} />}

        <p className="tuner__foot">
          GT-1'in kendi tuner'ı: ölçüm cihazda yapılır. Referans (A = 440) ve tuner çıkışı (MUTE / BYPASS) cihazın
          sistem ayarlarındadır, burada değiştirilmez. Kapatınca cihaz çalma moduna döner.
        </p>
      </div>
    </main>
  );
}

function SingleMeter({ r }: { r: Reading | null }) {
  const t = tone(r);
  const has = r !== null && r.note !== null;
  return (
    <section className="tm-panel tuner-single" data-tone={t}>
      <div className="tuner-single__note" aria-live="polite">{has ? r!.note : "—"}</div>
      <div className="tuner-single__cents tm-readout">{has ? `${signed(r!.cents)} cent` : "sinyal yok"}</div>
      <div className="tuner-meter" role="meter" aria-valuemin={-50} aria-valuemax={50} aria-valuenow={has ? r!.cents : 0} aria-label="Sapma (cent)">
        <div className="tuner-meter__zone" />
        {[-50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50].map((c) => (
          <span key={c} className={`tuner-meter__tick${c % 50 === 0 ? " tuner-meter__tick--major" : ""}`} style={{ left: `${c + 50}%` }} />
        ))}
        {has && <div className="tuner-meter__needle" style={{ left: `${r!.cents + 50}%` }} />}
      </div>
      <div className="tuner-meter__scale tm-readout"><span>♭ −50</span><span>0</span><span>+50 ♯</span></div>
    </section>
  );
}

function MultiMeter({ strings }: { strings: Record<number, Reading> }) {
  return (
    <section className="tm-panel tuner-multi">
      {STRINGS.map((n) => {
        const r = strings[n] ?? null;
        const has = r !== null && r.note !== null;
        // BTS snaps +-5 cents to the center line on the poly meter
        const pos = has ? (Math.abs(r!.cents) <= 5 ? 0 : r!.cents) : 0;
        return (
          <div key={n} className="tuner-string" data-tone={tone(r)}>
            <div className="tuner-string__bar">
              <span className="tuner-string__center" />
              {has && <span className="tuner-string__mark" style={{ bottom: `${pos + 50}%` }} />}
            </div>
            <div className="tuner-string__note">{has ? r!.note : "—"}</div>
            <div className="tm-readout tuner-string__cents">{has ? signed(r!.cents) : "·"}</div>
            <div className="tm-label">{n}. tel</div>
          </div>
        );
      })}
    </section>
  );
}
