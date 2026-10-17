import * as React from "react";

// 16×16, stroke currentColor 1.6, round caps; no fill (README: Iconography).
const paths = {
  check: <path d="M3.5 8.5l3 3 6-7" />,
  x: <path d="M4 4l8 8M12 4l-8 8" />,
  file: <path d="M4 2h5l3 3v9H4zM9 2v3h3" />,
  minus: <path d="M4 8h8" />,
  plus: <path d="M4 8h8M8 4v8" />,
  chevron: <path d="M4 10l4-4 4 4" />,
  sun: (
    <>
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
    </>
  ),
  moon: <path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" />,
  auto: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor" stroke="none" />
    </>
  ),
};
export type IconName = keyof typeof paths;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg className={`tm-icon ${className}`.trim()} viewBox="0 0 16 16" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

/** The app mark: a knob (accent disc, on-accent ring and pointer). */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10.5" fill="var(--accent)" />
      <circle cx="12" cy="12" r="6.2" fill="none" stroke="var(--on-accent)" strokeWidth="2" />
      <path d="M12 12V3.8" stroke="var(--on-accent)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
