// Which string is being tuned and which way its key has to turn.
// The GT-1's single-string tuner only reports the nearest note and cents (no octave, no string number),
// so the string is the one whose target note is closest; the two E strings (two Ds in drop D) are told apart by the last one.

export type Ref = "EADGBE" | "DADGBE";
export type Turn = "tighten" | "loosen" | "hold";
export type Reading = { note: string | null; cents: number; in_tune: boolean };
export type StringState = { string: number; note: string; offset: number; turn: Turn };

export const STRINGS = [6, 5, 4, 3, 2, 1];
/** Target notes, thickest (6) first. */
export const TARGETS: Record<Ref, string[]> = { EADGBE: ["E", "A", "D", "G", "B", "E"], DADGBE: ["D", "A", "D", "G", "B", "E"] };
export const target = (ref: Ref, string: number) => TARGETS[ref][6 - string];

const PC: Record<string, number> = { C: 0, "C#": 1, D: 2, "D#": 3, E: 4, F: 5, "F#": 6, G: 7, "G#": 8, A: 9, "A#": 10, B: 11 };
const IN_TUNE = 3; // cents, the unit's own window (device/gt1/tuner.py IN_TUNE_CENTS)

/** Signed distance in cents from the reading to the target note, folded into -600..+599 (no octave info). */
export function offsetTo(note: string, cents: number, targetNote: string): number {
  let semis = (((PC[note] - PC[targetNote]) % 12) + 12) % 12;
  if (semis >= 6) semis -= 12;
  return semis * 100 + cents;
}

export const turnFor = (offset: number): Turn => (Math.abs(offset) <= IN_TUNE ? "hold" : offset < 0 ? "tighten" : "loosen");

/** The string a single-mode reading most likely belongs to. Ties (the two E strings) go to the one nearest `last`. */
export function guessString(note: string, cents: number, ref: Ref, last: number | null): number {
  let best = STRINGS[0];
  let bestDist = Infinity;
  for (const s of STRINGS) {
    const d = Math.abs(offsetTo(note, cents, target(ref, s)));
    const closer = d < bestDist - 0.5;
    const tie = Math.abs(d - bestDist) <= 0.5;
    // tie: the one nearest the last string; still even (D after A in drop D), the next thinner one (strings go 6 -> 1)
    const nearer = last !== null && (Math.abs(s - last) < Math.abs(best - last) || (Math.abs(s - last) === Math.abs(best - last) && s < best));
    if (closer || (tie && nearer)) { best = s; bestDist = d; }
  }
  return best;
}

export function stringState(string: number, r: Reading | null | undefined, ref: Ref): StringState | null {
  if (!r || r.note === null) return null;
  const offset = offsetTo(r.note, r.cents, target(ref, string));
  return { string, note: r.note, offset, turn: turnFor(offset) };
}

export type Tone = "ok" | "near" | "far";
export const toneOf = (s: StringState): Tone => (s.turn === "hold" ? "ok" : Math.abs(s.offset) <= 15 ? "near" : "far");

export const TURN_TEXT: Record<Turn, string> = { tighten: "sıkıştır", loosen: "gevşet", hold: "akortta" };
