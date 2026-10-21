import * as React from "react";
import { cx, slotLabel, thumbUrl } from "../ds";
import type { RunRequest } from "./state";

// Small pieces shared by the Match, Result and Library views.

export function RequestFacts({ req }: { req: RunRequest }) {
  return (
    <ul className="facts t-small">
      <li>{req.target === "slot" ? `Hedef ${slotLabel(req.slot)}` : req.target === "listen" ? "Edit buffer" : "Sadece dosya"}</li>
      <li>Akort {req.tuning || "EADGBE"}</li>
      <li>{req.engine === "claude" ? "Claude ile" : "Algoritma"}</li>
      <li>{req.mode === "dual" ? "İki ton tek patch'te" : "Her ton ayrı slot"}</li>
    </ul>
  );
}

/** Song art: the YouTube thumbnail, or a monogram for local files and offline use. */
export function Cover({ id, title, size = "md" }: { id: string | null; title: string; size?: "sm" | "md" }) {
  const [failed, setFailed] = React.useState(false);
  const initials = title.replace(/\(.*?\)|\[.*?\]/g, "").split(/[\s-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
  return (
    <span className={cx("cover", `cover--${size}`)} aria-hidden="true">
      {id && !failed ? <img src={thumbUrl(id)} alt="" onError={() => setFailed(true)} /> : <span className="cover__mono">{initials || "♪"}</span>}
    </span>
  );
}
