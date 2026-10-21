import * as React from "react";
import * as cli from "../cli";
import { Button, CentsMeter, Notice, Segmented, StringMeter, cx, signed, type TunerReading } from "../ds";
import { STRINGS, guessString, stringState, target, toneOf, type Ref, type StringState } from "../tunerStrings";
import { friendly, typing, useStored, type Device } from "./state";

// The GT-1's own tuner (`tonematch gt1 tuner --json`): the unit measures, we only draw its @@TUNER readings.
// Stop goes through cli.stop() so the CLI puts the unit back into play mode before it exits.
// Stage mode: read from where you sit with the guitar; Space opens and closes the tuner.
// 3D view (default): the player's Les Paul; the camera flies to the headstock while the tuner is on and the
// key of the string being tuned shows which way to turn. Single mode guesses the string from the note;
// a click on a string (in the list or on the model) pins it.

const GuitarStage = React.lazy(() => import("./guitar/GuitarStage"));

type Mode = "single" | "multi";
type View = "3d" | "flat";
type TunerLine = ({ kind: "single" } & TunerReading) | ({ kind: "multi"; string: number } & TunerReading) | { kind: "start"; mode: Mode };

type Props = { device: Device; busy: boolean };
type Msg = { tone: "ok" | "warn" | "danger"; title: string; text?: string } | null;

const TURN_STATUS = { hold: "Akortta", tighten: "Pes: teli sıkıştır", loosen: "Tiz: teli gevşet" } as const;

export function TunerView({ device, busy }: Props) {
  const [mode, setMode] = useStored<Mode>("tuner-mode", "single");
  const [ref, setRef] = useStored<Ref>("tuner-ref", "EADGBE");
  const [view, setView] = useStored<View>("tuner-view", "3d");
  const [no3d, setNo3d] = React.useState(false);
  const [pinned, setPinned] = React.useState<number | null>(null);
  const [running, setRunning] = React.useState(false);
  const [live, setLive] = React.useState(false);       // the unit confirmed tuner mode (first @@TUNER line)
  const [single, setSingle] = React.useState<TunerReading | null>(null);
  const [strings, setStrings] = React.useState<Record<number, TunerReading>>({});
  const [msg, setMsg] = React.useState<Msg>(null);
  const runningRef = React.useRef(false);
  const lastString = React.useRef<number | null>(null);

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
  const pick = (n: number) => setPinned((p) => (p === n ? null : n));

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
  const current: StringState | null = has ? stringState(pinned ?? guessString(r!.note!, r!.cents, ref, lastString.current), r, ref) : null;
  React.useEffect(() => { if (current) lastString.current = current.string; });
  const multi = running ? STRINGS.map((n) => stringState(n, strings[n], ref)).filter((s): s is StringState => !!s) : [];
  const shows = mode === "single" ? (current ? [current] : []) : multi;
  // the 3D close-up leans toward the side of the last string heard (kept between plucks so it does not swing)
  const lean = React.useRef<-1 | 0 | 1>(0);
  if (!running || mode === "multi") lean.current = 0;
  else if (current) lean.current = current.string >= 4 ? -1 : 1;

  const tone = current ? toneOf(current) : "idle";
  const status = !running ? "Kapalı" : !live ? "GT-1'e bağlanıyor…" : mode === "multi" ? "Tüm telleri birlikte çal" : current ? TURN_STATUS[current.turn] : "Bir teli çal";
  const use3d = view === "3d" && !no3d;

  return (
    <section className="page tuner">
      <header className="page__head">
        <div>
          <h1 className="t-title">Tuner</h1>
          <p className="t-small page__sub">GT-1'in kendi tuner'ı: ölçümü cihaz yapar. Kapatınca cihaz çalma moduna döner.</p>
        </div>
        <div className="page__actions">
          <Segmented<View> name="tuner-view" value={use3d ? "3d" : "flat"} onChange={setView}
            options={[{ value: "3d", label: "3D", disabled: no3d }, { value: "flat", label: "Klasik" }]} />
          <Segmented<Mode> name="tuner-mode" value={mode} onChange={setMode}
            options={[{ value: "single", label: "Tek tel", disabled: running }, { value: "multi", label: "Çoklu", disabled: running }]} />
          <Button variant={running ? "secondary" : "primary"} icon={running ? "stop" : "play"} kbd="Space"
            onClick={toggle} disabled={!running && !canStart}>
            {running ? "Kapat" : "Tuner'ı aç"}
          </Button>
        </div>
      </header>

      {msg && <Notice tone={msg.tone} title={msg.title}>{msg.text}</Notice>}
      {no3d && view === "3d" && <Notice tone="warn" title="3D görünüm açılamadı">Bu bilgisayarda WebGL kullanılamıyor; klasik tuner gösteriliyor.</Notice>}

      <div className={cx("tuner-body", use3d && "has-3d", `is-${mode}`)}>
        {use3d && (
          <div className="tuner-scene">
            <React.Suspense fallback={<p className="tuner-scene__loading t-small">Gitar yükleniyor…</p>}>
              <GuitarStage focus={running ? "head" : "body"} lean={lean.current} shows={shows} targetOf={(n) => target(ref, n)}
                onPick={mode === "single" ? pick : undefined} onFail={() => setNo3d(true)} />
            </React.Suspense>
            <p className="tuner-scene__hint t-small" aria-hidden="true">
              Sürükle: döndür · Tekerlek: yakınlaş · Çift tık: görünümü sıfırla{mode === "single" ? " · Mandala tıkla: teli seç" : ""}
            </p>
          </div>
        )}

        {mode === "single" ? (
          <div className={cx("tuner-stage", `is-${tone}`, !running && "is-off")}>
            <div className="tuner-stage__note t-stage" aria-live="polite">{has ? r!.note : <span className="tuner-stage__rest" aria-hidden="true" />}</div>
            <div className="tuner-stage__cents t-readout-lg">{has ? `${signed(r!.cents)} cent` : " "}</div>
            <div className="tuner-stage__meter"><CentsMeter reading={r} /></div>
            <p className="t-title tuner-stage__status" role="status">{status}</p>
            <p className="t-small tuner-stage__string">
              {current ? `${current.string}. tel · hedef ${target(ref, current.string)}${pinned ? " (seçili)" : ""}` : pinned ? `${pinned}. tel seçili` : " "}
            </p>
            {!running && <p className="t-small tuner-stage__hint">Açmak için <strong>Space</strong>.</p>}
          </div>
        ) : (
          <div className={cx("tuner-poly", !running && "is-off")}>
            {STRINGS.map((n) => <StringMeter key={n} n={n} reading={running ? strings[n] ?? null : null} target={target(ref, n)} />)}
            <p className="t-title tuner-poly__status" role="status">{status}</p>
          </div>
        )}
      </div>

      <footer className="tuner__ref">
        <Segmented<Ref> name="tuner-ref" label="Gitarının akordu" value={ref} onChange={setRef}
          hint="Şarkı farklı akortta olsa da gitarın bu ikisinden birinde kalır; gerisini patch'teki pitch shifter yapar."
          options={[{ value: "EADGBE", label: "E standart" }, { value: "DADGBE", label: "Drop D" }]} />
        <div className="tuner__strings">
          <ol className="tuner__targets" aria-label="Teller, kalından inceye">
            {STRINGS.map((n) => (
              <li key={n}>
                <button type="button" className={cx("tuner__target", current?.string === n && "is-live")}
                  aria-pressed={pinned === n} disabled={mode !== "single"} onClick={() => pick(n)}
                  title={pinned === n ? "Otomatiğe dön" : `${n}. teli akort ediyorum`}>
                  <span className="t-small">{n}.</span><strong>{target(ref, n)}</strong>
                </button>
              </li>
            ))}
          </ol>
          {mode === "single" && (
            <p className="t-small tuner__pin">{pinned ? `${pinned}. tel seçili. Otomatik için tekrar tıkla.` : "Tel nottan otomatik bulunur; tıklayarak sabitle."}</p>
          )}
        </div>
      </footer>
    </section>
  );
}
