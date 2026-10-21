import * as React from "react";
import { Button, IconButton } from "./controls";
import { cx } from "./format";
import { Icon, type IconName } from "./icons";

// --------------------------------------------------------------------- LED
export type LedState = "off" | "on" | "ok" | "warn" | "err" | "busy" | "rec";
/** A panel LED. Never alone: always next to a word that says the same thing. */
export function Led({ state = "off" }: { state?: LedState }) {
  return <span className={cx("tm-led", state !== "off" && `tm-led--${state}`)} aria-hidden="true" />;
}

// -------------------------------------------------------------------- Chip
export type ChipProps = {
  children: React.ReactNode;
  tone?: "neutral" | "ok" | "warn" | "err" | "info";
  icon?: IconName;
  led?: LedState;
  /** a GT-1 parameter name before the value (uppercase, e.g. FX1) */
  param?: string;
  title?: string;
};
export function Chip({ children, tone = "neutral", icon, led, param, title }: ChipProps) {
  return (
    <span className={cx("tm-chip", `tm-chip--${tone}`)} title={title}>
      {led && <Led state={led} />}
      {icon && <Icon name={icon} />}
      {param && <span className="tm-chip__param t-param">{param}</span>}
      <span>{children}</span>
    </span>
  );
}

// ------------------------------------------------------------------ Status
export type StatusProps = { state: LedState; label: React.ReactNode; detail?: React.ReactNode; onClick?: () => void; disabled?: boolean; title?: string };
/** LED + label (+ one line of detail). With onClick it is a button (the rail's device card). */
export function Status({ state, label, detail, onClick, disabled, title }: StatusProps) {
  const inner = (
    <>
      <Led state={state} />
      <span className="tm-status__text">
        <span className="tm-status__label">{label}</span>
        {detail && <span className="tm-status__detail">{detail}</span>}
      </span>
    </>
  );
  return onClick
    ? <button type="button" className="tm-status tm-status--button" onClick={onClick} disabled={disabled} title={title}>{inner}</button>
    : <span className="tm-status" title={title}>{inner}</span>;
}

// -------------------------------------------------------------------- Card
export function Card({ children, className, as: As = "section", ...rest }: React.HTMLAttributes<HTMLElement> & { as?: "section" | "article" | "div" }) {
  return <As className={cx("tm-card", className)} {...rest}>{children}</As>;
}

export function SectionHead({ title, sub, actions, level = 2 }: { title: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode; level?: 2 | 3 }) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <div className="tm-sechead">
      <div>
        <H className="t-heading">{title}</H>
        {sub && <p className="tm-sechead__sub t-small">{sub}</p>}
      </div>
      {actions && <div className="tm-sechead__actions">{actions}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ Notice
export type NoticeProps = {
  tone?: "info" | "ok" | "warn" | "danger" | "busy";
  title: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
};
const NOTICE_ICON: Record<string, IconName> = { info: "info", ok: "check", warn: "alert", danger: "alert" };
export function Notice({ tone = "info", title, children, action }: NoticeProps) {
  return (
    <div className={cx("tm-notice", `tm-notice--${tone}`)} role={tone === "danger" ? "alert" : undefined}>
      {tone === "busy" ? <span className="tm-spinner" aria-hidden="true" /> : <Icon name={NOTICE_ICON[tone]} />}
      <div className="tm-notice__body">
        <div className="tm-notice__title">{title}</div>
        {children && <div className="tm-notice__text">{children}</div>}
      </div>
      {action && <div className="tm-notice__action">{action}</div>}
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
  tone?: "primary" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
};
/** Native <dialog> opened modally: Escape cancels, focus lands on the confirm button. */
export function Dialog({ open, title, children, confirmLabel, cancelLabel = "Vazgeç", tone = "primary", onConfirm, onCancel }: DialogProps) {
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
        <h2 className="tm-dialog__title t-title">{title}</h2>
        {children && <div className="tm-dialog__text">{children}</div>}
      </div>
      <div className="tm-dialog__actions">
        <Button onClick={onCancel}>{cancelLabel}</Button>
        <Button ref={yes} variant={tone} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </dialog>
  );
}

// ------------------------------------------------------------------- Sheet
export type SheetProps = {
  open: boolean;
  title: React.ReactNode;
  sub?: React.ReactNode;
  onClose: () => void;
  /** while true, Escape and the close button are ignored (e.g. while recording) */
  locked?: boolean;
  actions?: React.ReactNode;
  children: React.ReactNode;
};
/** A full-window modal surface for stage-mode work (calibration). */
export function Sheet({ open, title, sub, onClose, locked, actions, children }: SheetProps) {
  const ref = React.useRef<HTMLDialogElement>(null);
  const frame = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // focus the sheet itself, not its first button: Space in stage mode must never hit "close"
    if (open && !d.open) { d.showModal(); frame.current?.focus(); }
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="tm-sheet" onCancel={(e) => { e.preventDefault(); if (!locked) onClose(); }}>
      {open && (
        <div className="tm-sheet__frame" ref={frame} tabIndex={-1}>
          <header className="tm-sheet__head">
            <div className="tm-sheet__titles">
              <h2 className="t-title">{title}</h2>
              {sub && <div className="tm-sheet__sub t-small">{sub}</div>}
            </div>
            <div className="tm-sheet__actions">
              {actions}
              <IconButton icon="x" label="Kapat (Esc)" onClick={onClose} disabled={locked} />
            </div>
          </header>
          <div className="tm-sheet__body">{children}</div>
        </div>
      )}
    </dialog>
  );
}

// ------------------------------------------------------------------- Toast
export type ToastInput = { tone?: "ok" | "warn" | "danger" | "info"; title: React.ReactNode; text?: React.ReactNode; action?: { label: string; onClick: () => void } };
type ToastItem = ToastInput & { id: number };
let toastSeq = 0;
const toastListeners = new Set<(t: ToastItem) => void>();
/** Confirms an action that happened somewhere else on screen ("U20 yazıldı"). */
export function toast(t: ToastInput) {
  const item = { ...t, id: ++toastSeq };
  toastListeners.forEach((f) => f(item));
}
export function Toaster() {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  React.useEffect(() => {
    const add = (t: ToastItem) => setItems((xs) => [...xs.slice(-3), t]);
    toastListeners.add(add);
    return () => { toastListeners.delete(add); };
  }, []);
  const remove = (id: number) => setItems((xs) => xs.filter((x) => x.id !== id));
  return (
    <div className="tm-toaster" aria-live="polite">
      {items.map((t) => <ToastView key={t.id} t={t} onDone={() => remove(t.id)} />)}
    </div>
  );
}
function ToastView({ t, onDone }: { t: ToastItem; onDone: () => void }) {
  const [hover, setHover] = React.useState(false);
  React.useEffect(() => {
    if (hover) return;
    const h = setTimeout(onDone, t.tone === "danger" ? 9000 : 5000);
    return () => clearTimeout(h);
  }, [hover]);
  const tone = t.tone ?? "info";
  return (
    <div className={cx("tm-toast", `tm-toast--${tone}`)} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <Icon name={NOTICE_ICON[tone]} />
      <div className="tm-toast__body">
        <div className="tm-toast__title">{t.title}</div>
        {t.text && <div className="tm-toast__text">{t.text}</div>}
      </div>
      {t.action && <Button size="sm" variant="ghost" onClick={() => { t.action!.onClick(); onDone(); }}>{t.action.label}</Button>}
      <IconButton icon="x" label="Kapat" size="sm" onClick={onDone} />
    </div>
  );
}

// -------------------------------------------------------------- EmptyState
export function EmptyState({ icon, title, children, action }: { icon: IconName; title: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="tm-empty">
      <span className="tm-empty__icon"><Icon name={icon} size={22} /></span>
      <h3 className="t-heading">{title}</h3>
      {children && <p className="t-small">{children}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ w, h = 14, r }: { w?: number | string; h?: number; r?: number }) {
  return <span className="tm-skel" style={{ width: w, height: h, borderRadius: r }} aria-hidden="true" />;
}

// ----------------------------------------------------------------- Console
export type ConsoleLine = { text: string; kind?: "cmd" | "dim" | "ok" | "err" };
export function Console({ lines, height }: { lines: ConsoleLine[]; height?: number }) {
  const ref = React.useRef<HTMLPreElement>(null);
  const stick = React.useRef(true);
  React.useEffect(() => { const el = ref.current; if (el && stick.current) el.scrollTop = el.scrollHeight; }, [lines]);
  return (
    <pre ref={ref} className="tm-console t-console" style={height ? { height } : undefined} tabIndex={0}
      aria-label="Çıktı" onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24; }}>
      {lines.length === 0 ? <span className="is-dim">Henüz bir komut çalışmadı.</span>
        : lines.map((l, i) => <span key={i} className={l.kind ? `is-${l.kind}` : undefined}>{l.text + "\n"}</span>)}
    </pre>
  );
}
