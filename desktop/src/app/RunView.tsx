import * as React from "react";
import * as cli from "../cli";
import {
  Button, Dialog, Field, Led, Notice, PatchCard, Segmented, Select, Steps, TextInput,
  mmss, slotLabel, type RunResult, type Step,
} from "../ds";
import { planTuning } from "../tuning";
import type { Device } from "./App";
import { friendly, load, save, useStored, type Recent } from "./store";

type Target = "slot" | "listen" | "file";
type Mode = "dual" | "separate";
type Engine = "algo" | "claude";

const TUNINGS = [
  { value: "", label: "E standart · EADGBE" },
  { value: "DADGBE", label: "Drop D · DADGBE" },
  { value: "D#G#C#F#A#D#", label: "Eb standart · D#G#C#F#A#D#" },
  { value: "DGCFAD", label: "D standart · DGCFAD" },
  { value: "C#F#BEG#C#", label: "C# standart · C#F#BEG#C#" },
  { value: "CGCFAD", label: "Drop C · CGCFAD" },
  { value: "BEADF#B", label: "B standart · BEADF#B" },
  { value: "custom", label: "Başka bir akort…" },
];
const STEP_NAMES = ["İndir", "Ayrıştır", "Analiz", "GT-1"];
const TARGET_HINT: Record<Target, string> = {
  slot: "Patch cihaza kaydedilir ve seçilir.",
  listen: "Edit buffer'a yüklenir, hiçbir slot değişmez.",
  file: "Cihaza dokunmaz; .tsl dosyası BTS ile açılabilir.",
};

type Job =
  | { kind: "idle" }
  | { kind: "running"; title: string; sub: string; steps: { state: Step["state"]; start?: number; end?: number; note?: string }[]; now: string }
  | { kind: "done"; result: RunResult; target: Target }
  | { kind: "error"; title: string; text: string; tone: "warn" | "danger" };

/** Turkish dative after a slot read aloud: U94'e, U96'ya, U20'ye. */
function dative(n: number) {
  const tens = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"];
  const ones = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"];
  const word = n % 10 ? ones[n % 10] : tens[Math.floor(n / 10)];
  const vowels = "aeıioöuü";
  const last = [...word].reverse().find((c) => vowels.includes(c)) ?? "e";
  return `'${vowels.includes(word.at(-1)!) ? "y" : ""}${"aıou".includes(last) ? "a" : "e"}`;
}

/** Bare words become a YouTube search, like typing in YouTube's own box. */
function sourceArg(v: string) {
  const s = v.trim();
  return !s || /^(https?:\/\/|ytsearch\d*:)/i.test(s) || /^[A-Za-z0-9_-]{11}$/.test(s) ? s : `ytsearch1:${s}`;
}

type Props = {
  slot: number;
  setSlot: (n: number) => void;
  device: Device;
  env: cli.EnvInfo | null;
  openLog: () => void;
  onFinished: (wroteToDevice: boolean) => void;
};

export function RunView({ slot, setSlot, device, env, openLog, onFinished }: Props) {
  const [source, setSource] = React.useState("");
  const [target, setTarget] = React.useState<Target>("slot");
  const [mode, setMode] = React.useState<Mode>("dual");
  const [engine, setEngine] = useStored<Engine>("engine", "algo");
  const [preset, setPreset] = React.useState("");
  const [custom, setCustom] = React.useState("");
  const [job, setJob] = React.useState<Job>({ kind: "idle" });
  const [confirm, setConfirm] = React.useState<null | "write" | "stop">(null);
  const [, tick] = React.useReducer((x: number) => x + 1, 0);
  const sourceRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (job.kind !== "running") return;
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [job.kind]);

  const tuning = preset === "custom" ? custom.replace(/\s+/g, "") : preset;
  const plan = planTuning(tuning);
  const existing = device.slots.find((s) => s.slot === slotLabel(slot));
  const slotOptions = React.useMemo(() => Array.from({ length: 99 }, (_, i) => {
    const label = slotLabel(i + 1);
    const s = device.slots.find((x) => x.slot === label);
    return { value: String(i + 1), label: s ? `${label} · ${s.name.trim() || "(boş)"}` : label };
  }), [device.slots]);
  const isSearch = !!source.trim() && sourceArg(source).startsWith("ytsearch1:") && !source.trim().startsWith("ytsearch");
  const canRun = !!source.trim() && !("error" in plan) && job.kind !== "running";

  async function start() {
    const args = ["run", sourceArg(source), "--json"];
    if (target === "file") args.push("--no-device");
    if (target === "slot") args.push("--slot", slotLabel(slot), "--yes"); // confirmed in the app; the CLI has no stdin
    if (tuning) args.push("--tuning", tuning);
    if (mode === "separate") args.push("--separate");
    if (engine === "claude") args.push("--claude");

    const steps = STEP_NAMES.map(() => ({ state: "pending" as Step["state"] } as { state: Step["state"]; start?: number; end?: number; note?: string }));
    let state = {
      kind: "running" as const, title: source.trim(), steps, now: cli.isBusy() ? "Cihaz okuması bitince başlıyor…" : "Başlıyor…",
      sub: `${target === "slot" ? `Hedef ${slotLabel(slot)}` : target === "listen" ? "Edit buffer" : "Sadece dosya"} · Akort ${tuning || "EADGBE"} · ${engine === "claude" ? "Claude modu" : "Algoritma"}`,
    };
    setJob(state);
    const r = await cli.run<RunResult>(args, (l) => {
      const text = l.text.trim();
      const m = /^(\d)\/4\s+(.*)$/.exec(text);
      const s = state.steps.map((x) => ({ ...x }));
      if (m) {
        const i = Number(m[1]) - 1;
        s.forEach((x, j) => { if (j < i && x.state !== "done") { x.state = "done"; x.end = Date.now(); x.start ??= x.end; } });
        s[i] = { state: "active", start: Date.now() };
        state = { ...state, steps: s, now: m[2].replace(/\s*\.\.\.$/, "…") };
      } else if (/^ {4}\S/.test(l.text) && s[0].state === "active") {
        s[0].note = "indirildi";
        state = { ...state, steps: s, title: text };
      } else if (l.stream === "stdout" && text && !/^[┌└│├╭╰]/.test(text)) {
        state = { ...state, now: text };
      } else return;
      setJob(state);
    });
    if (r.result) {
      setJob({ kind: "done", result: r.result, target });
      const p0 = r.result.patches[0];
      const rec: Recent = { title: r.result.title, source: sourceArg(source), slot: p0?.slot?.startsWith("U") ? p0.slot : null, name: p0?.name ?? "", when: Date.now() };
      save("recent", [rec, ...load<Recent[]>("recent", []).filter((x) => x.source !== rec.source)].slice(0, 12));
      onFinished(target !== "file");
    } else if (r.cancelled) {
      setJob({ kind: "error", tone: "warn", title: "Durduruldu", text: "İşlem yarıda kesildi. Cihaza yazma aşamasındaysa slotu Cihaz sekmesinden kontrol et." });
    } else {
      const f = friendly(r.error?.message ?? `Çıkış kodu ${r.code}.`);
      setJob({ kind: "error", tone: f.kind, title: f.title, text: f.text });
    }
  }

  const runLabel = target === "slot" ? `Tonu çıkar ve ${slotLabel(slot)}${dative(slot)} yaz` : target === "listen" ? "Tonu çıkar ve dinle" : "Tonu çıkar";

  return (
    <main className="view view-run">
      <aside className="side">
        <form noValidate onSubmit={(e) => { e.preventDefault(); if (canRun) target === "slot" ? setConfirm("write") : start(); }}>
          <div className="side__title">
            <h2>Yeni ton</h2>
            <p className="tm-field__hint">Şarkıyı analiz eder, tonunu GT-1 patch'i olarak yazar.</p>
          </div>

          <Field label="Şarkı" htmlFor="source"
            hint={isSearch ? <>YouTube'da aranacak: <strong>{source.trim()}</strong></> : "YouTube linki ya da şarkı adı"}>
            <TextInput id="source" ref={sourceRef} value={source} onChange={(e) => setSource(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=…" autoFocus />
          </Field>

          <Segmented<Target> name="target" legend="Nereye" value={target} onChange={setTarget} hint={TARGET_HINT[target]}
            options={[{ value: "slot", label: "Slota yaz" }, { value: "listen", label: "Sadece dinle" }, { value: "file", label: "Dosyaya" }]} />

          {target === "slot" && (
            <Field label="Hedef slot" htmlFor="slot"
              hint={existing
                ? <>Şu an: <strong>{existing.name.trim() || "(boş)"}</strong> · {existing.amp}. Önce yedeklenir.</>
                : device.refreshing ? "Cihazdaki patch'ler okunuyor…" : "Mevcut patch önce yedeklenir."}>
              <Select id="slot" value={String(slot)} onChange={(v) => setSlot(Number(v))} options={slotOptions} />
            </Field>
          )}

          <Field label="Şarkının akordu" htmlFor="tuning"
            hint={"error" in plan
              ? <span className="tuning-preview is-error">{plan.error}</span>
              : <span className="tuning-preview">Sen <strong>{plan.play}</strong> çal · {plan.semitones
                ? <>pitch shifter <strong className="shift">{plan.semitones > 0 ? "+" : ""}{plan.semitones}</strong> yarım ses</>
                : "pitch shifter yok"}</span>}>
            <Select id="tuning" value={preset} onChange={setPreset} options={TUNINGS} />
            {preset === "custom" && (
              <TextInput mono value={custom} onChange={(e) => setCustom(e.target.value)} invalid={"error" in plan}
                placeholder="ör. C#G#C#F#A#D#" aria-label="Akort, kalın telden inceye" autoFocus />
            )}
          </Field>

          <Segmented<Engine> name="engine" legend="Analiz" value={engine} onChange={setEngine}
            hint={engine === "claude"
              ? "Algoritmanın önerisini Claude, kayıtta kullanılan ekipman bilgisiyle gözden geçirir. Yaklaşık 30 sn ekler."
              : "Tamamen ölçümden hesaplanır, yapay zekâ kullanılmaz."}
            options={[{ value: "algo", label: "Algoritma" }, { value: "claude", label: "Claude modu" }]} />

          <Segmented<Mode> name="mode" legend="İki tonlu şarkılar" value={mode} onChange={setMode}
            options={[{ value: "dual", label: "Tek patch, CTL ile" }, { value: "separate", label: "Her ton ayrı slot" }]} />

          {job.kind === "running"
            ? <Button block onClick={() => setConfirm("stop")}>Durdur</Button>
            : <Button variant="primary" block type="submit" disabled={!canRun}>{runLabel}</Button>}
        </form>
        <div className="side__foot">
          <p>Amfin düz kalsın; ton tamamen GT-1 patch'inde. BOSS TONE STUDIO açıkken cihaza bağlanılamaz.</p>
        </div>
      </aside>

      <section className="work" aria-live="polite">
        <div className="work__inner">
          {env && !env.ready ? (
            <Notice tone="danger" title="Python motoru bulunamadı">ToneMatch'in motoru uv ile kurulur: https://docs.astral.sh/uv/ (docs/09-setup.md).</Notice>
          ) : job.kind === "idle" ? (
            <Empty onPick={(r) => { setSource(r.source); if (r.slot) setSlot(Number(r.slot.slice(1))); sourceRef.current?.focus(); }} />
          ) : job.kind === "running" ? (
            <section className="job">
              <div className="job__head">
                <span className="tm-label">Çalışıyor</span>
                <h1>{job.title}</h1>
                <div className="job__sub">{job.sub}</div>
              </div>
              <Steps steps={job.steps.map((s, i) => ({ name: STEP_NAMES[i], state: s.state, note: s.note,
                time: s.start ? mmss(((s.end ?? Date.now()) - s.start) / 1000) : undefined }))} />
              <div className="job__now"><Led state="busy" /><span>{job.now}</span></div>
            </section>
          ) : job.kind === "done" ? (
            <Result r={job.result} target={job.target} />
          ) : (
            <Notice tone={job.tone} title={job.title} action={<Button size="sm" onClick={openLog}>Çıktıyı göster</Button>}>{job.text}</Notice>
          )}
        </div>
      </section>

      <Dialog open={confirm === "write"} title={`${slotLabel(slot)} üzerine yazılsın mı?`} confirmLabel="Yaz"
        onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); start(); }}>
        {existing && <>Şu an <strong>{existing.name.trim() || "boş"}</strong> var. </>}
        {mode === "separate" && "Şarkıda birden fazla ton varsa sonraki slotlar da kullanılır. "}
        Mevcut patch önce <strong>backups</strong> klasörüne yedeklenir.
      </Dialog>
      <Dialog open={confirm === "stop"} title="İşlem durdurulsun mu?" confirmLabel="Durdur"
        onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); cli.cancel(); }}>
        Cihaza yazma sırasındaysa slot yarım kalabilir.
      </Dialog>
    </main>
  );
}

function Empty({ onPick }: { onPick: (r: Recent) => void }) {
  const recents = load<Recent[]>("recent", []);
  return (
    <section className="empty">
      <div className="empty__head">
        <span className="tm-label">GT-1 ton eşleştirici</span>
        <h1>Bir şarkı ver, gitar tonunu GT-1'ine yazayım.</h1>
        <p>Kayıttaki gitarları ayırır; ritim, solo ve temiz tonları ayrı ayrı dinler, en yakın amfi modelini ve efektleri seçer. İki tonlu şarkılarda CTL ile geçiş yaparsın.</p>
      </div>
      <ol className="flow">
        <li><b>İndir</b><span>YouTube'dan sesi alır.</span></li>
        <li><b>Ayrıştır</b><span>Gitarı diğer enstrümanlardan ayırır.</span></li>
        <li><b>Analiz</b><span>Gain, EQ, delay ve reverb'i ölçer.</span></li>
        <li><b>GT-1</b><span>Yedekler, yazar, geri okuyup doğrular.</span></li>
      </ol>
      {recents.length > 0 && (
        <div className="recent">
          <span className="tm-label">Son işler</span>
          <div className="recent__list">
            {recents.slice(0, 6).map((r) => (
              <button key={r.source} className="recent__row" type="button" onClick={() => onPick(r)}>
                <span className="tm-readout">{r.slot ?? "—"}</span>
                <span className="recent__title">{r.title}</span>
                <span className="recent__when">{new Date(r.when).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Result({ r, target }: { r: RunResult; target: Target }) {
  const tu = r.tuning;
  const written = r.patches.filter((p) => p.slot?.startsWith("U")).map((p) => p.slot);
  return (
    <section className="job">
      <div className="job__head">
        <span className="tm-label">{written.length ? `${written.join(", ")} cihaza yazıldı` : target === "listen" ? "Edit buffer'a yüklendi" : "Dosyaya yazıldı"}</span>
        <h1>{r.title}</h1>
        <div className="job__sub">
          {tu && (tu.semitones
            ? <span>Akort <strong>{tu.name}</strong> · <strong>{tu.user_tuning}</strong> çal, pitch shifter {tu.semitones > 0 ? "+" : ""}{tu.semitones}</span>
            : <span>Akort <strong>{tu.name}</strong>{tu.evidence?.source === "default" ? " (belirtilmedi)" : ""} · pitch shifter yok</span>)}
          <span>Tempo <strong>{Math.round(r.tempo)}</strong> BPM</span>
          <span>Süre <strong>{mmss(r.duration)}</strong></span>
        </div>
      </div>
      {r.claude?.ok && (
        <Notice tone="ok" title={`Claude modu · ${r.claude.song || r.title}`}>{r.claude.rig_notes}</Notice>
      )}
      {r.claude && !r.claude.ok && (
        <Notice tone="warn" title="Claude modu çalışmadı, algoritmanın sonucu yazıldı">{r.claude.error}</Notice>
      )}
      <div className="results">{r.patches.map((p) => <PatchCard key={p.group} patch={p} duration={r.duration} />)}</div>
      <Notice title="Dosyalar">
        Patch: <span className="tm-readout">{r.tsl}</span>
        {r.backup && <><br />Önceki slot yedeği: <span className="tm-readout">{r.backup}</span></>}
      </Notice>
    </section>
  );
}
