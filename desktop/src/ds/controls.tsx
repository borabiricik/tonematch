import * as React from "react";
import { Icon } from "./icons";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

// ------------------------------------------------------------------ Button
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost" | "danger";
  size?: "md" | "sm";
  iconOnly?: boolean;
  block?: boolean;
};
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", size = "md", iconOnly, block, className, type = "button", ...rest }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx("tm-btn", variant !== "default" && `tm-btn--${variant}`, size === "sm" && "tm-btn--sm",
        iconOnly && "tm-btn--icon", block && "tm-btn--block", className)}
      {...rest}
    />
  );
});

// ------------------------------------------------------------------- Field
export type FieldProps = {
  label: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
};
export function Field({ label, htmlFor, hint, action, children }: FieldProps) {
  return (
    <div className="tm-field">
      {action ? (
        <div className="tm-field__row">
          <label className="tm-label" htmlFor={htmlFor}>{label}</label>
          {action}
        </div>
      ) : (
        <label className="tm-label" htmlFor={htmlFor}>{label}</label>
      )}
      {children}
      {hint && <span className="tm-field__hint">{hint}</span>}
    </div>
  );
}

export type TextInputProps = React.InputHTMLAttributes<HTMLInputElement> & { mono?: boolean; invalid?: boolean };
export const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(function TextInput(
  { mono, invalid, className, ...rest }, ref) {
  return (
    <input ref={ref} type="text" spellCheck={false} autoComplete="off" aria-invalid={invalid || undefined}
      className={cx("tm-input", mono && "tm-input--mono", className)} {...rest} />
  );
});

export type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  options: { value: string; label: string }[];
  onChange?: (value: string) => void;
};
export function Select({ options, onChange, ...rest }: SelectProps) {
  return (
    <div className="tm-select">
      <select onChange={(e) => onChange?.(e.target.value)} {...rest}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

// --------------------------------------------------------------- Segmented
export type SegmentedProps<T extends string> = {
  name: string;
  legend?: React.ReactNode;
  value: T;
  options: { value: T; label: React.ReactNode; disabled?: boolean }[];
  onChange: (value: T) => void;
  hint?: React.ReactNode;
};
export function Segmented<T extends string>({ name, legend, value, options, onChange, hint }: SegmentedProps<T>) {
  const strip = (
    <div className="tm-seg">
      {options.map((o) => (
        <React.Fragment key={o.value}>
          <input type="radio" name={name} id={`${name}-${o.value}`} value={o.value} checked={value === o.value}
            disabled={o.disabled} onChange={() => onChange(o.value)} />
          <label htmlFor={`${name}-${o.value}`}>{o.label}</label>
        </React.Fragment>
      ))}
    </div>
  );
  if (!legend) return strip;
  return (
    <fieldset className="tm-field">
      <legend className="tm-label">{legend}</legend>
      {strip}
      {hint && <span className="tm-field__hint">{hint}</span>}
    </fieldset>
  );
}

// -------------------------------------------------------------- SlotPicker
export const slotLabel = (n: number) => `U${String(n).padStart(2, "0")}`;
export function parseSlot(v: string): number | null {
  const m = /^\s*[uU]?\s*0*(\d{1,2})\s*$/.exec(v);
  const n = m ? Number(m[1]) : NaN;
  return n >= 1 && n <= 99 ? n : null;
}
const wrap = (n: number) => ((n - 1 + 99) % 99) + 1;

export type SlotPickerProps = { id?: string; value: number; onChange: (slot: number) => void; describedBy?: string };
/** GT-1 user slot U01–U99: − / + buttons, typing ("94", "u94"), arrow keys; wraps U99 → U01. */
export function SlotPicker({ id, value, onChange, describedBy }: SlotPickerProps) {
  const [text, setText] = React.useState(slotLabel(value));
  React.useEffect(() => setText(slotLabel(value)), [value]);
  const commit = () => {
    const n = parseSlot(text);
    if (n) onChange(n);
    else setText(slotLabel(value));
  };
  return (
    <div className="tm-slotpick">
      <button type="button" aria-label="Önceki slot" onClick={() => onChange(wrap(value - 1))}><Icon name="minus" /></button>
      <input id={id} value={text} inputMode="numeric" aria-describedby={describedBy}
        aria-invalid={parseSlot(text) ? undefined : true}
        onChange={(e) => { setText(e.target.value); const n = parseSlot(e.target.value); if (n) onChange(n); }}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            e.preventDefault();
            onChange(wrap(value + (e.key === "ArrowUp" ? 1 : -1)));
          } else if (e.key === "Enter") commit();
        }} />
      <button type="button" aria-label="Sonraki slot" onClick={() => onChange(wrap(value + 1))}><Icon name="plus" /></button>
    </div>
  );
}

// -------------------------------------------------------------------- Tabs
export type TabsProps<T extends string> = { tabs: { id: T; label: React.ReactNode }[]; value: T; onChange: (id: T) => void; label?: string };
export function Tabs<T extends string>({ tabs, value, onChange, label }: TabsProps<T>) {
  return (
    <nav className="tm-tabs" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" className="tm-tab" aria-selected={t.id === value} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </nav>
  );
}

// ------------------------------------------------------------------- Panel
export function Panel({ title, action, children }: { title: React.ReactNode; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="tm-panel">
      <div className="tm-panel__head"><span className="tm-label">{title}</span>{action}</div>
      <div className="tm-panel__body">{children}</div>
    </section>
  );
}
