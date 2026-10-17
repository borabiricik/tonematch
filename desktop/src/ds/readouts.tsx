import * as React from "react";
import { Led } from "./feedback";
import { Icon } from "./icons";

// -------------------------------------------------------------------- Knob
const CX = 26, CY = 26, R = 19, A0 = 135, SWEEP = 270;
const pt = (deg: number, r = R) => {
  const t = (deg * Math.PI) / 180;
  return `${(CX + r * Math.cos(t)).toFixed(2)} ${(CY + r * Math.sin(t)).toFixed(2)}`;
};
const arc = (from: number, to: number) => `M ${pt(from)} A ${R} ${R} 0 ${to - from > 180 ? 1 : 0} 1 ${pt(to)}`;

export type KnobProps = { label: string; value: number; changed?: boolean };
/** A GT-1 knob: 0–100 on a 270° sweep from seven to five o'clock. */
export function Knob({ label, value, changed }: KnobProps) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const end = A0 + (SWEEP * v) / 100;
  return (
    <div className="tm-knob" title={`${label} ${v}`}>
      <svg viewBox="0 0 52 46" aria-hidden="true">
        <path className="tm-knob__track-edge" d={arc(A0, A0 + SWEEP)} />
        <path className="tm-knob__track" d={arc(A0, A0 + SWEEP)} />
        {v > 0 && <path className="tm-knob__arc" d={arc(A0, end)} />}
        <circle className="tm-knob__cap" cx={CX} cy={CY} r="11" />
        <path className="tm-knob__pointer" d={`M ${pt(end, 4)} L ${pt(end, 9.5)}`} />
      </svg>
      <span className={`tm-knob__value${changed ? " tm-knob__value--changed" : ""}`}>{v}</span>
      <span className="tm-label">{label}</span>
    </div>
  );
}

export type Knobs = Record<"gain" | "bass" | "middle" | "treble" | "presence" | "level", number>;
const ORDER: [keyof Knobs, string][] = [["gain", "Gain"], ["bass", "Bass"], ["middle", "Middle"], ["treble", "Treble"], ["presence", "Presence"], ["level", "Level"]];
/** The six preamp knobs in front-panel order; `compareTo` marks values that differ (CTL patches). */
export function KnobRow({ values, compareTo }: { values: Knobs; compareTo?: Knobs }) {
  return (
    <div className="tm-knobs">
      {ORDER.map(([k, label]) => <Knob key={k} label={label} value={values[k]} changed={!!compareTo && compareTo[k] !== values[k]} />)}
    </div>
  );
}

// ---------------------------------------------------------------- Timeline
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export type TimelineProps = { duration: number; segments: number[][]; alt?: boolean };
/** Where in the song a tone plays. */
export function Timeline({ duration, segments, alt }: TimelineProps) {
  const d = Math.max(duration, 1);
  return (
    <div className="tm-tone__where">
      <div className="tm-timeline" role="img" aria-label={segments.map(([a, b]) => `${mmss(a)}–${mmss(b)}`).join(", ")}>
        {segments.map(([a, b], i) => (
          <span key={i} className={`tm-timeline__seg${alt ? " tm-timeline__seg--alt" : ""}`}
            style={{ left: `${(100 * a) / d}%`, width: `${Math.max(0.6, (100 * (b - a)) / d)}%` }} />
        ))}
      </div>
      <div className="tm-timeline-scale"><span>0:00</span><span>{mmss(d)}</span></div>
    </div>
  );
}

// -------------------------------------------------------------------- Chip
export type ChipProps = {
  keyLabel?: string;
  detail?: React.ReactNode;
  tone?: "default" | "accent" | "ok" | "warn" | "err";
  icon?: "file";
  children: React.ReactNode;
};
/** One active block of a patch (OD/DS, FX1, DELAY …) or a state with an LED. */
export function Chip({ keyLabel, detail, tone = "default", icon, children }: ChipProps) {
  const state = tone === "ok" || tone === "warn" || tone === "err";
  return (
    <span className={`tm-chip${tone === "default" ? "" : ` tm-chip--${tone}`}`}>
      {state && <Led state={tone} />}
      {icon && <Icon name={icon} />}
      {keyLabel && <span className="tm-chip__key">{keyLabel}</span>}
      {children}
      {detail !== undefined && detail !== "" && <span className="tm-chip__detail">{detail}</span>}
    </span>
  );
}
