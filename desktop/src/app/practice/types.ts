// The practice CLI's payloads (`tonematch practice ... --json`, src/tonematch/practice/). Kept in step with
// exercises.Exercise, progress.routine / stats, session.play, quiz.run_quiz and solo.list_solos.

export type TabNote = { beat: number; dur: number; string: number; fret: number; midi: number; tech: "" | "h" | "p" | "d" | "u" | "b" };

export type Exercise = {
  id: string; skill: string; family: string; group: string; title: string; subtitle: string;
  per_beat: number; bpm: number; goal_bpm: number; notes: TabNote[]; beats: number; level: number;
  tips: string[]; focus: string; key: string | null;
  /** from the practice state: the player's working tempo and best clean tempo */
  working: number; best: number;
};

export type RoutineExercise = { id: string; title: string; subtitle: string; group: string; bpm: number; best: number; goal: number; warm: number };
export type Block = {
  id: "warmup" | "technique" | "burst" | "scales" | "theory" | "solo"; title: string; minutes: number; why: string;
  items: string[]; exercises: RoutineExercise[]; quiz?: QuizKind;
};
export type Settings = { minutes: number; threshold: number; latency_ms: number; click_level: number; count_in: number };
export type Routine = { date: string; minutes: number; key: string; focus: string; blocks: Block[]; done_ids: string[]; streak: number; settings: Settings };

export type NoteStatus = "hit" | "early" | "late" | "wrong" | "miss" | "extra" | "ring";
export type PracticeEvent =
  | { kind: "ready"; id: string; title: string; bpm: number; loops: number; warnings: string[] }
  | { kind: "start"; bpm: number; loops: number; beat_s: number; beats: number; count_in: number; device: string }
  | { kind: "beat"; beat: number; loop: number; count_in: boolean }
  | { kind: "note"; status: NoteStatus; i?: number; j?: number; loop?: number; dt_ms?: number; played?: number | null; expected?: number; t?: number }
  | { kind: "level"; db: number }
  | { kind: "tap"; beat: number; dt_ms: number }
  | { kind: "info"; message: string }
  | QuizEvent;

export type Decision = { suggest: "faster" | "slower" | "again"; to_bpm: number; message: string; clean: boolean; best: number; streak: number };
export type TakeResult = {
  id: string; skill: string; bpm: number; loops: number; notes: number; correct: number; accuracy: number; on_time: number;
  mean_ms: number | null; spread_ms: number | null; extras: number; per_loop: number[]; counts: Partial<Record<NoteStatus, number>>;
  trouble?: number[]; seconds: number; latency_ms: number; stopped: boolean; decision: Decision | null; warnings: string[];
};

export type QuizKind = "fretboard" | "interval" | "degree" | "chord" | "echo" | "mix";
export type QuizEvent =
  | { kind: "question"; n: number; prompt: string; item: string; count: number; answer: string; string?: number; frets?: number[]; play?: number[]; root?: number }
  | { kind: "heard"; n: number; note: string; midi: number }
  | { kind: "answer"; n: number; right: boolean; answer: string; played: string[]; ms: number | null };
export type QuizResult = { quiz: QuizKind; asked: number; right: number; accuracy: number; mean_ms: number | null; items: { item: string; right: boolean; ms: number | null }[] };

export type SkillStat = {
  skill: string; title: string; takes: number; working: number | null; best: number;
  days: { day: string; best_clean: number; best_acc: number; bpm: number }[];
};
export type Stats = {
  skills: SkillStat[]; quiz: { quiz: QuizKind; sessions: number; asked: number; right: number; days: { day: string; asked: number; right: number; mean_ms: number | null }[] }[];
  minutes: { day: string; minutes: number }[]; streak: number; takes: number; total_minutes: number;
};

export type Solo = {
  track_id: string; title: string; artist: string; tempo: number; role: string;
  phrases: { index: number; beats: number; count: number; start_s: number; id?: string }[];
};

export const QUIZ_NAMES: Record<QuizKind, string> = {
  fretboard: "Klavyede nota", interval: "Aralık", degree: "Gam derecesi", chord: "Akor tonu", echo: "Kulaktan tekrar", mix: "Karışık",
};
export const QUIZ_HINTS: Record<QuizKind, string> = {
  fretboard: "Söylenen notayı o telde bul ve çal. Hız da ölçülür: düşünmeden bulmak, bilmektir.",
  interval: "Verilen notanın üstündeki aralığı çal. Aralıklar melodinin harfleridir.",
  degree: "Tonun derecesini klavyenin herhangi bir yerinde çal (oktav fark etmez).",
  chord: "Akorun istenen tonunu çal: solo, akor tonlarına basınca altyapıyı takip eder.",
  echo: "Dinle, sonra aynı notaları sırayla çal. Kulaktan çalmanın en kısa yolu.",
  mix: "Hepsinden karışık.",
};

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export const noteName = (m: number) => NOTE_NAMES[((m % 12) + 12) % 12];
