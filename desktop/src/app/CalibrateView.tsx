import * as React from "react";
import * as cli from "../cli";
import { Button, Dialog, Led, Notice, Segmented, SlotPicker, Timeline, mmss, roleName, slotLabel } from "../ds";
import { friendly } from "./store";

// Play-to-calibrate (`tonematch calibrate --json`, docs/07 item 0). The CLI selects the patch, counts down,
// records the GT-1's USB output and compares it with the song's guitar; we only draw its @@CALIB stream and result.
// Measuring writes nothing; "Slota kaydet" saves the edit buffer (knobs turned on the unit) with `gt1 save`:
// backup, write, read back + verify, refused when the unit has another patch selected (--expect-name).

export type CalTarget = { source: string; role: string; slot: string | null; ctl: "off" | "on" | undefined; patch: string };

type CalEvent =
  | { kind: "info"; message: string; phase?: undefined }
  | { kind: "info"; message: string; phase: "ready"; patch: string; amp: string; slot: string | null; ctl_on: boolean; duration: number; segments: number[][] }
  | { kind: "info"; message: string; phase: "countdown"; n: number }
  | { kind: "info"; message: string; phase: "record"; seconds: number }
  | { kind: "info"; message: string; phase: "measure" }
  | { kind: "level"; db: number };

type Axis = "drive" | "mid_scoop_db" | "presence_db" | "body_db" | "fizz_db" | "low_depth_db";
type CalResult = {
  title: string; role: string; ctl_on: boolean;
  patch: { name: string; amp: string; slot: string | null };
  values: Record<Axis, [number, number]>;
  fx: { delay_ms: [number | null, number | null]; reverb: [string, string] };
  compare: {
    diff: Record<Axis, number>; spectral_distance_db: number; close: Axis[];
    hints: { axis: Axis; value: number; knob: string; direction: "up" | "down"; text: string }[];
  };
  played_seconds: number; level_db: number; warnings: string[]; wav: string;
};

type Ready = Extract<CalEvent, { phase: "ready" }>;
type SaveResult = { slot: string; name: string; saved: boolean; changed: { label: string; from: string; to: string }[]; backup: string | null };
type SaveMsg = { tone: "ok" | "warn" | "danger"; title: string; text: string } | null;
type State =
  | { kind: "connecting"; ready?: Ready }
  | { kind: "countdown"; ready?: Ready; n: number }
  | { kind: "record"; ready?: Ready; seconds: number; start: number; db: number; peak: number }
  | { kind: "measure"; ready?: Ready }
  | { kind: "done"; ready?: Ready; result: CalResult }
  | { kind: "error"; ready?: Ready; title: string; text: string; tone: "warn" | "danger" };

const AXES: { key: Axis; label: string; hint: string }[] = [
  { key: "drive", label: "Drive", hint: "distorsiyon miktarı, 0–1" },
  { key: "mid_scoop_db", label: "Orta", hint: "400–1200 Hz; eksi = oyuk" },
  { key: "presence_db", label: "Presence", hint: "2–4.5 kHz ısırık" },
  { key: "body_db", label: "Gövde", hint: "200–450 Hz alt-orta" },
  { key: "fizz_db", label: "Fizz", hint: "5–8 kHz üst tiz" },
  { key: "low_depth_db", label: "Alt uç", hint: "60–110 Hz; stemde bas sızıntısı olabilir" },
];
const LENGTHS = [{ value: "15", label: "15 sn" }, { value: "20", label: "20 sn" }, { value: "30", label: "30 sn" }];
const fmt = (k: Axis, v: number) => (k === "drive" ? v.toFixed(2) : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`);
const signed = (k: Axis, v: number) => (v > 0 ? "+" : "") + (k === "drive" ? v.toFixed(2) : `${v.toFixed(1)} dB`).replace("-", "−");

type Props = { target: CalTarget; fallbackSlot: number; onClose: () => void; onSaved: () => void };

export function Calibration({ target, fallbackSlot, onClose, onSaved }: Props) {
  const [seconds, setSeconds] = React.useState("20");
  const [saveSlot, setSaveSlot] = React.useState(() => (target.slot ? Number(target.slot.slice(1)) : fallbackSlot));
  const [confirm, setConfirm] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [saveMsg, setSaveMsg] = React.useState<SaveMsg>(null);
  const [state, setState] = React.useState<State | null>(null);
  const [round, setRound] = React.useState(0);
  const history = React.useRef<number[]>([]);
  const [, tick] = React.useReducer((x: number) => x + 1, 0);
  const runningRef = React.useRef(false);

  React.useEffect(() => () => { if (runningRef.current) cli.cancel(); }, []);
  React.useEffect(() => {
    if (state?.kind !== "record") return;
    const t = setInterval(tick, 200);
    return () => clearInterval(t);
  }, [state?.kind]);

  async function start() {
    let ready: Ready | undefined = state?.ready;
    setState({ kind: "connecting", ready });
    runningRef.current = true;
    const args = ["calibrate", target.source, "--role", target.role, "--seconds", seconds, "--json",
      // CTL is off after selecting a patch: give the player time to step on it for the second tone
      "--countdown", target.ctl === "on" ? "5" : "3"];
    // select the slot on the first round only: later rounds keep the knobs the player turned on the unit
    if (target.slot && round === 0) args.push("--slot", target.slot);
    const r = await cli.run<CalResult>(args, (l) => {
      if (!l.text.startsWith("@@CALIB ")) return;
      const ev = JSON.parse(l.text.slice(8)) as CalEvent;
      if (ev.kind === "level") {
        setState((s) => (s?.kind === "record" ? { ...s, db: ev.db, peak: Math.max(s.peak, ev.db) } : s));
      } else if (ev.phase === "ready") {
        ready = ev;
        setState((s) => (s ? { ...s, ready: ev } : s));
      } else if (ev.phase === "countdown") {
        setState({ kind: "countdown", ready, n: ev.n });
      } else if (ev.phase === "record") {
        setState({ kind: "record", ready, seconds: ev.seconds, start: Date.now(), db: -90, peak: -90 });
      } else if (ev.phase === "measure") {
        setState({ kind: "measure", ready });
      }
    });
    runningRef.current = false;
    if (r.result) {
      history.current = [...history.current, r.result.compare.spectral_distance_db];
      setRound((n) => n + 1);
      setState({ kind: "done", ready, result: r.result });
    } else if (r.cancelled) {
      setState({ kind: "error", ready, tone: "warn", title: "Kalibrasyon durduruldu", text: "Cihaza hiçbir şey yazılmadı." });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setState({ kind: "error", ready, tone: f.kind, title: f.title, text: f.text });
    }
  }

  async function save() {
    setConfirm(false); setSaving(true); setSaveMsg(null);
    const r = await cli.run<SaveResult>(["gt1", "save", slotLabel(saveSlot), "--expect-name", target.patch, "--yes", "--json"]);
    setSaving(false);
    if (r.result?.saved) {
      const ch = r.result.changed.map((c) => `${c.label} ${c.from} → ${c.to}`).join(", ");
      setSaveMsg({ tone: "ok", title: `${r.result.slot} kaydedildi ve doğrulandı`,
        text: `${ch || "Ayarlar yazıldı."} Önceki içerik yedeklendi: ${r.result.backup}` });
      onSaved();
    } else if (r.result) {
      setSaveMsg({ tone: "warn", title: "Değişiklik yok", text: `${r.result.slot} zaten cihazdaki ayarla aynı; yazılmadı.` });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setSaveMsg({ tone: f.kind, title: /yazılmadı/.test(f.text) ? "Kaydedilmedi" : f.title, text: f.text });
    }
  }

  const running = (!!state && ["connecting", "countdown", "record", "measure"].includes(state.kind)) || saving;
  const ready = state?.ready;
  const ctlOn = target.ctl === "on";

  return (
    <section className="tm-panel calib" aria-live="polite">
      <header className="calib__head">
        <div>
          <span className="tm-label">Kalibrasyon · {roleName(target.role)}{target.ctl ? ` · CTL ${ctlOn ? "açık" : "kapalı"}` : ""}</span>
          <h2>{target.patch}{ready ? <span className="calib__amp"> · {ready.amp}</span> : null}</h2>
          <p className="tm-field__hint">
            Şarkıda bu tonun geçtiği yeri GT-1'den çal; USB kaydı şarkıdaki gitarla karşılaştırılır. Cihaza bir şey yazılmaz.
          </p>
        </div>
        <div className="calib__tools">
          {!running && <Segmented name="calib-len" value={seconds} onChange={setSeconds} options={LENGTHS} />}
          {saving ? <span className="job__now"><Led state="busy" /><span>Kaydediliyor…</span></span>
            : running
              ? <Button onClick={() => cli.cancel()}>Durdur</Button>
              : <Button variant="primary" onClick={start}>{state ? "Tekrar çal" : "Başla"}</Button>}
          {!running && round > 0 && <Button onClick={() => setConfirm(true)}>Slota kaydet…</Button>}
          {!running && <Button variant="ghost" onClick={onClose}>Kapat</Button>}
        </div>
      </header>

      {ready && ready.segments.length > 0 && (
        <div className="calib__where">
          <span className="tm-field__hint">
            Çalınacak yer: {ready.segments.slice(0, 4).map(([a, b]) => `${mmss(a)}–${mmss(b)}`).join(", ")}
          </span>
          <Timeline duration={ready.duration} segments={ready.segments} alt={ctlOn} />
        </div>
      )}

      {!state && (
        <ol className="calib__steps">
          <li>Gitarını GT-1'e tak, bilgisayarda ses çalma.</li>
          <li>{target.slot ? `${target.slot} seçilir` : "Edit buffer'daki patch kullanılır"}{ctlOn ? ", geri sayımda CTL'ye bas (ikinci ton)" : ""}.</li>
          <li>Geri sayımdan sonra {seconds} saniye bu bölümü çal.</li>
        </ol>
      )}

      {state?.kind === "connecting" && <div className="job__now"><Led state="busy" /><span>{cli.pending() > 1 ? "Cihaz okuması bitince başlıyor…" : "GT-1'e bağlanıyor, patch okunuyor…"}</span></div>}

      {state?.kind === "countdown" && (
        <div className="calib__count">
          <span className="calib__count-n tm-readout">{state.n}</span>
          <span>{ctlOn ? "CTL'ye bas, hazırlan" : "Hazırlan"}</span>
        </div>
      )}

      {state?.kind === "record" && <Recording s={state} />}

      {state?.kind === "measure" && <div className="job__now"><Led state="busy" /><span>Kayıt ölçülüyor…</span></div>}

      {state?.kind === "error" && <Notice tone={state.tone} title={state.title}>{state.text}</Notice>}

      {saveMsg && <Notice tone={saveMsg.tone} title={saveMsg.title}>{saveMsg.text}</Notice>}

      {state?.kind === "done" && <CalReport r={state.result} round={round} history={history.current} />}

      <Dialog open={confirm} title={`${slotLabel(saveSlot)} üzerine kaydedilsin mi?`} confirmLabel="Kaydet"
        onCancel={() => setConfirm(false)} onConfirm={save}>
        <div className="calib__save">
          <p>
            Cihazdaki güncel ayar (<strong>{target.patch}</strong>, cihazdan çevirdiğin knob'larla) yazılır.
            Mevcut içerik önce yedeklenir, yazdıktan sonra geri okunup doğrulanır.
          </p>
          {!target.slot && (
            <div className="calib__save-slot">
              <span className="tm-label">Hedef slot</span>
              <SlotPicker value={saveSlot} onChange={setSaveSlot} />
            </div>
          )}
          {target.ctl && <p>İki tonlu patch: kaydetmeden önce CTL'yi kapalı konuma getir.</p>}
        </div>
      </Dialog>
    </section>
  );
}

function Recording({ s }: { s: Extract<State, { kind: "record" }> }) {
  const left = Math.max(0, s.seconds - (Date.now() - s.start) / 1000);
  const pct = (db: number) => Math.max(0, Math.min(100, ((db + 60) / 60) * 100));
  const hot = s.db > -3;
  const quiet = s.db < -50;
  return (
    <div className="calib__rec">
      <div className="calib__rec-head">
        <span className="calib__rec-label"><Led state="err" /> Kayıt · çal</span>
        <span className="tm-readout">{mmss(left)}</span>
      </div>
      <div className="calib-meter" role="meter" aria-label="Giriş seviyesi (dBFS)" aria-valuemin={-60} aria-valuemax={0} aria-valuenow={Math.round(s.db)}>
        <div className={`calib-meter__fill${hot ? " is-hot" : ""}`} style={{ width: `${pct(s.db)}%` }} />
        <div className="calib-meter__peak" style={{ left: `${pct(s.peak)}%` }} />
      </div>
      <div className="tuner-meter__scale tm-readout calib-meter__scale"><span>−60</span><span>{s.db.toFixed(0)} dBFS</span><span>0</span></div>
      {hot && <p className="calib__warn">Sinyal tavana yakın: clip olabilir.</p>}
      {quiet && <p className="calib__warn">Sinyal yok gibi: gitar takılı mı?</p>}
    </div>
  );
}

function CalReport({ r, round, history }: { r: CalResult; round: number; history: number[] }) {
  const c = r.compare;
  const prev = history.length > 1 ? history[history.length - 2] : null;
  const [ds, dp] = r.fx.delay_ms;
  const [rs, rp] = r.fx.reverb;
  return (
    <div className="calib__report">
      <div className="calib__score">
        <div>
          <span className="tm-label">Spektral mesafe</span>
          <div className="calib__dist tm-readout">{c.spectral_distance_db.toFixed(1)} dB</div>
          <span className="tm-field__hint">
            {prev === null ? "Küçük olan daha yakın. Ayar yapıp tekrar çal, burada izle."
              : c.spectral_distance_db < prev ? `Önceki turdan ${(prev - c.spectral_distance_db).toFixed(1)} dB daha yakın.`
                : `Önceki tur ${prev.toFixed(1)} dB'ydi.`}
          </span>
        </div>
        <span className="tm-field__hint">Tur {round} · {r.played_seconds.toFixed(0)} sn çalım · seviye {r.level_db.toFixed(0)} dBFS</span>
      </div>

      {r.warnings.map((w) => <Notice key={w} tone="warn" title="Dikkat">{w}</Notice>)}

      <table className="calib-table">
        <thead>
          <tr><th scope="col">Eksen</th><th scope="col">Şarkı</th><th scope="col">Senin çalımın</th><th scope="col">Fark</th><th scope="col" /></tr>
        </thead>
        <tbody>
          {AXES.map(({ key, label, hint }) => {
            const ok = c.close.includes(key);
            const [a, b] = r.values[key];
            return (
              <tr key={key}>
                <th scope="row"><span>{label}</span><span className="tm-field__hint">{hint}</span></th>
                <td className="tm-readout">{fmt(key, a)}</td>
                <td className="tm-readout">{fmt(key, b)}</td>
                <td className={`tm-readout calib-table__diff${ok ? "" : " is-off"}`}>{signed(key, c.diff[key])}</td>
                <td><span className={`calib-tag${ok ? " is-ok" : " is-off"}`}>{ok ? "yakın" : "farklı"}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="calib__hints">
        <span className="tm-label">Ne yapmalı</span>
        {c.hints.length === 0
          ? <p>Tüm eksenler yakın. Kulağına da uyuyorsa bu ton tamam.</p>
          : <ul>{c.hints.map((h) => <li key={h.axis}>{h.text.replace(/^patch şarkıya göre /, "Patch şarkıya göre ")}</li>)}</ul>}
        <p className="tm-field__hint">
          Delay: şarkı {ds ? `${Math.round(ds)} ms` : "yok"}, patch {dp ? `${Math.round(dp)} ms` : "yok"} · Reverb: şarkı {rs}, patch {rp}.
          {" "}Şimdilik sadece ölçüm: knob'ları cihazdan çevirip "Tekrar çal" de (patch yeniden seçilmez, ayarın
          korunur). Otomatik düzeltme sonraki adımda; beğendiğin ayarı cihazda WRITE ile kaydet.
        </p>
      </div>
      <p className="calib__file tm-field__hint">Kayıt: <span className="tm-readout">{r.wav}</span></p>
    </div>
  );
}
