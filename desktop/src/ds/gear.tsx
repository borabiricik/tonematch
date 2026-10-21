import * as React from "react";
import { cx } from "./format";

// Shapes of `tonematch run --json` (@@RESULT, src/tonematch/report.py) and `tonematch gt1 list --json`.
export type Knobs = Record<"gain" | "bass" | "middle" | "treble" | "presence" | "level", number>;
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

// -------------------------------------------------------------------- Knob
const CX = 30, CY = 30, R = 22, A0 = 135, SWEEP = 270;
const pt = (deg: number, r = R) => {
  const t = (deg * Math.PI) / 180;
  return `${(CX + r * Math.cos(t)).toFixed(2)} ${(CY + r * Math.sin(t)).toFixed(2)}`;
};
const arc = (from: number, to: number) => `M ${pt(from)} A ${R} ${R} 0 ${to - from > 180 ? 1 : 0} 1 ${pt(to)}`;

export type KnobProps = { label: string; value: number; changed?: boolean; size?: "sm" | "md"; onPedal?: boolean };
/** A GT-1 knob: 0–100 on a 270° sweep, seven to five o'clock. `changed` marks a value CTL moves. */
export function Knob({ label, value, changed, size = "md", onPedal }: KnobProps) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const end = A0 + (SWEEP * v) / 100;
  return (
    <div className={cx("tm-knob", `tm-knob--${size}`, onPedal && "tm-knob--on-pedal", changed && "is-changed")}
      role="img" aria-label={`${label} ${v}${changed ? ", CTL ile değişir" : ""}`}>
      <svg viewBox="0 0 60 54" aria-hidden="true">
        <path className="tm-knob__track" d={arc(A0, A0 + SWEEP)} />
        {v > 0 && <path className="tm-knob__arc" d={arc(A0, end)} />}
        <circle className="tm-knob__skirt" cx={CX} cy={CY} r="15" />
        <circle className="tm-knob__cap" cx={CX} cy={CY} r="11.5" />
        <path className="tm-knob__pointer" d={`M ${pt(end, 3)} L ${pt(end, 13)}`} />
      </svg>
      <span className="tm-knob__value t-readout">{v}</span>
      <span className="tm-knob__label t-param">{label}</span>
    </div>
  );
}

const ORDER: [keyof Knobs, string][] = [["gain", "Gain"], ["bass", "Bass"], ["middle", "Middle"], ["treble", "Treble"], ["presence", "Presence"], ["level", "Level"]];
/** The six PREAMP knobs in front-panel order; `compareTo` marks the ones CTL moves. */
export function KnobRow({ values, compareTo, size, onPedal }: { values: Knobs; compareTo?: Knobs; size?: "sm" | "md"; onPedal?: boolean }) {
  return (
    <div className="tm-knobs">
      {ORDER.map(([k, label]) => (
        <Knob key={k} label={label} value={values[k]} size={size} onPedal={onPedal} changed={!!compareTo && compareTo[k] !== values[k]} />
      ))}
    </div>
  );
}

// --------------------------------------------------------------------- LCD
/** The patch name as the GT-1's screen shows it (16 characters, uppercase). */
export function Lcd({ children, size = "md" }: { children: React.ReactNode; size?: "md" | "lg" }) {
  return <span className={cx("tm-lcd", `tm-lcd--${size}`, "t-patch-name")}>{children}</span>;
}

// ------------------------------------------------------------- Pedal/Chain
export type BlockKind = "fx1" | "od" | "preamp" | "fx2" | "delay" | "reverb";
const BLOCK_PARAM: Record<BlockKind, string> = { fx1: "FX1", od: "OD/DS", preamp: "PREAMP", fx2: "FX2", delay: "DELAY", reverb: "REVERB" };

export type PedalProps = {
  kind: BlockKind;
  /** the block's type on the unit (T-SCREAM, PLATE …); null = bypassed */
  type: string | null;
  detail?: React.ReactNode;
  /** CTL turns this block's settings to something else */
  changed?: boolean;
  children?: React.ReactNode;
};
/** One GT-1 block as an effect pedal: enclosure color by block, LED lit when on, dimmed when bypassed. */
export function Pedal({ kind, type, detail, changed, children }: PedalProps) {
  const on = type !== null;
  return (
    <div className={cx("tm-pedal", `tm-pedal--${kind}`, !on && "is-off", changed && "is-changed")}
      role="group" aria-label={`${BLOCK_PARAM[kind]}: ${on ? type : "kapalı"}${detail ? `, ${typeof detail === "string" ? detail : ""}` : ""}`}>
      <div className="tm-pedal__top">
        <span className="tm-pedal__param t-param">{BLOCK_PARAM[kind]}</span>
        <span className={cx("tm-led", on && "tm-led--pedal")} aria-hidden="true" />
      </div>
      <div className="tm-pedal__type">{on ? type : "Kapalı"}</div>
      {on && detail && <div className="tm-pedal__detail t-readout">{detail}</div>}
      {children}
    </div>
  );
}

/** A tone as a chain of pedals, in the GT-1's usual order. Bypassed blocks stay as a dim outline. */
export function SignalChain({ tone, compareTo }: { tone: Tone; compareTo?: Tone }) {
  const fx = (slot: string, t: Tone | undefined) => t?.fx.find((f) => f.slot === slot) ?? null;
  const diff = (slot: string) => {
    if (!compareTo) return false;
    const a = fx(slot, tone), b = fx(slot, compareTo);
    return (a?.name ?? null) !== (b?.name ?? null) || (a?.detail ?? "") !== (b?.detail ?? "");
  };
  const f1 = fx("FX1", tone), f2 = fx("FX2", tone), dl = fx("DELAY", tone), rv = fx("REVERB", tone);
  const odChanged = !!compareTo && (tone.od?.type ?? null) !== (compareTo.od?.type ?? null);
  const ampChanged = !!compareTo && tone.amp !== compareTo.amp;
  return (
    <div className="tm-chain" role="list" aria-label="Sinyal zinciri">
      <div role="listitem" className="tm-chain__io"><span className="t-param">IN</span></div>
      <div role="listitem"><Pedal kind="fx1" type={f1?.name ?? null} detail={f1?.detail || undefined} changed={diff("FX1")} /></div>
      <div role="listitem"><Pedal kind="od" type={tone.od?.type ?? null} detail={tone.od ? `DRIVE ${tone.od.drive}` : undefined} changed={odChanged} /></div>
      <div role="listitem" className="tm-chain__amp">
        <Pedal kind="preamp" type={tone.amp} changed={ampChanged}>
          <KnobRow values={tone.knobs} compareTo={compareTo?.knobs} size="sm" onPedal />
        </Pedal>
      </div>
      <div role="listitem"><Pedal kind="fx2" type={f2?.name ?? null} detail={f2?.detail || undefined} changed={diff("FX2")} /></div>
      <div role="listitem"><Pedal kind="delay" type={dl?.name ?? null} detail={dl?.detail || undefined} changed={diff("DELAY")} /></div>
      <div role="listitem"><Pedal kind="reverb" type={rv?.name ?? null} detail={rv?.detail || undefined} changed={diff("REVERB")} /></div>
      <div role="listitem" className="tm-chain__io"><span className="t-param">OUT</span></div>
    </div>
  );
}

// ----------------------------------------------------------------- Slots
export type SlotGridProps = {
  slots: SlotInfo[] | null;          // null = still reading
  target?: string;
  current?: string;
  selected?: string;
  /** names matching this filter stay lit, the rest dim */
  filter?: string;
  onPick?: (slot: string) => void;
  /** double-click: act on the slot (the app selects it on the unit) */
  onActivate?: (slot: string) => void;
};
/** The unit's 99 user slots in banks of 10 rows. Target = where the next run writes; current = selected on the unit. */
export function SlotGrid({ slots, target, current, selected, filter, onPick, onActivate }: SlotGridProps) {
  const q = (filter ?? "").trim().toLowerCase();
  if (!slots) {
    return (
      <div className="tm-slots" aria-busy="true" aria-label="Slotlar okunuyor">
        {Array.from({ length: 99 }, (_, i) => (
          <div key={i} className="tm-slot is-loading"><span className="tm-slot__no t-readout">U{String(i + 1).padStart(2, "0")}</span><span className="tm-skel" /></div>
        ))}
      </div>
    );
  }
  return (
    <div className="tm-slots" role="listbox" aria-label="Kullanıcı slotları">
      {slots.map((s) => {
        const name = s.name.trimEnd();
        const match = !q || name.toLowerCase().includes(q) || s.amp.toLowerCase().includes(q) || s.slot.toLowerCase() === q;
        return (
          <button key={s.slot} type="button" role="option" aria-selected={s.slot === selected} onClick={() => onPick?.(s.slot)}
            onDoubleClick={onActivate && (() => onActivate(s.slot))}
            className={cx("tm-slot", s.slot === target && "is-target", s.slot === current && "is-current", s.slot === selected && "is-selected", !match && "is-dim")}
            title={`${s.slot} · ${name || "(boş)"} · ${s.amp} G${s.gain}`}>
            <span className="tm-slot__no t-readout">{s.slot}</span>
            <span className="tm-slot__name">{name || "—"}</span>
            <span className="tm-slot__meta">
              <span>{s.amp}</span>
              {s.dual && <span className="tm-slot__ctl t-param">CTL</span>}
            </span>
            {s.slot === current && <span className="tm-slot__now" aria-label="cihazda seçili"><span className="tm-led tm-led--on" /></span>}
          </button>
        );
      })}
    </div>
  );
}
