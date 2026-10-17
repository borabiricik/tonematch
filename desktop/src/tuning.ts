// Live preview of `--tuning`: same rule as tonematch.tuning.parse_tuning (the CLI stays the authority).
// The song's tuning must be EADGBE or DADGBE shifted as a whole by k semitones (k = -9..+2).

const PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const STANDARD = [40, 45, 50, 55, 59, 64];
const DROP_D = [38, 45, 50, 55, 59, 64];

export type TuningPlan = { play: "EADGBE" | "DADGBE"; semitones: number } | { error: string };

export function planTuning(text: string): TuningPlan {
  let t = text.trim().replace(/♯/g, "#").replace(/♭/g, "b");
  if (!t) return { play: "EADGBE", semitones: 0 };
  if (!/[A-Z]/.test(t)) t = t.toUpperCase();
  const notes = [...t.matchAll(/([A-G])([#b]?)/g)];
  if (notes.map((m) => m[0]).join("") !== t.replace(/[\s,/-]/g, "")) return { error: "Notalar okunamadı. Örnek: EADGBE, D#G#C#F#A#D#" };
  if (notes.length !== 6) return { error: `6 tel gerekiyor, ${notes.length} nota var.` };
  const pcs = notes.map(([, n, acc]) => (PC[n] + (acc === "#" ? 1 : acc === "b" ? -1 : 0) + 12) % 12);
  for (const [ref, play] of [[STANDARD, "EADGBE"], [DROP_D, "DADGBE"]] as const) {
    const ks = new Set(pcs.map((p, i) => ((((p - (ref[i] % 12)) + 9) % 12) + 12) % 12 - 9));
    if (ks.size === 1) return { play, semitones: [...ks][0] };
  }
  return { error: "Açık akortlar tek pitch shifter ile yapılamaz." };
}
