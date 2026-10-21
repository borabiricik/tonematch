// Demo mode for `tonematch practice ...`: the same payloads and @@PRACTICE event streams as the CLI
// (src/tonematch/practice/cli.py), from a fixture the CLI generated (practice.json) and a simulated player
// who is good but not perfect, and gets a little better every take.
import data from "./practice.json";
import type { Exercise, QuizKind, Routine, Solo, Stats, TabNote } from "../app/practice/types";

type IO = {
  out: (line: string) => void; result: (v: unknown) => void; error: (m: string) => void;
  wait: (ms: number) => Promise<void>; opt: (name: string) => string | undefined; stopped: () => boolean;
};

const EXERCISES = [...(data.exercises as unknown as Exercise[]), ...(data.extra as unknown as Exercise[])];
const working: Record<string, number> = {};
const best: Record<string, number> = {};
const streakClean: Record<string, number> = {};
const doneToday = new Set<string>();
const settings = { ...(data.today as unknown as Routine).settings };
let takes = 0;
let skill = 0.86; // the simulated player's accuracy, creeping up

const DEMO_SOLO_NOTES: TabNote[] = (EXERCISES.find((e) => e.id === "pent6/A/1")?.notes ?? []).map((n, i) => ({
  ...n, beat: Math.round(n.beat * 4) / 4 + (i >= 12 ? 1 : 0), dur: 0.25, tech: i === 11 ? "b" : n.tech,
}));
const solos: Solo[] = [{ track_id: "demo", title: "Demo Solo", artist: "Demo", tempo: 112, role: "lead",
  phrases: [0, 1, 2].map((index) => ({ index, beats: 8, count: DEMO_SOLO_NOTES.length, start_s: 62 + index * 9 })) }];

function find(id: string): Exercise | null {
  if (id.startsWith("solo/")) {
    const [, tid, idx] = id.split("/");
    const s = solos.find((x) => x.track_id === tid);
    if (!s) return null;
    const i = Number(idx);
    return { id, skill: id, family: "solo", group: "Solo", title: `${s.artist} - ${s.title} · cümle ${i + 1}/${s.phrases.length}`,
      subtitle: `Kayıtta ${s.tempo} BPM · ${DEMO_SOLO_NOTES.length} nota · otomatik transkripsiyon (taslak)`, per_beat: 4,
      bpm: Math.round(s.tempo * 0.6), goal_bpm: s.tempo, notes: DEMO_SOLO_NOTES, beats: 8, level: 4, key: "A",
      tips: ["Önce dinle: kaydı yavaşlatıp (Dinle) cümleyi içinden söyleyebilene kadar.", "En zor ölçüyü ayrı döngüye al."],
      focus: "Önce kulak, sonra parmak", working: working[id] ?? Math.round(s.tempo * 0.6), best: best[id] ?? 0 };
  }
  const e = EXERCISES.find((x) => x.id === id);
  return e ? { ...e, working: working[e.skill] ?? e.bpm, best: best[e.skill] ?? 0 } : null;
}

function routine(): Routine {
  const r = structuredClone(data.today as unknown as Routine);
  const scale = settings.minutes / r.minutes;
  r.minutes = settings.minutes;
  r.settings = { ...settings };
  for (const b of r.blocks) {
    b.minutes = Math.max(2, Math.round(b.minutes * scale));
    for (const e of b.exercises) { const ex = find(e.id); if (ex) { e.bpm = ex.working; e.best = ex.best; } }
  }
  r.date = new Date().toISOString().slice(0, 10);
  r.done_ids = [...doneToday];
  r.streak = 6 + (doneToday.size ? 1 : 0);
  return r;
}

const gauss = () => { let u = 0, v = 0; while (!u) u = Math.random(); while (!v) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
const step = (bpm: number) => Math.max(2, Math.round(bpm * 0.04));

export async function practice(args: string[], io: IO): Promise<number> {
  const c = args[1];
  const ev = (v: unknown) => io.out(`@@PRACTICE ${JSON.stringify(v)}`);
  if (c === "today") { await io.wait(250); io.result(routine()); return 0; }
  if (c === "catalog") {
    await io.wait(300);
    io.result({ key: io.opt("--key") ?? data.key, exercises: (data.exercises as unknown as Exercise[]).map((e) => find(e.id)) });
    return 0;
  }
  if (c === "exercise") {
    await io.wait(200);
    const e = find(args[2]);
    if (!e) { io.error(`bilinmeyen egzersiz: ${args[2]}`); return 1; }
    io.result(e);
    return 0;
  }
  if (c === "set-bpm") { const e = find(args[2]); if (e) { working[e.skill] = Number(args[3]); streakClean[e.skill] = 0; } io.result({ bpm: Number(args[3]) }); return 0; }
  if (c === "settings") {
    const m = io.opt("--minutes"); if (m) settings.minutes = Number(m);
    const t = io.opt("--threshold"); if (t) settings.threshold = Number(t);
    io.result(settings); return 0;
  }
  if (c === "play") return play(args[2], io, ev);
  if (c === "quiz") return quiz((args[2] ?? "mix") as QuizKind, Number(io.opt("--count") ?? 10), io, ev);
  if (c === "latency") return latency(io, ev);
  if (c === "stats") { await io.wait(300); io.result(stats()); return 0; }
  if (c === "solos") { await io.wait(200); io.result({ solos }); return 0; }
  if (c === "solo") {
    for (const m of ["vuruşlar bulunuyor ...", "1:02.0-1:31.4 notalar çıkarılıyor ...", "2:40.2-3:05.8 notalar çıkarılıyor ..."]) {
      ev({ kind: "info", message: m }); await io.wait(1100);
    }
    const tid = `demo${solos.length + 1}`;
    const s: Solo = { ...solos[0], track_id: tid, title: args[2].replace(/^ytsearch\d*:/, "").slice(0, 40) || "Demo" };
    solos.push(s);
    io.result({ ...s, phrases: s.phrases.map((p) => ({ ...p, id: `solo/${tid}/${p.index}` })) });
    return 0;
  }
  if (c === "reference") { await io.wait(2500); io.result({ id: args[2], speed: 0.7, seconds: 6.2 }); return 0; }
  io.error(`demo: 'practice ${c}' desteklenmiyor`);
  return 2;
}

async function play(id: string, io: IO, ev: (v: unknown) => void): Promise<number> {
  const ex = find(id);
  if (!ex) { io.error(`bilinmeyen egzersiz: ${id}`); return 1; }
  const bpm = Number(io.opt("--bpm") ?? ex.working);
  const beatMs = 60000 / bpm;
  const loopS = (ex.beats * beatMs) / 1000;
  const loops = Number(io.opt("--loops") ?? 0) || Math.max(1, Math.min(12, Math.round(30 / loopS)));
  ev({ kind: "ready", id, title: ex.title, bpm, loops, warnings: [] });
  await io.wait(700);
  ev({ kind: "start", bpm, loops, beat_s: beatMs / 1000, beats: ex.beats, count_in: 4, device: "GT-1 (demo)" });
  // harder when faster than the player's comfort tempo
  const ease = Math.max(0.55, Math.min(0.995, skill - Math.max(0, bpm - ex.working) * 0.01));
  const events: { t: number; v: Record<string, unknown> }[] = [];
  const total = ex.beats * loops;
  for (let b = -4; b < total; b++) events.push({ t: (b + 4) * beatMs, v: { kind: "beat", beat: b, loop: b >= 0 ? Math.floor(b / ex.beats) : -1, count_in: b < 0 } });
  const verdicts: string[] = [];
  const dts: number[] = [];
  for (let k = 0; k < loops; k++) {
    ex.notes.forEach((n, j) => {
      const r = Math.random();
      const dt = gauss() * 14 + 4;
      let status = Math.abs(dt) <= 25 ? "hit" : dt < 0 ? "early" : "late";
      if (r > ease) status = r > ease + (1 - ease) / 2 ? "miss" : "wrong";
      verdicts.push(status);
      if (status !== "miss" && status !== "wrong") dts.push(dt);
      events.push({ t: (4 + k * ex.beats + n.beat) * beatMs + 70 + (status === "miss" ? 120 : 0),
        v: { kind: "note", status, i: k * ex.notes.length + j, j, loop: k, dt_ms: status === "miss" ? undefined : Math.round(dt * 10) / 10, expected: n.midi, played: n.midi } });
    });
  }
  events.sort((a, b) => a.t - b.t);
  const t0 = performance.now();
  let lvl = 0;
  for (const e of events) {
    while (performance.now() - t0 < e.t) {
      if (io.stopped()) break;
      await io.wait(15);
      if (performance.now() - lvl > 100) { lvl = performance.now(); ev({ kind: "level", db: Math.round((-20 + gauss() * 4) * 10) / 10 }); }
    }
    if (io.stopped()) break;
    ev(e.v);
  }
  const judged = verdicts.slice(0, Math.max(1, events.filter((e) => e.v.kind === "note" && performance.now() - t0 >= e.t).length));
  const right = judged.filter((v) => v === "hit" || v === "early" || v === "late").length;
  const counts = Object.fromEntries(["hit", "early", "late", "wrong", "miss"].map((k) => [k, judged.filter((v) => v === k).length]));
  const accuracy = Math.round((right / judged.length) * 1000) / 1000;
  const onTime = Math.round(((counts.hit as number) / judged.length) * 1000) / 1000;
  const mean = dts.length ? dts.reduce((a, b) => a + b, 0) / dts.length : null;
  const spread = mean === null ? null : Math.sqrt(dts.reduce((a, b) => a + (b - mean) ** 2, 0) / dts.length);
  const perLoop = Array.from({ length: Math.ceil(judged.length / ex.notes.length) }, (_, k) => {
    const l = judged.slice(k * ex.notes.length, (k + 1) * ex.notes.length);
    return Math.round((l.filter((v) => v === "hit" || v === "early" || v === "late").length / l.length) * 1000) / 1000;
  });
  // the ladder, as progress.decide
  const clean = accuracy >= settings.threshold && onTime >= 0.6;
  const sk = ex.skill;
  if (bpm !== (working[sk] ?? ex.bpm)) { working[sk] = bpm; streakClean[sk] = 0; }
  streakClean[sk] = clean ? (streakClean[sk] ?? 0) + 1 : 0;
  if (clean) best[sk] = Math.max(best[sk] ?? 0, bpm);
  const up = bpm + step(bpm);
  const decision = clean && streakClean[sk] >= 2
    ? { suggest: "faster", to_bpm: up, message: bpm < ex.goal_bpm ? `Üst üste ${streakClean[sk]} temiz tur. ${up} BPM'e geçelim mi?` : `Hedef tempoyu (${ex.goal_bpm}) geçtin ve temiz. ${up} BPM'i dene ya da sonraki egzersize geç.` }
    : clean ? { suggest: "again", to_bpm: bpm, message: `Temiz tur (%${Math.round(accuracy * 100)}). Bir tur daha temiz çalarsan tempoyu artıralım.` }
      : accuracy < 0.8 ? { suggest: "slower", to_bpm: Math.max(30, bpm - step(bpm)), message: `%${Math.round(accuracy * 100)} doğruluk. ${Math.max(30, bpm - step(bpm))} BPM'e inip temiz çalalım; yanlışı hızlı çalmak yanlışı ezberletir.` }
        : { suggest: "again", to_bpm: bpm, message: `%${Math.round(accuracy * 100)}, temize az kaldı (%${Math.round(settings.threshold * 100)}). Aynı tempoda bir tur daha.` };
  takes++;
  skill = Math.min(0.995, skill + 0.035);
  doneToday.add(id);
  io.result({
    id, skill: sk, bpm, loops, notes: judged.length, correct: right, accuracy, on_time: onTime,
    mean_ms: mean === null ? null : Math.round(mean * 10) / 10, spread_ms: spread === null ? null : Math.round(spread * 10) / 10,
    extras: Math.random() < 0.4 ? 1 : 0, per_loop: perLoop, counts, trouble: [], seconds: Math.round((performance.now() - t0) / 100) / 10,
    latency_ms: 14.2, stopped: io.stopped(), device: "GT-1 (demo)", warnings: [],
    decision: { ...decision, clean, best: best[sk] ?? 0, streak: streakClean[sk] },
  });
  return 0;
}

const QUESTIONS: Record<Exclude<QuizKind, "mix">, { prompt: string; answer: string; heard: string[]; string?: number; frets?: number[]; play?: number[] }[]> = {
  fretboard: [{ prompt: "5. telde C", answer: "C: 5. tel 3, 15. perde", heard: ["C"], string: 5, frets: [3, 15] },
    { prompt: "3. telde E", answer: "E: 3. tel 9. perde", heard: ["E"], string: 3, frets: [9] },
    { prompt: "2. telde F#", answer: "F#: 2. tel 7. perde", heard: ["F"], string: 2, frets: [7] }],
  interval: [{ prompt: "A (6. tel 5. perde) üstüne büyük üçlü", answer: "C# (M3, 4 yarım ses)", heard: ["C#"] },
    { prompt: "D (5. tel 5. perde) üstüne tam beşli", answer: "A (P5, 7 yarım ses)", heard: ["A"] }],
  degree: [{ prompt: "A minör pentatonik: ♭3. derece", answer: "C (♭3)", heard: ["C"] }, { prompt: "G majör (iyonyen): 6. derece", answer: "E (6)", heard: ["E"] }],
  chord: [{ prompt: "Dm7 akorunun 7'lisi", answer: "C", heard: ["C"] }, { prompt: "E akorunun 3'lüsü", answer: "G#", heard: ["G#"] }],
  echo: [{ prompt: "Dinle ve çal: 2 nota", answer: "E G", heard: ["E", "G"], play: [64, 67] }, { prompt: "Dinle ve çal: 2 nota", answer: "A C#", heard: ["A", "C#"], play: [57, 61] }],
};

async function quiz(kind: QuizKind, count: number, io: IO, ev: (v: unknown) => void): Promise<number> {
  await io.wait(600);
  ev({ kind: "start", quiz: kind, count, device: "GT-1 (demo)" });
  const kinds = Object.keys(QUESTIONS) as Exclude<QuizKind, "mix">[];
  const items: { item: string; right: boolean; ms: number }[] = [];
  for (let n = 1; n <= count && !io.stopped(); n++) {
    const k = kind === "mix" ? kinds[n % kinds.length] : kind;
    const q = QUESTIONS[k][n % QUESTIONS[k].length];
    ev({ kind: "question", n, item: `${k}:${n}`, count: q.heard.length, ...q });
    await io.wait(q.play ? 1600 : 900);
    const right = Math.random() < 0.8;
    const heard = right ? q.heard : ["D#"];
    for (const h of heard) { await io.wait(600); ev({ kind: "heard", n, note: h, midi: 60 }); }
    const ms = 1200 + Math.round(Math.random() * 1800);
    items.push({ item: `${k}:${n}`, right, ms });
    ev({ kind: "answer", n, right, answer: q.answer, played: heard, ms });
    await io.wait(1400);
  }
  doneToday.add(`quiz:${kind}`);
  const right = items.filter((i) => i.right).length;
  const times = items.filter((i) => i.right).map((i) => i.ms);
  io.result({ quiz: kind, asked: items.length, right, accuracy: items.length ? right / items.length : 0,
    mean_ms: times.length ? Math.round(times.reduce((a, b) => a + b, 0) / times.length) : null, items });
  return 0;
}

async function latency(io: IO, ev: (v: unknown) => void): Promise<number> {
  await io.wait(600);
  ev({ kind: "start", bpm: 80, loops: 1, beat_s: 0.75, beats: 16, count_in: 4, device: "GT-1 (demo)" });
  const taps: number[] = [];
  for (let b = -4; b < 16 && !io.stopped(); b++) {
    ev({ kind: "beat", beat: b, loop: b < 0 ? -1 : 0, count_in: b < 0 });
    await io.wait(750);
    if (b >= 0) { const dt = Math.round((18 + gauss() * 7) * 10) / 10; taps.push(dt); ev({ kind: "tap", beat: b, dt_ms: dt }); }
  }
  const sorted = [...taps].sort((a, b) => a - b);
  const off = sorted.length >= 8 ? sorted[Math.floor(sorted.length / 2)] : null;
  if (off !== null) settings.latency_ms = off;
  io.result({ offset_ms: off, used: taps.length, taps, seconds: 15, latency_ms: 14.2, stopped: io.stopped(), device: "GT-1 (demo)" });
  return 0;
}

function stats(): Stats {
  // two weeks of a player who practises most days
  const day = (d: number) => new Date(Date.now() - d * 864e5).toISOString().slice(0, 10);
  const skills = [["pent/1", "A minör pentatonik · kutu 1", 92], ["chromatic/1234", "Kromatik 1-2-3-4", 104],
    ["seq/natural_minor/4/0", "A doğal minör (eolyen) · 4'lü sekans", 84], ["sweep/min/3", "Am arpej · 3 tel sweep", 66]] as const;
  return {
    skills: skills.map(([sk, title, top]) => ({
      skill: sk, title, takes: 20 + takes, working: working[sk] ?? top, best: best[sk] ?? top - 2,
      days: Array.from({ length: 12 }, (_, i) => ({ day: day(13 - i), best_clean: Math.round(top - 20 + i * 1.7), best_acc: 0.9, bpm: Math.round(top - 18 + i * 1.7) })),
    })),
    quiz: [{ quiz: "fretboard", sessions: 6, asked: 60, right: 47, days: [] }, { quiz: "interval", sessions: 3, asked: 30, right: 21, days: [] }],
    minutes: Array.from({ length: 14 }, (_, i) => ({ day: day(13 - i), minutes: i % 6 === 5 ? 0 : 18 + ((i * 7) % 15) })),
    streak: 6 + (doneToday.size ? 1 : 0), takes: 180 + takes, total_minutes: 412,
  };
}
