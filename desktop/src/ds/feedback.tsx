import * as React from "react";
import { Button } from "./controls";
import { Icon } from "./icons";

// --------------------------------------------------------------------- LED
export type LedState = "off" | "on" | "ok" | "warn" | "err" | "busy";
export function Led({ state = "off" }: { state?: LedState }) {
  return <span className={`tm-led${state === "off" ? "" : ` tm-led--${state}`}`} aria-hidden="true" />;
}

// ------------------------------------------------------------------ Status
export type StatusProps = { state: LedState; children: React.ReactNode; onClick?: () => void; title?: string; disabled?: boolean };
/** LED + a word. With onClick it is a button (the header's device pill). */
export function Status({ state, children, onClick, title, disabled }: StatusProps) {
  const inner = <><Led state={state} /><span>{children}</span></>;
  return onClick
    ? <button type="button" className="tm-status tm-status--button" onClick={onClick} title={title} disabled={disabled}>{inner}</button>
    : <span className="tm-status" title={title}>{inner}</span>;
}

// ------------------------------------------------------------------- Steps
export type Step = { name: string; state: "pending" | "active" | "done" | "error"; time?: string; note?: string };
export function Steps({ steps }: { steps: Step[] }) {
  return (
    <ol className="tm-steps">
      {steps.map((s) => (
        <li key={s.name} className={`tm-step tm-step--${s.state}`} aria-current={s.state === "active" ? "step" : undefined}>
          <span className="tm-step__name">
            {s.state === "done" ? <Icon name="check" /> : s.state === "error" ? <Icon name="x" /> : <Led state={s.state === "active" ? "busy" : "off"} />}
            {s.name}
          </span>
          <span className="tm-step__time">{s.time ?? ""}</span>
          <span className="tm-step__note">{s.note ?? ""}</span>
        </li>
      ))}
    </ol>
  );
}

// ------------------------------------------------------------------ Notice
export type NoticeProps = {
  tone?: "info" | "ok" | "warn" | "danger" | "busy";
  title: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
};
export function Notice({ tone = "info", title, children, action }: NoticeProps) {
  const led: LedState = tone === "ok" ? "ok" : tone === "warn" ? "warn" : tone === "danger" ? "err" : tone === "busy" ? "busy" : "off";
  return (
    <div className={`tm-notice${tone === "info" || tone === "busy" ? "" : ` tm-notice--${tone}`}`} role={tone === "danger" ? "alert" : undefined}>
      {tone === "info" ? <Icon name="file" /> : <Led state={led} />}
      <div>
        <div className="tm-notice__title">{title}</div>
        {children && <div className="tm-notice__text">{children}</div>}
      </div>
      {action ?? <span />}
    </div>
  );
}

// ------------------------------------------------------------------ Dialog
export type DialogProps = {
  open: boolean;
  title: React.ReactNode;
  children?: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};
/** Native <dialog> opened modally: Escape cancels, focus lands on the confirm button. */
export function Dialog({ open, title, children, confirmLabel, cancelLabel = "Vazgeç", onConfirm, onCancel }: DialogProps) {
  const ref = React.useRef<HTMLDialogElement>(null);
  const yes = React.useRef<HTMLButtonElement>(null);
  React.useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { d.showModal(); yes.current?.focus(); }
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="tm-dialog" onCancel={(e) => { e.preventDefault(); onCancel(); }}>
      <div className="tm-dialog__body">
        <h2 className="tm-dialog__title">{title}</h2>
        {children && <p className="tm-dialog__text">{children}</p>}
      </div>
      <div className="tm-dialog__actions">
        <Button onClick={onCancel}>{cancelLabel}</Button>
        <Button ref={yes} variant="primary" onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </dialog>
  );
}

// ----------------------------------------------------------------- Console
export type ConsoleLine = { text: string; kind?: "cmd" | "dim" | "ok" | "err" };
export function Console({ lines, height }: { lines: ConsoleLine[]; height?: number }) {
  const ref = React.useRef<HTMLPreElement>(null);
  React.useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight; }, [lines]);
  return (
    <pre ref={ref} className="tm-console" style={height ? { height } : undefined}>
      {lines.map((l, i) => <span key={i} className={l.kind ? `is-${l.kind}` : undefined}>{l.text + "\n"}</span>)}
    </pre>
  );
}
