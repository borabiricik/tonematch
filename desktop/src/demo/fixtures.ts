// Demo data in the exact shapes the CLI prints (`--json`, src/tonematch/report.py and cli.py).
// Used only by demo mode (src/demo/mock.ts): lets the whole UI run without a GT-1, Python or a network.
import type { RunResult, SlotInfo } from "../ds";

export const DEMO_SLOTS: SlotInfo[] = (() => {
  const named: Record<number, [string, string, number, boolean?]> = {
    1: ["CLEAN CHORUS", "CLEAN TWIN", 30], 2: ["BLUES DRIVE", "BLUES", 58], 3: ["CRUNCH PLEXI", "MS1959 I", 64],
    4: ["LEAD SOLO", "T-AMP LEAD", 72], 5: ["METAL RHY", "CORE METAL", 88], 6: ["AMBIENT", "FULL RANGE", 20],
    7: ["FUNK CLEAN", "NATURAL", 26], 8: ["DJENT", "BGNR UB METAL", 92], 10: ["SHOEGAZE", "VO DRIVE", 70],
    12: ["COUNTRY", "CLEAN TWIN", 32], 14: ["SRV TEXAS", "BLUES", 62], 15: ["BROWN SOUND", "MS1959 II", 78],
    20: ["U2 STREETS", "VO DRIVE", 44], 21: ["PINK FLOYD SOLO", "T-AMP LEAD", 70],
    31: ["RHCP UNDER", "NATURAL", 34], 32: ["NIRVANA TEEN/CL", "POWER DRIVE", 80, true],
    41: ["SLASH LEAD", "BG LEAD", 80], 55: ["JAZZ BOX", "FULL RANGE", 18], 60: ["QOTSA FUZZ", "POWER DRIVE", 86],
    77: ["GILMOUR CLEAN", "CLEAN TWIN", 36], 88: ["HENDRIX VOODOO", "MS1959 I", 82],
    93: ["SONNE RHY", "BGNR UB METAL", 73], 94: ["ARCTIC RHY", "COMBO CRUNCH", 82], 95: ["GUNS N RHY/CLN", "BG DRIVE", 78, true],
    96: ["GITAROO RHY/CLN", "MS1959 I", 78, true], 97: ["RUNNING RHY", "POWER DRIVE", 83], 98: ["NOTHING CLN", "CLEAN TWIN", 40],
    99: ["MASTER OF RHY", "CORE METAL", 95],
  };
  return Array.from({ length: 99 }, (_, i) => {
    const n = i + 1;
    const [name, amp, gain, dual] = named[n] ?? ["INIT PATCH", "CRUNCH", 50];
    return { slot: `U${String(n).padStart(2, "0")}`, name: name.padEnd(16), amp, gain, dual: !!dual };
  });
})();

type Fixture = { match: RegExp; result: RunResult };

const ARCTIC: RunResult = {
  track_id: "bpOSxM0rNPM", title: "Arctic Monkeys - Do I Wanna Know? (Official Video)", artist: "Arctic Monkeys",
  duration: 272, tempo: 85,
  tuning: { name: "E standart", user_tuning: "EADGBE", semitones: 0, evidence: { source: "default" } },
  patches: [{
    group: "rhythm", name: "ARCTIC RHY", slot: "U94", dual: false, assigns: [],
    tones: [{
      role: "rhythm", amp: "COMBO CRUNCH", drive: "crunch", stereo: "wide/double-tracked",
      knobs: { gain: 82, bass: 40, middle: 51, treble: 57, presence: 0, level: 41 },
      od: { type: "T-SCREAM", drive: 20, level: 70 },
      fx: [{ slot: "REVERB", name: "ROOM", detail: "0.8s" }],
      segments: [[3.7, 52.1], [60.4, 122.3], [142.1, 210.5], [214.0, 265.7]],
    }],
  }],
  tsl: "output/Arctic_Monkeys_Do_I_Wanna_Know.tsl", backup: "backups/20261021-174512_before_U94-U94.tsl",
};

const GUNS: RunResult = {
  track_id: "1w7OgIMMRc4", title: "Guns N' Roses - Sweet Child O' Mine (Official Music Video)", artist: "Guns N' Roses",
  duration: 356, tempo: 125,
  tuning: { name: "Eb standart", user_tuning: "EADGBE", semitones: -1, evidence: { source: "user" } },
  patches: [{
    group: "rhythm+clean", name: "GUNS N RHY/CLN", slot: "U95", dual: true,
    assigns: ["PREAMP TYPE BG DRIVE → CLEAN TWIN", "PREAMP GAIN 78 → 43", "PREAMP LEVEL 42 → 50", "OD/DS OFF", "DELAY OFF", "FX2 ON (COMPRESSOR)", "REVERB ROOM → PLATE"],
    tones: [
      {
        role: "rhythm", amp: "BG DRIVE", drive: "crunch", stereo: "stereo",
        knobs: { gain: 78, bass: 52, middle: 55, treble: 53, presence: 9, level: 42 },
        od: { type: "T-SCREAM", drive: 30, level: 62 },
        fx: [{ slot: "FX1", name: "PITCHSHIFTER", detail: "-1" }, { slot: "DELAY", name: "STANDARD", detail: "240 ms" },
          { slot: "REVERB", name: "ROOM", detail: "0.8s" }],
        segments: [[0.3, 45.6], [76.4, 105.4], [134.1, 200.2], [214.5, 354.4]],
      },
      {
        role: "clean", amp: "CLEAN TWIN", drive: "clean", stereo: "wide/double-tracked",
        knobs: { gain: 43, bass: 52, middle: 55, treble: 53, presence: 9, level: 50 },
        od: null,
        fx: [{ slot: "FX1", name: "PITCHSHIFTER", detail: "-1" }, { slot: "FX2", name: "COMPRESSOR", detail: "" },
          { slot: "REVERB", name: "PLATE", detail: "0.8s" }],
        segments: [[45.6, 76.4], [105.4, 134.1], [200.2, 214.5]],
      },
    ],
  }],
  tsl: "output/Guns_N_Roses_Sweet_Child_O_Mine.tsl", backup: "backups/20261021-180233_before_U95-U95.tsl",
};

const FLOYD: RunResult = {
  track_id: "file_comfortably_numb", title: "Pink Floyd - Comfortably Numb (solo)", artist: "Pink Floyd",
  duration: 383, tempo: 64,
  tuning: { name: "E standart", user_tuning: "EADGBE", semitones: 0, evidence: { source: "default" } },
  patches: [
    {
      group: "lead", name: "COMFORT LEAD", slot: "U21", dual: false, assigns: [],
      tones: [{
        role: "lead", amp: "T-AMP LEAD", drive: "high_gain", stereo: "mono-ish",
        knobs: { gain: 70, bass: 45, middle: 62, treble: 58, presence: 40, level: 48 },
        od: { type: "BLUES OD", drive: 45, level: 60 },
        fx: [{ slot: "FX2", name: "PHASER", detail: "" }, { slot: "DELAY", name: "ANALOG", detail: "440 ms" }, { slot: "REVERB", name: "HALL", detail: "2.4s" }],
        segments: [[240.2, 383.0]],
      }],
    },
    {
      group: "clean", name: "COMFORT CLN", slot: "U22", dual: false, assigns: [],
      tones: [{
        role: "clean", amp: "CLEAN TWIN", drive: "clean", stereo: "wide/double-tracked",
        knobs: { gain: 30, bass: 50, middle: 48, treble: 60, presence: 20, level: 52 },
        od: null,
        fx: [{ slot: "FX2", name: "CHORUS", detail: "" }, { slot: "REVERB", name: "HALL", detail: "2.0s" }],
        segments: [[0, 96.3], [120.5, 190.4]],
      }],
    },
  ],
  tsl: "output/Pink_Floyd_Comfortably_Numb.tsl", backup: "backups/20261021-181102_before_U21-U22.tsl",
};

export const FIXTURES: Fixture[] = [
  { match: /arctic|wanna know|bpOSxM0rNPM/i, result: ARCTIC },
  { match: /guns|sweet child|1w7OgIMMRc4|gnr/i, result: GUNS },
  { match: /floyd|comfortably|gilmour/i, result: FLOYD },
];

/** A run result for any source: a fixture that matches, otherwise one picked by the text. */
export function demoRun(source: string): RunResult {
  const hit = FIXTURES.find((f) => f.match.test(source));
  if (hit) return structuredClone(hit.result);
  const pick = FIXTURES[[...source].reduce((a, c) => a + c.charCodeAt(0), 0) % FIXTURES.length].result;
  const title = source.replace(/^ytsearch\d*:/, "").trim() || "Demo şarkı";
  return { ...structuredClone(pick), track_id: "file_demo", title, artist: "" };
}

/** `calibrate --json` result: the song's measurement vs a take that is close but a little dark. */
export function demoCalibration(role: string, round: number, patch: string, amp: string, slot: string | null) {
  // each round gets closer, as if the player turned PRESENCE / MIDDLE up on the unit
  const k = Math.max(0.15, 1 - round * 0.35);
  const diff = { drive: +(0.06 * k).toFixed(3), mid_scoop_db: +(-2.6 * k).toFixed(1), presence_db: +(-3.9 * k).toFixed(1),
    body_db: +(1.2 * k).toFixed(1), fizz_db: +(-0.8 * k).toFixed(1), low_depth_db: +(2.4 * k).toFixed(1) };
  const song = { drive: 0.62, mid_scoop_db: -1.8, presence_db: 2.4, body_db: 0.6, fizz_db: -1.2, low_depth_db: -0.4 };
  const values = Object.fromEntries(Object.entries(song).map(([key, v]) => [key, [v, +(v + diff[key as keyof typeof diff]).toFixed(key === "drive" ? 3 : 1)]]));
  const BANDS = ["63Hz", "80Hz", "100Hz", "125Hz", "160Hz", "200Hz", "250Hz", "315Hz", "400Hz", "500Hz", "630Hz", "800Hz", "1kHz",
    "1.25kHz", "1.6kHz", "2kHz", "2.5kHz", "3.15kHz", "4kHz", "5kHz", "6.3kHz", "8kHz"];
  const shape = [4.2, 3.6, 3.1, 2.4, 1.6, 1.2, 0.9, 0.4, -0.6, -1.4, -2.2, -2.6, -2.1, -1.6, -1.9, -3.2, -4.1, -4.4, -3.6, -1.8, -1.0, -0.6];
  const third_oct_diff = Object.fromEntries(BANDS.map((b, i) => [b, +(shape[i] * k).toFixed(1)]));
  const core = BANDS.slice(4).map((b) => third_oct_diff[b]);
  const dist = +Math.sqrt(core.reduce((a, v) => a + v * v, 0) / core.length).toFixed(2);
  const DEAD: Record<string, number> = { drive: 0.05, mid_scoop_db: 1.5, presence_db: 1.5, body_db: 1.5, fizz_db: 1.5, low_depth_db: 2 };
  const WORDS: Record<string, [string, string, string]> = {
    drive: ["daha az distorsiyonlu", "daha çok distorsiyonlu", "GAIN"],
    mid_scoop_db: ["ortalar daha oyuk", "ortalar daha önde", "MIDDLE"],
    presence_db: ["daha az ısırık/parlaklık (2-4.5 kHz)", "daha çok ısırık/parlaklık (2-4.5 kHz)", "TREBLE / PRESENCE"],
    body_db: ["alt-orta gövde daha ince", "alt-orta gövde daha kalın", "BASS / MASTER EQ low-mid"],
    fizz_db: ["üst tizler (5-8 kHz) daha karanlık", "üst tizler (5-8 kHz) daha cızırtılı", "MASTER EQ high"],
    low_depth_db: ["alt uç daha sıkı", "alt uç daha derin/gevşek", "BASS"],
  };
  const hints = Object.entries(diff).filter(([key, v]) => Math.abs(v) >= DEAD[key])
    .map(([key, v]) => ({ axis: key, value: v, knob: WORDS[key][2], direction: v > 0 ? "down" : "up",
      text: `patch şarkıya göre ${v > 0 ? WORDS[key][1] : WORDS[key][0]} → ${WORDS[key][2]} ${v > 0 ? "↓" : "↑"}`, weight: Math.abs(v) / DEAD[key] }))
    .sort((a, b) => b.weight - a.weight);
  return {
    track_id: "demo", title: "Demo", artist: "", role, ctl_on: false,
    patch: { name: patch, amp, slot }, values,
    fx: { delay_ms: [240, round > 0 ? 240 : 300], reverb: ["room", "room"] },
    compare: { diff, third_oct_diff, spectral_distance_db: dist, hints, close: Object.keys(diff).filter((key) => Math.abs(diff[key as keyof typeof diff]) < DEAD[key]) },
    played_seconds: 19.2, level_db: -14.3, warnings: round === 0 ? ["Demo modu: bu sonuç gerçek bir kayıttan değil, örnek veriden geliyor."] : [],
    wav: `data/tracks/demo/calib/${role}_demo.wav`, device: "IN (GT-1)",
    record: `data/tracks/demo/calib/${role}_demo_${round}.json`,
    // the engine's slopes, damped (calibrate.corrections): mid / presence up, a little less gain
    moves: [
      { field: "preamp_a_middle", label: "MIDDLE", from: 51, to: 51 + Math.round(4.7 * k) },
      { field: "preamp_a_treble", label: "TREBLE", from: 48, to: 48 + Math.round(4.7 * k) },
      { field: "preamp_a_presence", label: "PRESENCE", from: 18, to: 18 + Math.round(3.5 * k) },
      { field: "preamp_a_gain", label: "GAIN", from: 62, to: 62 - Math.round(2.2 * k) },
    ].filter((m) => m.to !== m.from),
    move_notes: [] as string[],
  };
}
