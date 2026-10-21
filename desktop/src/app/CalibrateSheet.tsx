import * as React from "react";
import * as cli from "../cli";
import {
  AxisCompare, BandDiff, Button, Dialog, Icon, LevelMeter, Notice, Segmented, Sheet, SlotPicker, SongMap, Sparkline,
  mmss, roleName, signed, slotLabel, toast, type AxisRow,
} from "../ds";
import { friendly, typing } from "./state";

// Play-to-calibrate (`tonematch calibrate --json`, docs/07 item 0). The CLI selects the patch, counts down,
// records the GT-1's USB output and compares it with the song's guitar; we draw its @@CALIB stream and result.
// Stage mode: the player holds a guitar and looks from a distance, so numbers are big and Space starts a take.
// Measuring writes nothing; "Slota kaydet" saves the edit buffer (knobs turned on the unit) with `gt1 save`:
// backup, write, read back + verify, refused when the unit has another patch selected (--expect-name).

export type CalTarget = {
  source: string; role: string; slot: string | null; ctl: "off" | "on" | undefined; patch: string; amp: string; title: string;
  /** where the tone plays, known from the run result before the CLI reports it */
  segments: number[][]; duration: number;
};

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
    diff: Record<Axis, number>; spectral_distance_db: number; close: Axis[]; third_oct_diff?: Record<string, number>;
    hints: { axis: Axis; value: number; knob: string; direction: "up" | "down"; text: string }[];
  };
  played_seconds: number; level_db: number; warnings: string[]; wav: string;
};

type Ready = Extract<CalEvent, { phase: "ready" }>;
type SaveResult = { slot: string; name: string; saved: boolean; changed: { label: string; from: string; to: string }[]; backup: string | null };
type State =
  | { kind: "intro"; ready?: Ready }
  | { kind: "connecting"; ready?: Ready }
  | { kind: "countdown"; ready?: Ready; n: number }
  | { kind: "record"; ready?: Ready; seconds: number; start: number; db: number; peak: number }
  | { kind: "measure"; ready?: Ready }
  | { kind: "done"; ready?: Ready; result: CalResult }
  | { kind: "error"; ready?: Ready; title: string; text: string; tone: "warn" | "danger" };

const AXES: { key: Axis; label: string; hint: string }[] = [
  { key: "drive", label: "Drive", hint: "Distorsiyon miktarı" },
  { key: "mid_scoop_db", label: "Orta", hint: "400–1200 Hz · eksi = oyuk" },
  { key: "presence_db", label: "Presence", hint: "2–4.5 kHz ısırık" },
  { key: "body_db", label: "Gövde", hint: "200–450 Hz alt-orta" },
  { key: "fizz_db", label: "Fizz", hint: "5–8 kHz üst tiz" },
  { key: "low_depth_db", label: "Alt uç", hint: "60–110 Hz · stemde bas sızabilir" },
];
const BASS_BLEED = ["63Hz", "80Hz", "100Hz", "125Hz"];
const LENGTHS = [{ value: "15", label: "15 sn" }, { value: "20", label: "20 sn" }, { value: "30", label: "30 sn" }];

type Props = { target: CalTarget | null; fallbackSlot: number; onClose: () => void; onSaved: () => void };

export function CalibrateSheet({ target, fallbackSlot, onClose, onSaved }: Props) {
  const [seconds, setSeconds] = React.useState("20");
  const [saveSlot, setSaveSlot] = React.useState(() => (target?.slot ? Number(target.slot.slice(1)) : fallbackSlot));
  const [confirm, setConfirm] = React.useState<null | "save" | "close">(null);
  const [saving, setSaving] = React.useState(false);
  const [state, setState] = React.useState<State>({ kind: "intro" });
  const [round, setRound] = React.useState(0);
  const history = React.useRef<number[]>([]);
  const [, tick] = React.useReducer((x: number) => x + 1, 0);
  const runningRef = React.useRef(false);

  React.useEffect(() => () => { if (runningRef.current) cli.cancel(); }, []);
  React.useEffect(() => {
    if (state.kind !== "record") return;
    const t = setInterval(tick, 200);
    return () => clearInterval(t);
  }, [state.kind]);

  const running = ["connecting", "countdown", "record", "measure"].includes(state.kind) || saving;

  // Space = start / play again, from across the room
  React.useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || typing(e) || confirm) return;
      if ((e.target as HTMLElement)?.tagName === "BUTTON") return; // let a focused button handle its own Space
      e.preventDefault();
      if (!running) start();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!target) return null;
  const ctlOn = target.ctl === "on";

  async function start() {
    if (!target) return;
    let ready: Ready | undefined = state.ready;
    setState({ kind: "connecting", ready });
    runningRef.current = true;
    const args = ["calibrate", target.source, "--role", target.role, "--seconds", seconds, "--json",
      // CTL is off after selecting a patch: give the player time to step on it for the second tone
      "--countdown", ctlOn ? "5" : "3"];
    // select the slot on the first round only: later rounds keep the knobs the player turned on the unit
    if (target.slot && round === 0) args.push("--slot", target.slot);
    const r = await cli.run<CalResult>(args, (l) => {
      if (!l.text.startsWith("@@CALIB ")) return;
      const ev = JSON.parse(l.text.slice(8)) as CalEvent;
      if (ev.kind === "level") {
        setState((s) => (s.kind === "record" ? { ...s, db: ev.db, peak: Math.max(s.peak, ev.db) } : s));
      } else if (ev.phase === "ready") {
        ready = ev;
        setState((s) => ({ ...s, ready: ev }));
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
      setState({ kind: "error", ready, tone: "warn", title: "Kayıt durduruldu", text: "Cihaza hiçbir şey yazılmadı." });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setState({ kind: "error", ready, tone: f.kind, title: f.title, text: f.text });
    }
  }

  async function save() {
    setConfirm(null); setSaving(true);
    const r = await cli.run<SaveResult>(["gt1", "save", slotLabel(saveSlot), "--expect-name", target!.patch, "--yes", "--json"]);
    setSaving(false);
    if (r.result?.saved) {
      const ch = r.result.changed.map((c) => `${c.label} ${c.from} → ${c.to}`).join(", ");
      toast({ tone: "ok", title: `${r.result.slot} kaydedildi ve doğrulandı`, text: `${ch || "Ayarlar yazıldı."} Önceki hali yedeklendi.` });
      onSaved();
    } else if (r.result) {
      toast({ tone: "info", title: "Değişiklik yok", text: `${r.result.slot} zaten cihazdaki ayarla aynı; yazılmadı.` });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      toast({ tone: f.kind === "warn" ? "warn" : "danger", title: f.title, text: f.text });
    }
  }

  const ready = state.ready;
  const where = ready ?? target;
  const close = () => (round > 0 && !saving ? setConfirm("close") : onClose());

  return (
    <Sheet open title={<>Çalarak karşılaştır · {roleName(target.role)}</>}
      sub={<>{target.patch} · {ready?.amp ?? target.amp}{target.ctl ? ` · CTL ${ctlOn ? "açık" : "kapalı"}` : ""} · {target.title}</>}
      onClose={close} locked={running}
      actions={<>
        {!running && round > 0 && <Button icon="device" onClick={() => setConfirm("save")}>Slota kaydet…</Button>}
        {running && !saving && <Button variant="danger" icon="stop" onClick={() => cli.cancel()}>Durdur</Button>}
      </>}>
      <div className="cal">
        <div className="cal__stage" aria-live="polite">
          {state.kind === "intro" && (
            <div className="cal__intro">
              <ol className="cal__steps">
                <li><span className="cal__n">1</span><span>Gitarını GT-1'e tak. Bilgisayarda başka ses çalmasın.</span></li>
                <li><span className="cal__n">2</span><span>{target.slot ? `${target.slot} cihazda seçilecek` : "Cihazdaki güncel patch kullanılacak"}{ctlOn ? ". Geri sayımda CTL'ye bas (ikinci ton)" : ""}.</span></li>
                <li><span className="cal__n">3</span><span>Geri sayımdan sonra sağdaki bölümü {seconds} saniye çal.</span></li>
              </ol>
              <div className="cal__go">
                <Segmented name="cal-len" label="Kayıt uzunluğu" value={seconds} onChange={setSeconds} options={LENGTHS} />
                <Button variant="primary" size="lg" icon="record" kbd="Space" onClick={start}>Kaydı başlat</Button>
              </div>
              <p className="t-small cal__note">Sadece ölçülür; cihazda hiçbir şey değişmez. İstersen sonra knob'ları cihazdan çevirip tekrar çalarsın.</p>
            </div>
          )}

          {state.kind === "connecting" && (
            <div className="cal__center"><span className="tm-spinner cal__spin" /><p className="t-title">{cli.pending() > 1 ? "Cihaz okuması bitince başlıyor…" : "GT-1'e bağlanıyor, patch okunuyor…"}</p></div>
          )}

          {state.kind === "countdown" && (
            <div className="cal__center">
              <span className="t-stage cal__count" key={state.n}>{state.n}</span>
              <p className="t-title">{ctlOn ? "CTL'ye bas, hazırlan" : "Hazırlan"}</p>
            </div>
          )}

          {state.kind === "record" && <Recording s={state} />}

          {state.kind === "measure" && (
            <div className="cal__center"><span className="tm-spinner cal__spin" /><p className="t-title">Kayıt ölçülüyor…</p></div>
          )}

          {state.kind === "error" && (
            <div className="cal__center cal__center--top">
              <Notice tone={state.tone} title={state.title}>{state.text}</Notice>
              <Button variant="primary" size="lg" icon="record" kbd="Space" onClick={start}>Tekrar dene</Button>
            </div>
          )}

          {state.kind === "done" && <Report r={state.result} round={round} history={history.current} onAgain={start} />}
        </div>

        <aside className="cal__side">
          <section>
            <h3 className="t-heading">Nereden çalacaksın</h3>
            {where.segments.length > 0 ? (
              <>
                <ul className="cal__where">
                  {where.segments.slice(0, 5).map(([a, b]) => <li key={a} className="t-readout">{mmss(a)} – {mmss(b)}</li>)}
                </ul>
                <SongMap duration={where.duration} lanes={[{ label: roleName(target.role), segments: where.segments, tone: ctlOn ? "you" : "song" }]} />
              </>
            ) : <p className="t-small cal__muted">Şarkıda bu tonun geçtiği yer bulunamadı.</p>}
          </section>
          {history.current.length > 0 && (
            <section>
              <h3 className="t-heading">Turlar</h3>
              {history.current.length > 1 && <Sparkline values={history.current} width={240} height={44} label={`Tur tur spektral mesafe: ${history.current.map((v) => v.toFixed(1)).join(", ")} dB`} />}
              <ol className="cal__rounds">
                {history.current.map((v, i) => <li key={i}><span>Tur {i + 1}</span><span className="t-readout">{v.toFixed(1)} dB</span></li>)}
              </ol>
            </section>
          )}
          <section className="cal__tip t-small">
            <Icon name="info" />
            <span>Mesafe küçüldükçe tonun şarkıya yaklaşıyor. Beğendiğin ayarı <strong>Slota kaydet</strong> ile yaz (önce yedeklenir).</span>
          </section>
        </aside>
      </div>

      <Dialog open={confirm === "save"} title={`${slotLabel(saveSlot)} üzerine kaydedilsin mi?`} confirmLabel="Kaydet"
        onCancel={() => setConfirm(null)} onConfirm={save}>
        <p>Cihazdaki güncel ayar (<strong>{target.patch}</strong>, cihazdan çevirdiğin knob'larla) yazılır. Mevcut içerik önce yedeklenir, yazdıktan sonra geri okunup doğrulanır.</p>
        {!target.slot && (
          <div className="cal__saveslot"><span className="t-label">Hedef slot</span><SlotPicker value={saveSlot} onChange={setSaveSlot} /></div>
        )}
        {target.ctl && <p>İki tonlu patch: kaydetmeden önce CTL'yi kapalı konuma getir.</p>}
      </Dialog>
      <Dialog open={confirm === "close"} title="Kaydetmeden kapatılsın mı?" confirmLabel="Kapat" cancelLabel="Geri dön"
        onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); onClose(); }}>
        <p>Cihazda knob çevirdiysen o ayar sadece edit buffer'da durur; patch değiştirince kaybolur.</p>
      </Dialog>
    </Sheet>
  );
}

function Recording({ s }: { s: Extract<State, { kind: "record" }> }) {
  const left = Math.max(0, s.seconds - (Date.now() - s.start) / 1000);
  const hot = s.db > -3;
  const quiet = s.db < -50;
  return (
    <div className="cal__rec">
      <div className="cal__rec-head">
        <span className="cal__rec-label"><span className="tm-led tm-led--rec" /> Kayıt</span>
        <span className="t-stage cal__left">{mmss(left)}</span>
      </div>
      <LevelMeter db={s.db} peak={s.peak} size="lg" />
      <p className="t-heading cal__rec-msg" role="status">
        {hot ? "Sinyal tavana yakın: clip olabilir, patch seviyesini düşür." : quiet ? "Sinyal yok gibi: gitar takılı mı, volume açık mı?" : "Çal. Seviye iyi."}
      </p>
    </div>
  );
}

function Report({ r, round, history, onAgain }: { r: CalResult; round: number; history: number[]; onAgain: () => void }) {
  const c = r.compare;
  const prev = history.length > 1 ? history[history.length - 2] : null;
  const better = prev !== null && c.spectral_distance_db < prev;
  const [ds, dp] = r.fx.delay_ms;
  const [rs, rp] = r.fx.reverb;
  const rows: AxisRow[] = AXES.map(({ key, label, hint }) => ({
    key, label, hint, song: r.values[key][0], you: r.values[key][1], close: c.close.includes(key), unit: key === "drive" ? "ratio" : "db",
  }));
  return (
    <div className="cal__report">
      <div className="cal__score">
        <div>
          <span className="t-label cal__muted">Spektral mesafe · tur {round}</span>
          <div className="cal__dist"><span className="t-stage">{c.spectral_distance_db.toFixed(1)}</span><span className="t-title">dB</span></div>
          <p className={better ? "cal__delta is-better" : "cal__delta"}>
            {prev === null ? "Küçük olan daha yakın. Knob'ları cihazdan çevir, tekrar çal."
              : better ? `Önceki turdan ${(prev - c.spectral_distance_db).toFixed(1)} dB daha yakın.`
                : `Önceki tur ${prev.toFixed(1)} dB'ydi: bu ayar uzaklaştırdı.`}
          </p>
        </div>
        <div className="cal__score-actions">
          <Button variant="primary" size="lg" icon="record" kbd="Space" onClick={onAgain}>Tekrar çal</Button>
          <span className="t-small cal__muted">{r.played_seconds.toFixed(0)} sn çalım · seviye {r.level_db.toFixed(0)} dBFS</span>
        </div>
      </div>

      {r.warnings.map((w) => <Notice key={w} tone="warn" title="Dikkat">{w}</Notice>)}

      <section className="cal__block">
        <h3 className="t-heading">Ne yapmalı</h3>
        {c.hints.length === 0 ? <p className="t-body">Tüm eksenler yakın. Kulağına da uyuyorsa bu ton tamam.</p> : (
          <ul className="moves">
            {c.hints.map((h) => (
              <li key={h.axis} className="move">
                <span className={`move__arrow is-${h.direction}`}><Icon name={h.direction === "up" ? "chevron-up" : "chevron-down"} /></span>
                <span className="move__knob t-param">{h.knob}</span>
                <span className="move__text">{h.text.replace(/^patch şarkıya göre /, "Patch şarkıya göre ").replace(/ → .*$/, "")}</span>
                <span className="move__val t-readout">{AXES.find((a) => a.key === h.axis)?.key === "drive" ? signed(h.value, 2) : `${signed(h.value, 1)} dB`}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="cal__block">
        <h3 className="t-heading">Eksen eksen</h3>
        <AxisCompare rows={rows} />
      </section>

      {c.third_oct_diff && Object.keys(c.third_oct_diff).length > 0 && (
        <section className="cal__block">
          <h3 className="t-heading">Frekans frekans</h3>
          <p className="t-small cal__muted">
            Senin çalımın eksi şarkı, 1/3 oktav. Mavi: sende daha güçlü; krem: şarkıda daha güçlü. Taralı bantlar (63–125 Hz)
            stemdeki bas sızıntısı yüzünden mesafeye katılmaz.
          </p>
          <BandDiff bands={c.third_oct_diff} ignored={BASS_BLEED} />
        </section>
      )}

      <p className="t-small cal__muted">
        Delay: şarkı {ds ? `${Math.round(ds)} ms` : "yok"}, patch {dp ? `${Math.round(dp)} ms` : "yok"} · Reverb: şarkı {rs}, patch {rp}.
        Kayıt: <span className="t-console">{r.wav}</span>
      </p>
    </div>
  );
}
