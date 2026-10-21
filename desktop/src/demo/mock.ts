// Demo mode: a stand-in for the Tauri side (run_cli and friends). It replays what the tonematch CLI
// prints for each command, with realistic timing, so every screen works without a GT-1 or Python.
// Turned on in Settings, or automatically when the UI runs in a plain browser (npm run dev, no Tauri).
import { planTuning } from "../tuning";
import { DEMO_SLOTS, demoCalibration, demoRun } from "./fixtures";

type Emit = (event: "cli-line" | "cli-exit", payload: unknown) => void;
type Job = { stop?: () => void; cancel: () => void };

const listeners = new Map<string, Set<(e: { payload: unknown }) => void>>();
const jobs = new Map<number, Job>();
let next = 0;
let slots = DEMO_SLOTS.map((s) => ({ ...s }));
let current = "U94";
let updated = Date.now() / 1000 - 3 * 3600;
let calRound = 0;

const emit: Emit = (event, payload) => listeners.get(event)?.forEach((f) => f({ payload }));
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function mockListen(event: string, cb: (e: { payload: unknown }) => void) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event)!.add(cb);
}

export async function mockInvoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  switch (cmd) {
    case "environment":
      return { project: "(demo)", venv: "(demo)", uv: null, ready: true, platform: "demo", demo: true } as T;
    case "cached_slots":
      return { updated, slots } as T;
    case "reveal_path":
      return undefined as T;
    case "run_cli": {
      const id = ++next;
      start(id, args.args as string[]);
      return id as T;
    }
    case "cancel_job": jobs.get(args.job as number)?.cancel(); return undefined as T;
    case "stop_job": {
      const j = jobs.get(args.job as number);
      if (!j?.stop) throw new Error("bu iş durdurma isteğini desteklemiyor");
      j.stop();
      return undefined as T;
    }
  }
  throw new Error(`demo: bilinmeyen komut ${cmd}`);
}

function start(id: number, args: string[]) {
  let stopped = false, cancelled = false;
  const job: Job = { cancel: () => { cancelled = true; }, stop: () => { stopped = true; } };
  jobs.set(id, job);
  const out = (line: string, stream: "stdout" | "stderr" = "stdout") => { if (!cancelled) emit("cli-line", { job: id, stream, line }); };
  const result = (v: unknown) => out(`@@RESULT ${JSON.stringify(v)}`);
  const error = (message: string) => out(`@@ERROR ${JSON.stringify({ message, kind: "RuntimeError" })}`);
  /** wait, unless the job was cancelled meanwhile */
  const wait = async (ms: number) => { await sleep(ms); if (cancelled) throw new Error("cancelled"); };
  const opt = (name: string) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };

  const body = async (): Promise<number> => {
    const [c0, c1] = args;
    if (c0 === "gt1" && c1 === "status") {
      await wait(1100);
      updated = Date.now() / 1000;
      result({ connected: true, current, edit_buffer: slotName(current), output_select_from_system: true, preamp_from_system: false, slots });
      return 0;
    }
    if (c0 === "gt1" && c1 === "info") {
      await wait(400);
      result({ connected: true, current, edit_buffer: slotName(current), output_select_from_system: true, preamp_from_system: false });
      return 0;
    }
    if (c0 === "gt1" && c1 === "list") { await wait(900); result({ slots, cached: false }); return 0; }
    if (c0 === "gt1" && c1 === "select") {
      await wait(500);
      current = args[2];
      result({ slot: current, name: slotName(current) });
      return 0;
    }
    if (c0 === "gt1" && c1 === "backup") {
      for (const s of slots) { out(`  ${s.slot} ${s.name}`); await wait(28); }
      out("backup written: backups/20261021-190000_all_U01-U99.tsl");
      return 0;
    }
    if (c0 === "gt1" && c1 === "save") {
      await wait(1400);
      const slot = args[2];
      const name = opt("--expect-name") ?? slotName(current);
      remember(slot, name.trim());
      current = slot;
      result({ slot, name, saved: true, backup: `backups/20261021-190500_${slot}.tsl`,
        changed: [{ label: "PRESENCE", from: "0", to: "18" }, { label: "MIDDLE", from: "51", to: "58" }] });
      return 0;
    }
    if (c0 === "gt1" && c1 === "tuner") return tuner(args.includes("--multi"));
    if (c0 === "calibrate") return calibrate();
    if (c0 === "run") return run();
    out(`demo: '${args.join(" ")}' desteklenmiyor`, "stderr");
    return 2;
  };

  async function run(): Promise<number> {
    const src = args[1];
    const r = demoRun(src);
    const toFile = args.includes("--no-device");
    const slot = opt("--slot");
    const tuning = opt("--tuning");
    out("1/4 indiriliyor / hazırlanıyor ...");
    await wait(1600);
    out(`    ${r.artist} - ${r.title.replace(`${r.artist} - `, "")}`);
    await wait(500);
    out("2/4 gitar ayrıştırılıyor (ilk seferde ~1-2 dk) ...");
    for (let p = 0; p <= 100; p += 10) { out(`  BS-Roformer-SW ${p}%`, "stderr"); await wait(320); }
    out("3/4 ton analizi ...");
    await wait(1500);
    out("    rol ayrımı: " + r.patches.flatMap((p) => p.tones.map((t) => t.role)).join(", "));
    await wait(700);
    out("4/4 GT-1 eşleştirmesi ...");
    if (args.includes("--claude")) {
      out("    Claude modu: motorun önerisi gözden geçiriliyor ...");
      await wait(2200);
      r.claude = { enabled: true, ok: true, model: "claude-opus-5-5", backend: "cli", song: r.title,
        rig_notes: "Kayıtta humbucker'lı bir gitar ve hafif boost'lanmış İngiliz tipi bir amfi kullanılmış; motorun seçimi buna uygun." };
      r.patches.forEach((p) => p.tones.forEach((t) => { t.claude = { confidence: "medium", why: "Kayıttaki ekipmana göre bu amfi modeli ve boost en yakın seçim." }; }));
    }
    await wait(1200);
    // same rule as the CLI: no --tuning = E standard, no shifter; otherwise FX1 PITCHSHIFTER by the shift
    const plan = planTuning(tuning ?? "");
    const semis = "error" in plan ? 0 : plan.semitones;
    r.tuning = { name: tuning ? tuning.toUpperCase() : "E standart", user_tuning: "error" in plan ? "EADGBE" : plan.play, semitones: semis,
      evidence: { source: tuning ? "user" : "default" } };
    r.patches.forEach((p) => p.tones.forEach((t) => {
      t.fx = t.fx.filter((f) => f.name !== "PITCHSHIFTER");
      if (semis) t.fx.unshift({ slot: "FX1", name: "PITCHSHIFTER", detail: `${semis > 0 ? "+" : ""}${semis}` });
    }));
    if (args.includes("--separate")) {
      r.patches = r.patches.flatMap((p) => p.dual
        ? p.tones.map((t, i) => ({ group: t.role, name: `${p.name.split(" ")[0]} ${i ? "CLN" : "RHY"}`, slot: null, dual: false, assigns: [], tones: [t] }))
        : [p]);
    }
    const start = slot ? Number(slot.slice(1)) : null;
    r.patches.forEach((p, i) => {
      p.slot = toFile ? null : start ? `U${String(start + i).padStart(2, "0")}` : "TEMP";
      if (start && !toFile) remember(p.slot!, p.name);
    });
    if (start && !toFile) current = r.patches[0].slot!;
    r.backup = start && !toFile ? `backups/20261021-190000_before_${r.patches[0].slot}.tsl` : null;
    out(`.tsl: ${r.tsl}`);
    result(r);
    return 0;
  }

  async function tuner(multi: boolean): Promise<number> {
    await wait(700);
    out(`@@TUNER ${JSON.stringify({ kind: "start", mode: multi ? "multi" : "single" })}`);
    const notes = ["E", "A", "D", "G", "B", "E"];
    let t = 0;
    while (!stopped && !cancelled) {
      t += 1;
      if (multi) {
        for (let s = 6; s >= 1; s--) {
          const drift = s === 3 ? 18 * Math.cos(t / 9) : s === 5 ? -9 + 6 * Math.sin(t / 7) : 2 * Math.sin(t / 5 + s);
          const c = Math.round(drift);
          out(`@@TUNER ${JSON.stringify({ kind: "multi", string: s, note: notes[6 - s], cents: c, in_tune: Math.abs(c) <= 3 })}`);
        }
      } else {
        // a string being tuned up: far flat, close, then settling in
        const phase = (t % 120) / 120;
        const c = phase < 0.1 ? null : Math.round(-40 * Math.exp(-phase * 5) + 2 * Math.sin(t / 3));
        out(`@@TUNER ${JSON.stringify(c === null ? { kind: "single", note: null, cents: 0, in_tune: false } : { kind: "single", note: "A", cents: c, in_tune: Math.abs(c) <= 3 })}`);
      }
      await sleep(110);
    }
    if (cancelled) return 1;
    result({ reason: "stopped" });
    return 0;
  }

  async function calibrate(): Promise<number> {
    const role = opt("--role") ?? "rhythm";
    const seconds = Number(opt("--seconds") ?? 20);
    const countdown = Number(opt("--countdown") ?? 3);
    const slot = opt("--slot") ?? current;
    await wait(1200);
    const r = demoRun(args[1]);
    const p = r.patches.find((x) => x.tones.some((t) => t.role === role)) ?? r.patches[0];
    const tone = p.tones.find((t) => t.role === role) ?? p.tones[0];
    const ctl_on = p.dual && p.tones[1]?.role === role;
    out(`@@CALIB ${JSON.stringify({ kind: "info", message: "hazır", phase: "ready", patch: p.name.trim(), amp: tone.amp, slot,
      ctl_on, duration: r.duration, segments: tone.segments })}`);
    for (let n = countdown; n >= 1; n--) { out(`@@CALIB ${JSON.stringify({ kind: "info", message: `${n} ...`, phase: "countdown", n })}`); await wait(1000); }
    out(`@@CALIB ${JSON.stringify({ kind: "info", message: "ÇAL!", phase: "record", seconds })}`);
    const t0 = Date.now();
    while (Date.now() - t0 < seconds * 1000) {
      const x = (Date.now() - t0) / 1000;
      const db = -16 + 7 * Math.sin(x * 2.1) * Math.sin(x * 0.7) + (Math.random() - 0.5) * 6 + (x % 4 < 0.15 ? 12 : 0);
      out(`@@CALIB ${JSON.stringify({ kind: "level", db: Math.min(-0.5, +db.toFixed(1)) })}`);
      await wait(100);
    }
    out(`@@CALIB ${JSON.stringify({ kind: "info", message: "ölçülüyor ...", phase: "measure" })}`);
    await wait(1600);
    result(demoCalibration(role, calRound++, p.name.trim(), tone.amp, slot));
    return 0;
  }

  body().then(
    (code) => { jobs.delete(id); emit("cli-exit", { job: id, code }); },
    (e) => {
      jobs.delete(id);
      if (!cancelled) error(String(e?.message ?? e));
      emit("cli-exit", { job: id, code: cancelled ? null : 1 });
    },
  );
}

function slotName(s: string) { return slots.find((x) => x.slot === s)?.name ?? "INIT PATCH"; }
function remember(slot: string, name: string) {
  slots = slots.map((s) => (s.slot === slot ? { ...s, name: name.padEnd(16) } : s));
  updated = Date.now() / 1000;
}
