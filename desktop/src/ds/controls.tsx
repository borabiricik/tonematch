import * as React from "react";
import { cx, parseSlot, slotLabel } from "./format";
import { Icon, type IconName } from "./icons";

// ------------------------------------------------------------------ Button
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  /** primary = the one main action of a view; secondary = everything else; ghost = inline tools; danger = stop/overwrite */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  icon?: IconName;
  /** a keyboard shortcut shown inside the button, e.g. "⌘↵" */
  kbd?: string;
  loading?: boolean;
  block?: boolean;
};
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", icon, kbd, loading, block, className, type = "button", children, disabled, ...rest }, ref) {
  return (
    <button ref={ref} type={type} disabled={disabled || loading} aria-busy={loading || undefined}
      className={cx("tm-btn", `tm-btn--${variant}`, `tm-btn--${size}`, block && "tm-btn--block", className)} {...rest}>
      {loading ? <span className="tm-spinner" aria-hidden="true" /> : icon && <Icon name={icon} />}
      {children && <span className="tm-btn__label">{children}</span>}
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  );
});

export type IconButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: IconName;
  /** required: the accessible name and the tooltip */
  label: string;
  variant?: "ghost" | "secondary";
  size?: "sm" | "md";
};
export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, label, variant = "ghost", size = "md", className, type = "button", ...rest }, ref) {
  return (
    <button ref={ref} type={type} aria-label={label} title={label}
      className={cx("tm-btn", `tm-btn--${variant}`, `tm-btn--${size}`, "tm-btn--icon", className)} {...rest}>
      <Icon name={icon} />
    </button>
  );
});

/** A keycap: shortcuts in buttons, menus and the settings list. */
export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="tm-kbd">{children}</kbd>;
}

// ------------------------------------------------------------------- Field
export type FieldProps = {
  label: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
  /** hint turns into an error message (danger, role=alert) */
  error?: React.ReactNode;
  /** one ghost tool on the label row */
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};
export function Field({ label, htmlFor, hint, error, action, children, className }: FieldProps) {
  return (
    <div className={cx("tm-field", className)}>
      <div className="tm-field__row">
        <label className="tm-field__label t-label" htmlFor={htmlFor}>{label}</label>
        {action}
      </div>
      {children}
      {error ? <span className="tm-field__hint tm-field__hint--error" role="alert">{error}</span>
        : hint && <span className="tm-field__hint">{hint}</span>}
    </div>
  );
}

export type TextInputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> & {
  invalid?: boolean;
  icon?: IconName;
  size?: "md" | "lg";
  /** a tool at the end of the field (clear button, kbd hint) */
  end?: React.ReactNode;
};
export const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(function TextInput(
  { invalid, icon, size = "md", end, className, ...rest }, ref) {
  return (
    <div className={cx("tm-input", `tm-input--${size}`, invalid && "is-invalid", className)}>
      {icon && <Icon name={icon} className="tm-input__icon" />}
      <input ref={ref} type="text" spellCheck={false} autoComplete="off" aria-invalid={invalid || undefined} {...rest} />
      {end && <span className="tm-input__end">{end}</span>}
    </div>
  );
});

export type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  options: { value: string; label: string; group?: string }[];
  onChange?: (value: string) => void;
};
export function Select({ options, onChange, className, ...rest }: SelectProps) {
  const groups = [...new Set(options.map((o) => o.group ?? ""))];
  return (
    <div className={cx("tm-select", className)}>
      <select onChange={(e) => onChange?.(e.target.value)} {...rest}>
        {groups.map((g) => {
          const items = options.filter((o) => (o.group ?? "") === g).map((o) => <option key={o.value} value={o.value}>{o.label}</option>);
          return g ? <optgroup key={g} label={g}>{items}</optgroup> : items;
        })}
      </select>
      <Icon name="chevron-down" className="tm-select__chev" />
    </div>
  );
}

// --------------------------------------------------------------- Segmented
export type SegmentedProps<T extends string> = {
  name: string;
  label?: React.ReactNode;
  value: T;
  options: { value: T; label: React.ReactNode; icon?: IconName; disabled?: boolean }[];
  onChange: (value: T) => void;
  hint?: React.ReactNode;
  size?: "sm" | "md";
  block?: boolean;
};
/** Two to four exclusive modes; arrow keys move between them (native radios). */
export function Segmented<T extends string>({ name, label, value, options, onChange, hint, size = "md", block }: SegmentedProps<T>) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const strip = (
    <div className={cx("tm-seg", `tm-seg--${size}`, block && "tm-seg--block")}
      style={{ "--n": options.length, "--i": index } as React.CSSProperties}>
      <span className="tm-seg__thumb" aria-hidden="true" />
      {options.map((o) => (
        <React.Fragment key={o.value}>
          <input type="radio" name={name} id={`${name}-${o.value}`} value={o.value} checked={value === o.value}
            disabled={o.disabled} onChange={() => onChange(o.value)} />
          <label htmlFor={`${name}-${o.value}`}>{o.icon && <Icon name={o.icon} />}<span>{o.label}</span></label>
        </React.Fragment>
      ))}
    </div>
  );
  if (!label) return strip;
  return (
    <fieldset className="tm-field">
      <legend className="tm-field__label t-label">{label}</legend>
      {strip}
      {hint && <span className="tm-field__hint">{hint}</span>}
    </fieldset>
  );
}

// ------------------------------------------------------------------ Switch
export type SwitchProps = { checked: boolean; onChange: (v: boolean) => void; label: React.ReactNode; hint?: React.ReactNode; disabled?: boolean; id?: string };
/** A footswitch-like toggle: label left, switch right. */
export function Switch({ checked, onChange, label, hint, disabled, id }: SwitchProps) {
  const auto = React.useId();
  const sid = id ?? auto;
  return (
    <div className={cx("tm-switch", disabled && "is-disabled")}>
      <label htmlFor={sid} className="tm-switch__text">
        <span className="tm-switch__label">{label}</span>
        {hint && <span className="tm-field__hint">{hint}</span>}
      </label>
      <button id={sid} type="button" role="switch" aria-checked={checked} disabled={disabled}
        className="tm-switch__track" onClick={() => onChange(!checked)}>
        <span className="tm-switch__thumb" />
      </button>
    </div>
  );
}

// -------------------------------------------------------------- SlotPicker
const wrap = (n: number) => ((n - 1 + 99) % 99) + 1;
export type SlotPickerProps = { id?: string; value: number; onChange: (slot: number) => void; describedBy?: string; size?: "md" | "lg" };
/** GT-1 user slot U01–U99: − / + buttons, typing ("94", "u94"), arrow keys; wraps U99 → U01. */
export function SlotPicker({ id, value, onChange, describedBy, size = "md" }: SlotPickerProps) {
  const [text, setText] = React.useState(slotLabel(value));
  React.useEffect(() => setText(slotLabel(value)), [value]);
  const commit = () => {
    const n = parseSlot(text);
    if (n) onChange(n);
    else setText(slotLabel(value));
  };
  return (
    <div className={cx("tm-slotpick", `tm-slotpick--${size}`)}>
      <button type="button" aria-label="Önceki slot" onClick={() => onChange(wrap(value - 1))}><Icon name="minus" /></button>
      <input id={id} value={text} inputMode="numeric" aria-describedby={describedBy} className="t-readout"
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
