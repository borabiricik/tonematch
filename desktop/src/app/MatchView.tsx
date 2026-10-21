import * as React from "react";
import * as cli from "../cli";
import {
  Button, Card, Dialog, Field, Icon, IconButton, Kbd, Led, Notice, Pipeline, Segmented, Select, SlotPicker, TextInput,
  ago, cx, dative, mmss, slotLabel, thumbUrl, youtubeId, type RunResult, type Stage,
} from "../ds";
import { planTuning } from "../tuning";
import { Cover, RequestFacts } from "./parts";
import { ResultView } from "./ResultView";
import {
  addToLibrary, friendly, kbd, typing, useLibrary, useStored,
  type Device, type DualMode, type Engine, type LibraryEntry, type RunRequest, type Target,
} from "./state";

const TUNINGS = [
  { value: "", label: "E standart · EADGBE" },
  { value: "DADGBE", label: "Drop D · DADGBE" },
  { value: "D#G#C#F#A#D#", label: "Eb standart · D#G#C#F#A#D#", group: "Pitch shifter ile" },
  { value: "DGCFAD", label: "D standart · DGCFAD", group: "Pitch shifter ile" },
  { value: "C#F#BEG#C#", label: "C# standart · C#F#BEG#C#", group: "Pitch shifter ile" },
  { value: "CGCFAD", label: "Drop C · CGCFAD", group: "Pitch shifter ile" },
  { value: "BEADF#B", label: "B standart · BEADF#B", group: "Pitch shifter ile" },
  { value: "custom", label: "Başka bir akort…", group: "Pitch shifter ile" },
];
const STAGES = ["İndir", "Ayrıştır", "Analiz", "GT-1'e yaz"];
const TARGET_HINT: Record<Target, string> = {
  slot: "Patch seçtiğin slota yazılır ve cihazda seçilir. Slottaki eski patch önce yedeklenir.",
  listen: "Patch edit buffer'a yüklenir, hiçbir slot değişmez. Beğenirsen sonra kaydedersin.",
  file: "Cihaza dokunmaz. BOSS TONE STUDIO'da açılabilen bir .tsl dosyası yazılır.",
};

type StageState = { state: Stage["state"]; start?: number; end?: number; note?: string };
type Job =
  | { kind: "idle" }
  | { kind: "running"; title: string; req: RunRequest; stages: StageState[]; now: string; started: number }
  | { kind: "done"; entry: LibraryEntry }
  | { kind: "error"; title: string; text: string; tone: "warn" | "danger" };

/** Bare words become a YouTube search, like typing in YouTube's own box. */
function sourceArg(v: string) {
  const s = v.trim();
  return !s || /^(https?:\/\/|ytsearch\d*:)/i.test(s) || /^[A-Za-z0-9_-]{11}$/.test(s) || /^([/~]|[A-Za-z]:\\)/.test(s) ? s : `ytsearch1:${s}`;
}
function describeSource(v: string): { kind: "youtube"; id: string } | { kind: "search"; q: string } | { kind: "file" } | null {
  const s = v.trim();
  if (!s) return null;
  const id = youtubeId(s);
  if (id) return { kind: "youtube", id };
  if (/^([/~]|[A-Za-z]:\\)/.test(s)) return { kind: "file" };
  if (/^https?:\/\//i.test(s)) return null;
  return { kind: "search", q: s.replace(/^ytsearch\d*:/, "") };
}

type Props = {
  active: boolean;
  slot: number;
  setSlot: (n: number) => void;
  device: Device;
  env: cli.EnvInfo | null;
  prefill: { req: RunRequest; n: number } | null;
  onRunning: (running: boolean) => void;
  openLog: () => void;
  openTuner: () => void;
  onFinished: (wroteToDevice: boolean) => void;
};

export function MatchView({ active, slot, setSlot, device, env, prefill, onRunning, openLog, openTuner, onFinished }: Props) {
  const [source, setSource] = React.useState("");
  const [target, setTarget] = useStored<Target>("target", "slot");
  const [mode, setMode] = useStored<DualMode>("dual-mode", "dual");
  const [engine, setEngine] = useStored<Engine>("engine", "algo");
  const [preset, setPreset] = React.useState("");
  const [custom, setCustom] = React.useState("");
  const [job, setJob] = React.useState<Job>({ kind: "idle" });
  const [confirm, setConfirm] = React.useState<null | "write" | "stop">(null);
  const [library] = useLibrary();
  const [, tick] = React.useReducer((x: number) => x + 1, 0);
  const sourceRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (job.kind !== "running") return;
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [job.kind]);
  React.useEffect(() => onRunning(job.kind === "running"), [job.kind]);

  // "Run again" from the library fills the form
  React.useEffect(() => {
    if (!prefill) return;
    const r = prefill.req;
    setSource(r.source.replace(/^ytsearch1:/, ""));
    setTarget(r.target); setMode(r.mode); setEngine(r.engine); setSlot(r.slot);
    const known = TUNINGS.some((t) => t.value === r.tuning);
    setPreset(known ? r.tuning : "custom"); setCustom(known ? "" : r.tuning);
    setJob({ kind: "idle" });
    requestAnimationFrame(() => sourceRef.current?.focus());
  }, [prefill?.n]);

  const tuning = preset === "custom" ? custom.replace(/\s+/g, "") : preset;
  const plan = planTuning(tuning);
  const existing = device.slots.find((s) => s.slot === slotLabel(slot));
  const described = describeSource(source);
  const canRun = !!source.trim() && !("error" in plan) && job.kind !== "running" && !(env && !env.ready);

  function submit() {
    if (!canRun) return;
    if (target === "slot") setConfirm("write");
    else start();
  }

  // ⌘↵ runs from anywhere on this view (also from inside the song field)
  React.useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); submit(); }
      else if (e.key === "/" && !typing(e) && job.kind !== "running") { e.preventDefault(); sourceRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function start() {
    const req: RunRequest = { source: sourceArg(source), target, slot, tuning, mode, engine };
    const args = ["run", req.source, "--json"];
    if (target === "file") args.push("--no-device");
    if (target === "slot") args.push("--slot", slotLabel(slot), "--yes"); // confirmed in the app; the CLI has no stdin
    if (tuning) args.push("--tuning", tuning);
    if (mode === "separate") args.push("--separate");
    if (engine === "claude") args.push("--claude");

    let state: Extract<Job, { kind: "running" }> = {
      kind: "running", title: described?.kind === "search" ? described.q : source.trim(), req, started: Date.now(),
      stages: STAGES.map(() => ({ state: "pending" as Stage["state"] })),
      now: cli.isBusy() ? "Cihaz okuması bitince başlıyor…" : "Başlıyor…",
    };
    setJob(state);
    const r = await cli.run<RunResult>(args, (l) => {
      const text = l.text.trim();
      const m = /^(\d)\/4\s+(.*)$/.exec(text);
      const s = state.stages.map((x) => ({ ...x }));
      if (m) {
        const i = Number(m[1]) - 1;
        s.forEach((x, j) => { if (j < i && x.state !== "done") { x.state = "done"; x.end = Date.now(); x.start ??= x.end; } });
        s[i] = { state: "active", start: Date.now() };
        state = { ...state, stages: s, now: m[2].replace(/\s*\.\.\.$/, "…") };
      } else if (/^ {4}\S/.test(l.text) && s[0].state === "active") {
        s[0].note = "indirildi";
        state = { ...state, stages: s, title: text.replace(/^\s*-\s*/, "") };
      } else if (text && !/^[┌└│├╭╰┏┗┃]/.test(text) && !text.startsWith(".tsl")) {
        state = { ...state, now: text };
      } else return;
      setJob(state);
    });
    if (r.result) {
      const entry: LibraryEntry = { id: `${Date.now()}`, when: Date.now(), request: req, result: r.result };
      addToLibrary(entry);
      setJob({ kind: "done", entry });
      onFinished(target !== "file");
    } else if (r.cancelled) {
      setJob({ kind: "error", tone: "warn", title: "Durduruldu", text: "İşlem yarıda kesildi. Cihaza yazma aşamasındaysa slotu Cihaz sayfasından kontrol et." });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setJob({ kind: "error", tone: f.kind, title: f.title, text: f.text });
    }
  }

  if (job.kind === "done") {
    return (
      <ResultView entry={job.entry} slot={slot} onSaved={() => onFinished(true)}
        actions={<>
          <Button icon="refresh" onClick={() => { setJob({ kind: "idle" }); requestAnimationFrame(() => sourceRef.current?.focus()); }}>Ayarları değiştir</Button>
          <Button variant="primary" icon="plus" onClick={() => { setSource(""); setJob({ kind: "idle" }); requestAnimationFrame(() => sourceRef.current?.focus()); }}>Yeni ton</Button>
        </>} />
    );
  }

  if (job.kind === "running") {
    const yt = youtubeId(job.req.source);
    return (
      <section className="page run" aria-live="polite">
        <header className="song-head">
          <Cover id={yt} title={job.title} />
          <div className="song-head__text">
            <span className="song-head__eyebrow t-small"><Led state="busy" /> Ton çıkarılıyor · {mmss((Date.now() - job.started) / 1000)}</span>
            <h1 className="t-display song-head__title">{job.title}</h1>
            <RequestFacts req={job.req} />
          </div>
        </header>
        <Card className="run__card">
          <Pipeline stages={job.stages.map((s, i) => ({ name: STAGES[i], state: s.state, note: s.note,
            time: s.start ? mmss(((s.end ?? Date.now()) - s.start) / 1000) : undefined }))} />
          <div className="run__now">
            <span className="tm-spinner" aria-hidden="true" />
            <span className="t-console run__line">{job.now}</span>
          </div>
        </Card>
        <div className="run__foot">
          <p className="t-small">İş arka planda sürer, bu sırada diğer sayfalara geçebilirsin. Gitar ayrıştırma ilk seferde birkaç dakika sürebilir.</p>
          <div className="run__actions">
            <Button variant="ghost" icon="terminal" onClick={openLog}>Çıktıyı göster</Button>
            <Button variant="danger" icon="stop" onClick={() => setConfirm("stop")}>Durdur</Button>
          </div>
        </div>
        <aside className="wait-card">
          <span className="wait-card__icon"><Icon name="tuner" /></span>
          <div>
            <h2 className="t-heading">Bu arada gitarını akort et</h2>
            <p className="t-small">
              {(() => { const p = planTuning(job.req.tuning); return "error" in p ? "Gitarın standart akortta kalsın."
                : <>Gitarın <strong>{p.play}</strong> kalsın{p.semitones ? <>; şarkının {job.req.tuning} akordunu patch'teki pitch shifter yapar</> : null}.</>; })()}
            </p>
          </div>
          <Button icon="tuner" onClick={openTuner}>Tuner'ı aç</Button>
        </aside>
        <Dialog open={confirm === "stop"} title="İşlem durdurulsun mu?" confirmLabel="Durdur" tone="danger"
          onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); cli.cancel(); }}>
          <p>Cihaza yazma sırasındaysa slot yarım kalabilir; yedek <strong>backups</strong> klasöründe durur.</p>
        </Dialog>
      </section>
    );
  }

  const runLabel = target === "slot" ? `Tonu çıkar ve ${slotLabel(slot)}${dative(slot)} yaz` : target === "listen" ? "Tonu çıkar ve dinle" : "Tonu çıkar";
  const recent = library.slice(0, 4);

  return (
    <section className="page match">
      <header className="match__hero">
        <h1 className="t-display">Hangi şarkının tonu?</h1>
        <p className="t-lead match__lead">
          Kayıttaki gitarı diğer enstrümanlardan ayırırım. Ritim, solo ve temiz tonları ayrı ayrı ölçer, her biri için
          en yakın GT-1 amfisini, knob ayarlarını ve efektleri seçerim.
        </p>
      </header>

      {env && !env.ready && (
        <Notice tone="danger" title="Python motoru bulunamadı">
          ToneMatch'in motoru uv ile kurulur: <span className="t-console">uv sync</span> (docs/09-setup.md).
        </Notice>
      )}
      {job.kind === "error" && (
        <Notice tone={job.tone} title={job.title} action={<Button size="sm" variant="ghost" icon="terminal" onClick={openLog}>Çıktı</Button>}>{job.text}</Notice>
      )}

      <form className="match__form" noValidate onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <div className="match__source">
          <label htmlFor="source" className="sr-only">Şarkı</label>
          <TextInput id="source" ref={sourceRef} size="lg" icon="search" value={source} onChange={(e) => setSource(e.target.value)}
            placeholder="YouTube linki ya da sanatçı ve şarkı adı" autoFocus
            end={source
              ? <IconButton icon="x" label="Temizle" size="sm" onClick={() => { setSource(""); sourceRef.current?.focus(); }} />
              : <Kbd>/</Kbd>} />
          <SourcePreview d={described} />
        </div>

        <Card className="rack">
          <div className="rack__row">
            <Segmented<Target> name="target" label="Nereye" value={target} onChange={setTarget} hint={TARGET_HINT[target]}
              options={[{ value: "slot", label: "Slota yaz", icon: "device" }, { value: "listen", label: "Sadece dinle", icon: "ear" }, { value: "file", label: "Dosyaya", icon: "file" }]} />
            <Field label="Hedef slot" htmlFor="slot" className={cx(target !== "slot" && "is-muted")}
              hint={target !== "slot" ? "Bu seçenekte slot kullanılmaz."
                : existing ? <>Şu an: <strong>{existing.name.trim() || "boş"}</strong> · {existing.amp}</>
                  : device.refreshing ? "Cihazdaki patch'ler okunuyor…" : "Slottaki patch önce yedeklenir."}>
              <div className="rack__slot">
                <SlotPicker id="slot" value={slot} onChange={setSlot} />
                {mode === "separate" && target === "slot" && <span className="t-small rack__note">Birden çok ton varsa sonraki slotlar da kullanılır.</span>}
              </div>
            </Field>
          </div>
          <div className="rack__row">
            <Field label="Şarkının akordu" htmlFor="tuning"
              error={"error" in plan ? plan.error : undefined}
              hint={"error" in plan ? undefined : (
                <span className="tuning-preview">
                  Gitarın <strong>{plan.play}</strong> kalsın · {plan.semitones
                    ? <>FX1'e pitch shifter <strong className="tuning-preview__shift">{plan.semitones > 0 ? "+" : "−"}{Math.abs(plan.semitones)}</strong> yarım ses</>
                    : "pitch shifter yok"}
                </span>)}>
              <Select id="tuning" value={preset} onChange={setPreset} options={TUNINGS} />
              {preset === "custom" && (
                <TextInput value={custom} onChange={(e) => setCustom(e.target.value)} invalid={"error" in plan}
                  placeholder="Kalın telden inceye, ör. C#G#C#F#A#D#" aria-label="Akort, kalın telden inceye" autoFocus />
              )}
            </Field>
            <Segmented<Engine> name="engine" label="Analiz" value={engine} onChange={setEngine}
              hint={engine === "claude"
                ? "Algoritmanın önerisini Claude, kayıtta kullanılan ekipman bilgisiyle gözden geçirir. Yaklaşık 30 sn ekler."
                : "Tamamen ölçümden hesaplanır. Hiçbir dış servis çağrılmaz."}
              options={[{ value: "algo", label: "Algoritma" }, { value: "claude", label: "Claude ile", icon: "sparkle" }]} />
          </div>
          <div className="rack__row rack__row--last">
            <Segmented<DualMode> name="mode" label="İki tonlu şarkılar" value={mode} onChange={setMode}
              hint={mode === "dual" ? "Ritim ve temiz ton aynı patch'te; CTL'ye basınca geçersin." : "Her ton kendi slotuna yazılır."}
              options={[{ value: "dual", label: "Tek patch, CTL ile", icon: "footswitch" }, { value: "separate", label: "Her ton ayrı slot" }]} />
            <div className="rack__cta">
              <Button variant="primary" size="lg" type="submit" disabled={!canRun} kbd={kbd("↵")} block>{runLabel}</Button>
              {!source.trim() && <span className="t-small rack__why">Başlamak için bir şarkı yaz.</span>}
            </div>
          </div>
        </Card>
      </form>

      {recent.length > 0 && (
        <section className="recent" aria-labelledby="recent-h">
          <h2 id="recent-h" className="t-heading">Son tonlar</h2>
          <div className="recent__grid">
            {recent.map((e) => (
              <button key={e.id} type="button" className="recent__item" onClick={() => {
                setSource(e.request.source.replace(/^ytsearch1:/, ""));
                requestAnimationFrame(() => sourceRef.current?.focus());
              }} title="Şarkıyı forma al">
                <Cover id={youtubeId(e.result.track_id) ?? null} title={e.result.title} size="sm" />
                <span className="recent__text">
                  <span className="recent__title">{e.result.title}</span>
                  <span className="t-small recent__meta">
                    {e.result.patches.map((p) => p.slot ?? "dosya").join(", ")} · {ago(e.when)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <Dialog open={confirm === "write"} title={`${slotLabel(slot)} üzerine yazılsın mı?`} confirmLabel={`${slotLabel(slot)}${dative(slot)} yaz`}
        onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); start(); }}>
        <p>
          {existing ? <>Şu an <strong>{existing.name.trim() || "boş bir patch"}</strong> ({existing.amp}) var. </> : null}
          Mevcut patch önce <strong>backups</strong> klasörüne yedeklenir, yazdıktan sonra geri okunup doğrulanır.
        </p>
        {mode === "separate" && <p>Şarkıda birden fazla ton varsa sonraki slotlar da kullanılır.</p>}
      </Dialog>
    </section>
  );
}

function SourcePreview({ d }: { d: ReturnType<typeof describeSource> }) {
  if (!d) return <p className="source-preview t-small">Örnek: <span className="t-console">https://youtu.be/…</span> ya da <span className="t-console">arctic monkeys do i wanna know</span></p>;
  if (d.kind === "youtube") return (
    <p className="source-preview t-small">
      <img src={thumbUrl(d.id)} alt="" className="source-preview__thumb" onError={(e) => { e.currentTarget.style.display = "none"; }} />
      YouTube videosu · <span className="t-console">{d.id}</span>
    </p>
  );
  if (d.kind === "file") return <p className="source-preview t-small">Bilgisayardaki ses dosyası</p>;
  return <p className="source-preview t-small">YouTube'da aranacak ve ilk sonuç kullanılacak: <strong>{d.q}</strong></p>;
}
