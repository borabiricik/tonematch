import * as React from "react";
import { cx } from "../../ds";
import type { NoteStatus, TabNote } from "./types";

// Tablature of one loop of an exercise (SVG). String 1 (high E) on top, a bar line every 4 beats.
// Notes take the colour of their verdict in the current loop (the previous loop's stays faint until replaced);
// the cursor is moved by requestAnimationFrame from `clock` (no React render per frame).

export type TabClock = { beat: number; at: number; beatMs: number; loopBeats: number; running: boolean };

const STRING_GAP = 22;
const TOP = 30;
const LEFT = 30;
const STRING_NAMES = ["e", "B", "G", "D", "A", "E"];

type Props = {
  notes: TabNote[]; beats: number; perBeat: number;
  status?: Record<number, NoteStatus>; previous?: Record<number, NoteStatus>; trouble?: number[];
  clock?: React.MutableRefObject<TabClock>;
};

export function Tab({ notes, beats, perBeat, status = {}, previous = {}, trouble = [], clock }: Props) {
  const ppb = Math.max(72, perBeat * 30);
  const width = LEFT + beats * ppb + 24;
  const height = TOP + STRING_GAP * 5 + 24;
  const x = (beat: number) => LEFT + 12 + beat * ppb;
  const y = (s: number) => TOP + (s - 1) * STRING_GAP;
  const cursor = React.useRef<SVGLineElement>(null);
  const scroller = React.useRef<HTMLDivElement>(null);
  const bad = new Set(trouble);

  React.useEffect(() => {
    if (!clock) return;
    let raf = 0;
    const tick = () => {
      const c = clock.current;
      const el = cursor.current;
      if (el) {
        const into = c.running ? Math.min(1, (performance.now() - c.at) / c.beatMs) : 0;
        const abs = c.beat + into;
        const show = c.running && abs >= 0;
        const b = ((abs % c.loopBeats) + c.loopBeats) % c.loopBeats;
        el.style.opacity = show ? "1" : "0";
        el.setAttribute("transform", `translate(${x(b) - x(0)} 0)`);
        const sc = scroller.current;
        if (sc && show) {
          const px = x(b);
          if (px > sc.scrollLeft + sc.clientWidth * 0.7) sc.scrollLeft = px - sc.clientWidth * 0.3;
          else if (px < sc.scrollLeft) sc.scrollLeft = Math.max(0, px - 40);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [clock, ppb]);

  return (
    <div className="tab" ref={scroller}>
      <svg width={width} height={height} role="img" aria-label="Tab">
        {/* beats and bars */}
        {Array.from({ length: beats + 1 }, (_, b) => (
          <g key={b}>
            <line className={b % 4 === 0 || b === beats ? "tab__bar" : "tab__beat"} x1={x(b) - 12} x2={x(b) - 12}
              y1={y(1)} y2={y(6)} />
            {b < beats && <text className="tab__count" x={x(b)} y={TOP - 16} textAnchor="middle">{(b % 4) + 1}</text>}
          </g>
        ))}
        {STRING_NAMES.map((n, i) => (
          <g key={n + i}>
            <line className="tab__string" x1={LEFT} x2={width - 8} y1={y(i + 1)} y2={y(i + 1)} />
            <text className="tab__name" x={LEFT - 14} y={y(i + 1) + 4} textAnchor="middle">{n}</text>
          </g>
        ))}
        {notes.map((n, j) => {
          const st = status[j] ?? previous[j];
          const faded = status[j] === undefined && previous[j] !== undefined;
          const label = `${n.fret}${n.tech === "b" ? "b" : ""}`;
          const w = 10 + label.length * 8;
          return (
            <g key={j} className={cx("tab__note", st && `is-${st}`, faded && "is-faded", bad.has(j) && "is-trouble")}
              transform={`translate(${x(n.beat)} ${y(n.string)})`}>
              <rect x={-w / 2} y={-9} width={w} height={18} rx={5} />
              <text y={4.5} textAnchor="middle">{label}</text>
              {(n.tech === "h" || n.tech === "p") && <text className="tab__tech" y={-13} textAnchor="middle">{n.tech}</text>}
              {(n.tech === "d" || n.tech === "u") && <text className="tab__tech" y={-13} textAnchor="middle">{n.tech === "d" ? "↓" : "↑"}</text>}
            </g>
          );
        })}
        <line ref={cursor} className="tab__cursor" x1={x(0)} x2={x(0)} y1={TOP - 22} y2={y(6) + 12} style={{ opacity: 0 }} />
      </svg>
    </div>
  );
}

/** A fretboard diagram of the positions an exercise (or an answer) uses; roots filled. */
export function Fretboard({ notes, root, active, highlightString, compact }: {
  notes: { string: number; fret: number; midi: number }[]; root?: number | null; active?: { string: number; fret: number } | null;
  highlightString?: number; compact?: boolean;
}) {
  const frets = notes.map((n) => n.fret);
  const lo = notes.length ? Math.max(0, Math.min(...frets) - 1) : 0;
  const hi = notes.length ? Math.max(lo + 5, Math.max(...frets) + 1) : 12;
  const fw = compact ? 30 : 38;
  const sg = compact ? 14 : 18;
  const left = 24;
  const top = 14;
  const width = left + (hi - lo) * fw + 16;
  const height = top + sg * 5 + 26;
  const fx = (f: number) => (f === 0 ? left - 10 : left + (f - lo - 0.5) * fw);
  const sy = (s: number) => top + (s - 1) * sg;
  const seen = new Set<string>();
  const dots = notes.filter((n) => { const k = `${n.string}:${n.fret}`; if (seen.has(k)) return false; seen.add(k); return true; });
  return (
    <svg className="fretboard" width={width} height={height} role="img" aria-label="Klavye şeması">
      {[1, 2, 3, 4, 5, 6].map((s) => (
        <line key={s} className={cx("fretboard__string", highlightString === s && "is-on")} x1={left} x2={width - 8} y1={sy(s)} y2={sy(s)} />
      ))}
      {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map((f) => (
        <g key={f}>
          <line className={f === 0 ? "fretboard__nut" : "fretboard__fret"} x1={left + (f - lo) * fw} x2={left + (f - lo) * fw} y1={sy(1)} y2={sy(6)} />
          {f > lo && [3, 5, 7, 9, 12, 15, 17, 19, 21].includes(f) && (
            <text className="fretboard__num" x={left + (f - lo - 0.5) * fw} y={sy(6) + 18} textAnchor="middle">{f}</text>
          )}
        </g>
      ))}
      {dots.map((n) => {
        const isRoot = root !== undefined && root !== null && n.midi % 12 === root;
        const on = active && active.string === n.string && active.fret === n.fret;
        return (
          <circle key={`${n.string}:${n.fret}`} className={cx("fretboard__dot", isRoot && "is-root", on && "is-active")}
            cx={fx(n.fret)} cy={sy(n.string)} r={compact ? 5.5 : 7} />
        );
      })}
    </svg>
  );
}
