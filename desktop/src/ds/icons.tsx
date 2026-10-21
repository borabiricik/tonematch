import * as React from "react";

// 16×16 grid, stroke currentColor 1.5, round caps and joins, no fill (design/README.md: Iconography).
const paths = {
  check: <path d="M3.5 8.5l3 3 6-7" />,
  x: <path d="M4 4l8 8M12 4l-8 8" />,
  plus: <path d="M3.5 8h9M8 3.5v9" />,
  minus: <path d="M3.5 8h9" />,
  "chevron-down": <path d="M4 6l4 4 4-4" />,
  "chevron-up": <path d="M4 10l4-4 4 4" />,
  "chevron-right": <path d="M6 4l4 4-4 4" />,
  "chevron-left": <path d="M10 4L6 8l4 4" />,
  "arrow-right": <path d="M3 8h10M9 4l4 4-4 4" />,
  search: <><circle cx="7" cy="7" r="4.25" /><path d="M10.2 10.2L13.5 13.5" /></>,
  // a waveform turning into a step: the "match a tone" view
  wave: <path d="M1.5 8h1.5l1.5-4 2 8 2-6 1.5 4 1-2h3.5" />,
  library: <><path d="M3 2.5v11M6 2.5v11" /><path d="M9 3.2l3.2-.9 2.3 10.8-3.2.9z" /></>,
  // the GT-1 seen from above: two footswitches, a screen
  device: <><rect x="1.75" y="3.5" width="12.5" height="9" rx="1.5" /><path d="M4.5 6.5h3" /><circle cx="5" cy="10" r="0.9" /><circle cx="11" cy="10" r="0.9" /><path d="M10 6.5h1.5" /></>,
  tuner: <><path d="M2.5 11.5a5.5 5.5 0 0 1 11 0" /><path d="M8 11.5l2.5-4" /><path d="M8 4.2v1.2M3.9 6l.9.8M12.1 6l-.9.8" /></>,
  settings: <><path d="M2.5 4.5h6M11.5 4.5h2M2.5 11.5h2M7.5 11.5h6" /><circle cx="10" cy="4.5" r="1.5" /><circle cx="6" cy="11.5" r="1.5" /></>,
  terminal: <><rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.5" /><path d="M4.5 6.5l2 1.5-2 1.5M8.5 10h3" /></>,
  refresh: <><path d="M13 8a5 5 0 1 1-1.5-3.55" /><path d="M13 2.5v2.5h-2.5" /></>,
  backup: <><rect x="2" y="2.75" width="12" height="3.5" rx="1" /><path d="M3 6.25v6a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-6M6.5 9h3" /></>,
  folder: <path d="M2 4.25a1 1 0 0 1 1-1h3l1.5 1.5H13a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z" />,
  file: <><path d="M4 1.75h5l3 3v9.5H4z" /><path d="M9 1.75v3h3" /></>,
  external: <><path d="M9.5 2.5h4v4M13.5 2.5L8 8" /><path d="M12 9.5v3a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3" /></>,
  copy: <><rect x="5.25" y="5.25" width="8.5" height="8.5" rx="1.5" /><path d="M10.75 5.25V3.5a1.25 1.25 0 0 0-1.25-1.25H3.5A1.25 1.25 0 0 0 2.25 3.5v6A1.25 1.25 0 0 0 3.5 10.75h1.75" /></>,
  play: <path d="M5 3.25v9.5L12.5 8z" />,
  stop: <rect x="4" y="4" width="8" height="8" rx="1" />,
  record: <circle cx="8" cy="8" r="4.5" />,
  sun: <><circle cx="8" cy="8" r="2.75" /><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></>,
  moon: <path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" />,
  auto: <><circle cx="8" cy="8" r="5.5" /><path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor" stroke="none" /></>,
  info: <><circle cx="8" cy="8" r="6" /><path d="M8 7.25v4M8 4.9v.1" /></>,
  alert: <><path d="M8 2l6.25 11H1.75z" /><path d="M8 6.5v3M8 11.4v.1" /></>,
  // Claude mode: a review mark, not a brand logo
  sparkle: <path d="M8 1.75l1.4 4.85L14.25 8 9.4 9.4 8 14.25 6.6 9.4 1.75 8 6.6 6.6z" />,
  link: <><path d="M6.75 9.25l2.5-2.5" /><path d="M7.5 4.5l1-1a2.47 2.47 0 0 1 3.5 3.5l-1 1M8.5 11.5l-1 1A2.47 2.47 0 0 1 4 9l1-1" /></>,
  clock: <><circle cx="8" cy="8" r="6" /><path d="M8 4.75V8l2.25 1.5" /></>,
  keyboard: <><rect x="1.5" y="4" width="13" height="8" rx="1.5" /><path d="M4 6.75h.1M6.5 6.75h.1M9 6.75h.1M11.5 6.75h.1M5 9.5h6" /></>,
  grid: <><rect x="2" y="2" width="5" height="5" rx="1" /><rect x="9" y="2" width="5" height="5" rx="1" /><rect x="2" y="9" width="5" height="5" rx="1" /><rect x="9" y="9" width="5" height="5" rx="1" /></>,
  footswitch: <><circle cx="8" cy="9" r="3.75" /><path d="M8 5.25V2.5M6 2.5h4" /></>,
  ear: <><path d="M4.5 6a3.5 3.5 0 0 1 7 0c0 2-2 2.5-2 4.5a2 2 0 0 1-3.5 1.3" /><path d="M6.75 6.25a1.25 1.25 0 0 1 2.5 0" /></>,
  history: <><path d="M2.75 8a5.25 5.25 0 1 0 1.6-3.8" /><path d="M2.5 2.75v2.5H5M8 5.25V8l2 1.25" /></>,
  demo: <><rect x="2" y="2.5" width="12" height="11" rx="1.5" /><path d="M5 6l2 2-2 2M8.5 10h2.5" /></>,
  more: <><circle cx="3.5" cy="8" r="0.6" /><circle cx="8" cy="8" r="0.6" /><circle cx="12.5" cy="8" r="0.6" /></>,
};
export type IconName = keyof typeof paths;

const FILLED = new Set<IconName>(["play", "stop", "record"]);

export function Icon({ name, className = "", size }: { name: IconName; className?: string; size?: number }) {
  return (
    <svg className={`tm-icon${FILLED.has(name) ? " tm-icon--fill" : ""} ${className}`.trim()} viewBox="0 0 16 16" aria-hidden="true"
      style={size ? { width: size, height: size } : undefined}>
      {paths[name]}
    </svg>
  );
}

/** The app mark: a cream chicken-head knob on a graphite plate, pointer at two o'clock. */
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="tm-mark">
      <rect x="1" y="1" width="30" height="30" rx="8" fill="var(--primary)" />
      <circle cx="16" cy="17" r="8.5" fill="var(--on-primary)" />
      <path d="M16 17 L22.5 10.5" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" />
      <path d="M6.2 24.5a12 12 0 0 1-1.7-4.3M25.8 24.5a12 12 0 0 0 1.7-4.3" stroke="var(--on-primary)" strokeWidth="1.6"
        strokeLinecap="round" opacity="0.55" />
    </svg>
  );
}
