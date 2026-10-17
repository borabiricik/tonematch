// window.ToneMatch — React 18 components (documentation types; source: desktop/src/ds).
import type * as React from "react";

export type IconName = "check" | "x" | "file" | "minus" | "plus" | "chevron" | "sun" | "moon" | "auto";
export declare function Icon(props: { name: IconName; className?: string }): React.ReactElement;
export declare function Mark(props: { size?: number }): React.ReactElement;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = the one main action of a view; ghost = inline tools; danger = stop/destroy */
  variant?: "default" | "primary" | "ghost" | "danger";
  size?: "md" | "sm";
  iconOnly?: boolean;
  block?: boolean;
}
export declare const Button: React.ForwardRefExoticComponent<ButtonProps & React.RefAttributes<HTMLButtonElement>>;

export interface FieldProps {
  label: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
  /** one ghost tool on the label row */
  action?: React.ReactNode;
  children: React.ReactNode;
}
export declare function Field(props: FieldProps): React.ReactElement;

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> { mono?: boolean; invalid?: boolean }
export declare const TextInput: React.ForwardRefExoticComponent<TextInputProps & React.RefAttributes<HTMLInputElement>>;

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  options: { value: string; label: string }[];
  onChange?: (value: string) => void;
}
export declare function Select(props: SelectProps): React.ReactElement;

export interface SegmentedProps<T extends string = string> {
  name: string;
  legend?: React.ReactNode;
  value: T;
  options: { value: T; label: React.ReactNode; disabled?: boolean }[];
  onChange: (value: T) => void;
  hint?: React.ReactNode;
}
export declare function Segmented<T extends string>(props: SegmentedProps<T>): React.ReactElement;

export interface SlotPickerProps { id?: string; value: number; onChange: (slot: number) => void; describedBy?: string }
export declare function SlotPicker(props: SlotPickerProps): React.ReactElement;
export declare function slotLabel(n: number): string;
export declare function parseSlot(text: string): number | null;

export interface TabsProps<T extends string = string> { tabs: { id: T; label: React.ReactNode }[]; value: T; onChange: (id: T) => void; label?: string }
export declare function Tabs<T extends string>(props: TabsProps<T>): React.ReactElement;

export interface PanelProps { title: React.ReactNode; action?: React.ReactNode; children: React.ReactNode }
export declare function Panel(props: PanelProps): React.ReactElement;

export type LedState = "off" | "on" | "ok" | "warn" | "err" | "busy";
export declare function Led(props: { state?: LedState }): React.ReactElement;
export interface StatusProps { state: LedState; children: React.ReactNode; onClick?: () => void; title?: string; disabled?: boolean }
export declare function Status(props: StatusProps): React.ReactElement;

export interface Step { name: string; state: "pending" | "active" | "done" | "error"; time?: string; note?: string }
export interface StepsProps { steps: Step[] }
export declare function Steps(props: StepsProps): React.ReactElement;

export interface NoticeProps { tone?: "info" | "ok" | "warn" | "danger" | "busy"; title: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }
export declare function Notice(props: NoticeProps): React.ReactElement;

export interface DialogProps {
  open: boolean;
  title: React.ReactNode;
  children?: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}
export declare function Dialog(props: DialogProps): React.ReactElement;

export interface ConsoleLine { text: string; kind?: "cmd" | "dim" | "ok" | "err" }
export interface ConsoleProps { lines: ConsoleLine[]; height?: number }
export declare function Console(props: ConsoleProps): React.ReactElement;

export interface KnobProps { label: string; value: number; changed?: boolean }
export declare function Knob(props: KnobProps): React.ReactElement;
export type Knobs = Record<"gain" | "bass" | "middle" | "treble" | "presence" | "level", number>;
export declare function KnobRow(props: { values: Knobs; compareTo?: Knobs }): React.ReactElement;

export interface TimelineProps { duration: number; segments: number[][]; alt?: boolean }
export declare function Timeline(props: TimelineProps): React.ReactElement;
export declare function mmss(seconds: number): string;

export interface ChipProps { keyLabel?: string; detail?: React.ReactNode; tone?: "default" | "accent" | "ok" | "warn" | "err"; icon?: "file"; children: React.ReactNode }
export declare function Chip(props: ChipProps): React.ReactElement;

export interface Tone {
  role: string; amp: string; drive: string; stereo: string; knobs: Knobs;
  od: { type: string; drive: number; level: number } | null;
  fx: { slot: string; name: string; detail: string }[];
  segments: number[][];
}
export interface PatchResult { group: string; name: string; slot: string | null; dual: boolean; assigns: string[]; tones: Tone[] }
export interface PatchCardProps { patch: PatchResult; duration: number }
export declare function PatchCard(props: PatchCardProps): React.ReactElement;

export interface SlotInfo { slot: string; name: string; amp: string; gain: number; dual?: boolean }
export interface SlotGridProps { slots: SlotInfo[] | null; target?: string; current?: string; onPick?: (slot: string) => void }
export declare function SlotGrid(props: SlotGridProps): React.ReactElement;
