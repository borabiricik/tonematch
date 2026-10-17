import * as React from "react";
import { Chip, KnobRow, Timeline, type Knobs } from "./readouts";

// Shapes of `tonematch run --json` (@@RESULT) and `tonematch gt1 list --json`.
export type Tone = {
  role: string; amp: string; drive: string; stereo: string;
  knobs: Knobs;
  od: { type: string; drive: number; level: number } | null;
  fx: { slot: string; name: string; detail: string }[];
  segments: number[][];
  claude?: { confidence: "high" | "medium" | "low"; why: string } | null;
};
export type PatchResult = { group: string; name: string; slot: string | null; dual: boolean; assigns: string[]; tones: Tone[] };
export type RunResult = {
  track_id: string; title: string; artist: string; duration: number; tempo: number;
  tuning: { name: string; user_tuning: string; semitones: number; evidence?: { source?: string } } | null;
  patches: PatchResult[]; tsl: string; backup: string | null;
  claude?: { enabled: boolean; ok: boolean; model: string; backend: string; song?: string; rig_notes?: string; error?: string } | null;
};
export type SlotInfo = { slot: string; name: string; amp: string; gain: number; dual?: boolean };

const ROLE: Record<string, string> = { rhythm: "Ritim", lead: "Solo", clean: "Temiz", crunch: "Crunch" };
export const roleName = (r: string) => ROLE[r] ?? r;
const CONF: Record<string, string> = { high: "emin", medium: "kısmen emin", low: "tahmin" };
const DRIVE: Record<string, string> = { clean: "temiz", crunch: "crunch", high_gain: "yüksek gain" };

function ToneBlock({ tone, duration, ctl, other }: { tone: Tone; duration: number; ctl?: "off" | "on"; other?: Tone }) {
  return (
    <div className="tm-tone">
      <div className="tm-tone__head">
        <span className="tm-label">{ctl ? `CTL ${ctl === "off" ? "kapalı" : "açık"}` : "Ton"} · {roleName(tone.role)}</span>
        <span className="tm-field__hint">{DRIVE[tone.drive] ?? tone.drive}</span>
      </div>
      <div className="tm-tone__amp">
        <span className="tm-tone__amp-name">{tone.amp}</span>
        {tone.claude && <Chip keyLabel="CLAUDE" detail={CONF[tone.claude.confidence]}>önerisi</Chip>}
      </div>
      {tone.claude && <p className="tm-tone__note">{tone.claude.why}</p>}
      <KnobRow values={tone.knobs} compareTo={other?.knobs} />
      {(tone.od || tone.fx.length > 0) && (
        <div className="tm-chips">
          {tone.od && <Chip tone="accent" keyLabel="OD/DS" detail={`d${tone.od.drive}`}>{tone.od.type}</Chip>}
          {tone.fx.map((f) => <Chip key={f.slot} keyLabel={f.slot} detail={f.detail}>{f.name}</Chip>)}
        </div>
      )}
      <Timeline duration={duration} segments={tone.segments} alt={ctl === "on"} />
    </div>
  );
}

export type PatchCardProps = { patch: PatchResult; duration: number };
/** One patch the engine built: slot, name readout, one column per tone (two for a CTL patch). */
export function PatchCard({ patch: p, duration }: PatchCardProps) {
  const onDevice = !!p.slot?.startsWith("U");
  const [a, b] = p.tones;
  return (
    <article className="tm-patch">
      <header className="tm-patch__head">
        <span className={`tm-patch__slot${onDevice ? "" : " tm-patch__slot--none"}`}>{onDevice ? p.slot : "—"}</span>
        <div className="tm-patch__meta">
          <span className="tm-patch__lcd">{p.name}</span>
          <span className="tm-field__hint">
            {p.dual ? `İki ton tek patch'te: CTL'ye basınca ${roleName(b.role).toLowerCase()} tona geçer` : `${roleName(a.role)} tonu`}
          </span>
        </div>
        {onDevice ? <Chip tone="ok">Cihaza yazıldı</Chip>
          : p.slot ? <Chip tone="warn">Edit buffer'da, kaydedilmedi</Chip>
            : <Chip icon="file">Sadece dosya</Chip>}
      </header>
      <div className={`tm-patch__tones${p.dual ? " tm-patch__tones--dual" : ""}`}>
        {p.dual
          ? <><ToneBlock tone={a} duration={duration} ctl="off" other={b} /><ToneBlock tone={b} duration={duration} ctl="on" other={a} /></>
          : <ToneBlock tone={a} duration={duration} />}
      </div>
    </article>
  );
}

export type SlotGridProps = {
  slots: SlotInfo[] | null;          // null = still reading
  target?: string;
  current?: string;
  onPick?: (slot: string) => void;
};
/** All 99 user slots. Target = where the next run writes; current = selected on the unit. */
export function SlotGrid({ slots, target, current, onPick }: SlotGridProps) {
  if (!slots) {
    return (
      <div className="tm-slots" aria-busy="true">
        {Array.from({ length: 99 }, (_, i) => (
          <div key={i} className="tm-slot tm-slot--loading">
            <span className="tm-slot__no">U{String(i + 1).padStart(2, "0")}</span>
            <span className="tm-slot__name"> </span>
            <span className="tm-slot__amp">&nbsp;</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="tm-slots">
      {slots.map((s) => (
        <button key={s.slot} type="button" onClick={() => onPick?.(s.slot)} title={`${s.name.trim()} · ${s.amp} G${s.gain}`}
          className={`tm-slot${s.slot === target ? " tm-slot--target" : ""}${s.slot === current ? " tm-slot--current" : ""}`}>
          <span className="tm-slot__no">{s.slot}</span>
          <span className="tm-slot__name">{s.name.trimEnd() || " "}</span>
          <span className="tm-slot__amp">{s.amp}{s.dual ? " · CTL" : ""}</span>
        </button>
      ))}
    </div>
  );
}
