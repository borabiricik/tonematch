import * as React from "react";
import { cx, mmss, signed } from "./format";
import { Icon } from "./icons";

// ---------------------------------------------------------------- Pipeline
export type Stage = { name: string; state: "pending" | "active" | "done" | "error"; time?: string; note?: string };
/** The run's real stages as a cable between jacks: the cable fills up to the active stage. */
export function Pipeline({ stages }: { stages: Stage[] }) {
  const lastDone = stages.reduce((n, s, i) => (s.state === "done" ? i : n), -1);
  const active = stages.findIndex((s) => s.state === "active");
  const reach = active >= 0 ? active : lastDone;
  const pct = stages.length > 1 ? (Math.max(0, reach) / (stages.length - 1)) * 100 : 0;
  return (
    <ol className="tm-pipe" style={{ "--fill": `${pct}%`, "--n": stages.length } as React.CSSProperties}>
      <span className="tm-pipe__cable" aria-hidden="true"><span className="tm-pipe__cable-fill" /></span>
      {stages.map((s) => (
        <li key={s.name} className={cx("tm-pipe__stage", `is-${s.state}`)} aria-current={s.state === "active" ? "step" : undefined}>
          <span className="tm-pipe__jack" aria-hidden="true">
            {s.state === "done" ? <Icon name="check" /> : s.state === "error" ? <Icon name="x" /> : null}
          </span>
          <span className="tm-pipe__name">{s.name}</span>
          <span className="tm-pipe__time t-readout">{s.time ?? (s.state === "pending" ? "—" : "")}</span>
          {s.note && <span className="tm-pipe__note t-small">{s.note}</span>}
        </li>
      ))}
    </ol>
  );
}

// ----------------------------------------------------------------- SongMap
export type Lane = { label: string; segments: number[][]; tone?: "song" | "you" };
/** Where in the song each tone plays: one lane per tone, minute ticks, optional highlighted range. */
export function SongMap({ duration, lanes, highlight }: { duration: number; lanes: Lane[]; highlight?: number[][] }) {
  const d = Math.max(duration, 1);
  const ticks = Array.from({ length: Math.floor(d / 60) + 1 }, (_, i) => i * 60).filter((t) => t > 0 && t < d - 8);
  // tick labels too close to the 0:00 / end labels would collide in narrow panels
  const labelled = ticks.filter((t) => t > d * 0.16 && t < d * 0.84);
  const pos = (t: number) => `${(100 * t) / d}%`;
  return (
    <div className="tm-songmap">
      {lanes.map((l) => (
        <div key={l.label} className="tm-songmap__lane">
          <span className="tm-songmap__label t-small">{l.label}</span>
          <div className="tm-songmap__track" role="img"
            aria-label={`${l.label}: ${l.segments.map(([a, b]) => `${mmss(a)}–${mmss(b)}`).join(", ") || "yok"}`}>
            {ticks.map((t) => <span key={t} className="tm-songmap__tick" style={{ left: pos(t) }} />)}
            {highlight?.map(([a, b], i) => <span key={`h${i}`} className="tm-songmap__hl" style={{ left: pos(a), width: pos(b - a) }} />)}
            {l.segments.map(([a, b], i) => (
              <span key={i} className={cx("tm-songmap__seg", `is-${l.tone ?? "song"}`)}
                style={{ left: pos(a), width: `max(3px, ${(100 * (b - a)) / d}%)` }} title={`${mmss(a)}–${mmss(b)}`} />
            ))}
          </div>
        </div>
      ))}
      <div className="tm-songmap__scale t-readout">
        <span>0:00</span>
        {labelled.map((t) => <span key={t} style={{ left: pos(t) }}>{mmss(t)}</span>)}
        <span>{mmss(d)}</span>
      </div>
    </div>
  );
}

// -------------------------------------------------------------- LevelMeter
const dbPct = (db: number) => Math.max(0, Math.min(100, ((db + 60) / 60) * 100));
/** Input level in dBFS (−60…0) as an LED ladder with a peak-hold mark. */
export function LevelMeter({ db, peak, size = "md" }: { db: number; peak?: number; size?: "md" | "lg" }) {
  const hot = db > -3;
  return (
    <div className={cx("tm-level", `tm-level--${size}`)}>
      <div className="tm-level__bar" role="meter" aria-label="Giriş seviyesi" aria-valuemin={-60} aria-valuemax={0}
        aria-valuenow={Math.round(db)} aria-valuetext={`${Math.round(db)} dBFS`}>
        <div className={cx("tm-level__fill", hot && "is-hot")} style={{ "--w": `${dbPct(db)}%` } as React.CSSProperties} />
        {peak !== undefined && <div className="tm-level__peak" style={{ left: `${dbPct(peak)}%` }} />}
      </div>
      <div className="tm-level__scale t-readout" aria-hidden="true">
        {[-60, -48, -36, -24, -12, -6, 0].map((v) => <span key={v} style={{ left: `${dbPct(v)}%` }}>{v === 0 ? "0" : `−${-v}`}</span>)}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- CentsMeter
export type TunerReading = { note: string | null; cents: number; in_tune: boolean };
export const tunerTone = (r: TunerReading | null) => (!r || r.note === null ? "idle" : r.in_tune ? "ok" : Math.abs(r.cents) <= 15 ? "near" : "far");
/** −50…+50 cents: a needle, the ±3 cent window, ticks every 10. */
export function CentsMeter({ reading }: { reading: TunerReading | null }) {
  const has = !!reading && reading.note !== null;
  const c = has ? Math.max(-50, Math.min(50, reading!.cents)) : 0;
  return (
    <div className="tm-cents" data-tone={tunerTone(reading)}>
      <div className="tm-cents__track" role="meter" aria-label="Sapma" aria-valuemin={-50} aria-valuemax={50}
        aria-valuenow={has ? c : 0} aria-valuetext={has ? `${signed(c)} cent` : "sinyal yok"}>
        <span className="tm-cents__zone" />
        {Array.from({ length: 11 }, (_, i) => i * 10 - 50).map((v) => (
          <span key={v} className={cx("tm-cents__tick", v % 50 === 0 && "is-major", v === 0 && "is-center")} style={{ left: `${v + 50}%` }} />
        ))}
        {has && <span className="tm-cents__needle" style={{ left: `${c + 50}%` }} />}
      </div>
      <div className="tm-cents__scale t-readout" aria-hidden="true"><span>♭ −50</span><span>0</span><span>+50 ♯</span></div>
    </div>
  );
}

/** One string of the polyphonic tuner: a vertical meter, note and cents under it. */
export function StringMeter({ n, reading, target }: { n: number; reading: TunerReading | null; target?: string }) {
  const has = !!reading && reading.note !== null;
  // BTS snaps ±5 cents to the center line on the poly meter
  const pos = has ? (Math.abs(reading!.cents) <= 5 ? 0 : Math.max(-50, Math.min(50, reading!.cents))) : 0;
  return (
    <div className="tm-string" data-tone={tunerTone(reading)}>
      <div className="tm-string__bar" role="meter" aria-label={`${n}. tel`} aria-valuemin={-50} aria-valuemax={50} aria-valuenow={has ? reading!.cents : 0}>
        <span className="tm-string__center" />
        {has && <span className="tm-string__mark" style={{ bottom: `${pos + 50}%` }} />}
      </div>
      <div className="tm-string__note">{has ? reading!.note : (target ?? "—")}</div>
      <div className="tm-string__cents t-readout">{has ? signed(reading!.cents) : "·"}</div>
      <div className="tm-string__n t-small">{n}. tel</div>
    </div>
  );
}

// ------------------------------------------------------------- AxisCompare
export type AxisRow = { key: string; label: string; hint: string; song: number; you: number; close: boolean; unit: "db" | "ratio" };
/** Song vs your playing on each measured axis: two marks on a shared scale, the gap between them shaded. */
export function AxisCompare({ rows }: { rows: AxisRow[] }) {
  return (
    <div className="tm-axes" role="table" aria-label="Şarkı ve senin çalımın, eksen eksen">
      <div className="tm-axes__legend" role="row">
        <span role="columnheader" className="t-small">Eksen</span>
        <span role="columnheader" className="tm-axes__keys t-small">
          <span><i className="is-song" /> Şarkı</span><span><i className="is-you" /> Sen</span>
        </span>
        <span role="columnheader" className="t-small tm-axes__diffhead">Fark</span>
      </div>
      {rows.map((r) => {
        const [lo, hi] = r.unit === "ratio" ? [0, 1] : [-12, 12];
        const p = (v: number) => Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));
        const a = p(r.song), b = p(r.you);
        const fmt = (v: number) => (r.unit === "ratio" ? v.toFixed(2) : `${signed(v, 1)}`);
        const diff = r.you - r.song;
        return (
          <div key={r.key} className={cx("tm-axes__row", r.close ? "is-close" : "is-off")} role="row">
            <span role="rowheader" className="tm-axes__label">
              <span className="t-heading">{r.label}</span>
              <span className="t-small">{r.hint}</span>
            </span>
            <span role="cell" className="tm-axes__plot" aria-label={`Şarkı ${fmt(r.song)}, sen ${fmt(r.you)}`}>
              {r.unit === "db" && <span className="tm-axes__zero" />}
              <span className="tm-axes__gap" style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(a - b)}%` }} />
              <span className="tm-axes__dot is-song" style={{ left: `${a}%` }} />
              <span className="tm-axes__dot is-you" style={{ left: `${b}%` }} />
            </span>
            <span role="cell" className="tm-axes__diff">
              <span className="t-readout">{r.unit === "ratio" ? signed(diff, 2) : `${signed(diff, 1)} dB`}</span>
              <span className={cx("tm-axes__tag", r.close ? "is-ok" : "is-off")}>{r.close ? "yakın" : "farklı"}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- BandDiff
/** Patch minus song per 1/3-octave band (dB): bars up = your patch is louder there. `ignored` bands are drawn hatched. */
export function BandDiff({ bands, ignored = [], range = 8 }: { bands: Record<string, number>; ignored?: string[]; range?: number }) {
  const entries = Object.entries(bands);
  const label = (b: string) => b.replace("kHz", "k").replace("Hz", "");
  return (
    <figure className="tm-bands">
      <div className="tm-bands__plot" role="img"
        aria-label={`Bant bant fark: ${entries.map(([b, v]) => `${b} ${signed(v, 1)} dB`).join(", ")}`}>
        <span className="tm-bands__axis t-readout" style={{ top: 0 }}>+{range}</span>
        <span className="tm-bands__axis t-readout" style={{ top: "50%" }}>0</span>
        <span className="tm-bands__axis t-readout" style={{ bottom: 0 }}>−{range}</span>
        <span className="tm-bands__zero" />
        {entries.map(([b, v]) => {
          const h = Math.min(50, (Math.abs(v) / range) * 50);
          return (
            <span key={b} className={cx("tm-bands__col", ignored.includes(b) && "is-ignored")} title={`${b}: ${signed(v, 1)} dB`}>
              <span className={cx("tm-bands__bar", v >= 0 ? "is-up" : "is-down")}
                style={v >= 0 ? { bottom: "50%", height: `${h}%` } : { top: "50%", height: `${h}%` }} />
            </span>
          );
        })}
      </div>
      <div className="tm-bands__labels t-readout" aria-hidden="true">
        {entries.map(([b], i) => <span key={b}>{i % 2 === 0 ? label(b) : ""}</span>)}
      </div>
    </figure>
  );
}

// --------------------------------------------------------------- Sparkline
/** A short series, the last point marked. Default: bigger values lower (calibration distance: lower is closer);
 *  rising: bigger values higher (tempo, minutes, accuracy). */
export function Sparkline({ values, width = 120, height = 32, label, rising }: { values: number[]; width?: number; height?: number; label: string; rising?: boolean }) {
  if (values.length === 0) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const span = Math.max(max - min, 0.5);
  const x = (i: number) => (values.length === 1 ? width / 2 : 4 + (i * (width - 8)) / (values.length - 1));
  const y = (v: number) => 4 + ((rising ? max - v : v - min) / span) * (height - 8);
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className="tm-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <path d={d} />
      {values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={i === values.length - 1 ? 3.2 : 2} className={i === values.length - 1 ? "is-last" : undefined} />)}
    </svg>
  );
}
