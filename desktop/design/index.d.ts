// window.ToneMatch — React 18 components (documentation types; source: desktop/src/ds).
import type * as React from "react";

export type IconName =
  | "check" | "x" | "plus" | "minus" | "chevron-down" | "chevron-up" | "chevron-right" | "chevron-left" | "arrow-right"
  | "search" | "wave" | "library" | "device" | "tuner" | "settings" | "terminal" | "refresh" | "backup" | "folder" | "file"
  | "external" | "copy" | "play" | "stop" | "record" | "sun" | "moon" | "auto" | "info" | "alert" | "sparkle" | "link"
  | "clock" | "keyboard" | "grid" | "footswitch" | "ear" | "history" | "demo" | "more";
export declare function Icon(props: { name: IconName; className?: string; size?: number }): React.ReactElement;
export declare function Mark(props: { size?: number }): React.ReactElement;

// ------------------------------------------------------------------ Actions
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = the one main action of a view; secondary = the rest; ghost = inline tools; danger = stop / overwrite */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  icon?: IconName;
  /** a shortcut shown inside the button, e.g. "⌘↵" or "Space" */
  kbd?: string;
  loading?: boolean;
  block?: boolean;
}
export declare const Button: React.ForwardRefExoticComponent<ButtonProps & React.RefAttributes<HTMLButtonElement>>;

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconName;
  /** required: accessible name and tooltip */
  label: string;
  variant?: "ghost" | "secondary";
  size?: "sm" | "md";
}
export declare const IconButton: React.ForwardRefExoticComponent<IconButtonProps & React.RefAttributes<HTMLButtonElement>>;
export declare function Kbd(props: { children: React.ReactNode }): React.ReactElement;

// -------------------------------------------------------------------- Forms
export interface FieldProps {
  label: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
  /** replaces the hint with an error message (danger, role=alert) */
  error?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}
export declare function Field(props: FieldProps): React.ReactElement;

export interface TextInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  invalid?: boolean;
  icon?: IconName;
  size?: "md" | "lg";
  end?: React.ReactNode;
}
export declare const TextInput: React.ForwardRefExoticComponent<TextInputProps & React.RefAttributes<HTMLInputElement>>;

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  options: { value: string; label: string; group?: string }[];
  onChange?: (value: string) => void;
}
export declare function Select(props: SelectProps): React.ReactElement;

export interface SegmentedProps<T extends string = string> {
  name: string;
  label?: React.ReactNode;
  value: T;
  options: { value: T; label: React.ReactNode; icon?: IconName; disabled?: boolean }[];
  onChange: (value: T) => void;
  hint?: React.ReactNode;
  size?: "sm" | "md";
  block?: boolean;
}
export declare function Segmented<T extends string>(props: SegmentedProps<T>): React.ReactElement;

export interface SwitchProps { checked: boolean; onChange: (v: boolean) => void; label: React.ReactNode; hint?: React.ReactNode; disabled?: boolean; id?: string }
export declare function Switch(props: SwitchProps): React.ReactElement;

export interface SlotPickerProps { id?: string; value: number; onChange: (slot: number) => void; describedBy?: string; size?: "md" | "lg" }
export declare function SlotPicker(props: SlotPickerProps): React.ReactElement;

// ----------------------------------------------------------------- Feedback
export type LedState = "off" | "on" | "ok" | "warn" | "err" | "busy" | "rec";
export declare function Led(props: { state?: LedState }): React.ReactElement;

export interface ChipProps { children: React.ReactNode; tone?: "neutral" | "ok" | "warn" | "err" | "info"; icon?: IconName; led?: LedState; param?: string; title?: string }
export declare function Chip(props: ChipProps): React.ReactElement;

export interface StatusProps { state: LedState; label: React.ReactNode; detail?: React.ReactNode; onClick?: () => void; disabled?: boolean; title?: string }
export declare function Status(props: StatusProps): React.ReactElement;

export interface NoticeProps { tone?: "info" | "ok" | "warn" | "danger" | "busy"; title: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }
export declare function Notice(props: NoticeProps): React.ReactElement;

export interface DialogProps {
  open: boolean; title: React.ReactNode; children?: React.ReactNode;
  confirmLabel: string; cancelLabel?: string; tone?: "primary" | "danger";
  onConfirm: () => void; onCancel: () => void;
}
export declare function Dialog(props: DialogProps): React.ReactElement;

export interface SheetProps { open: boolean; title: React.ReactNode; sub?: React.ReactNode; onClose: () => void; locked?: boolean; actions?: React.ReactNode; children: React.ReactNode }
export declare function Sheet(props: SheetProps): React.ReactElement;

export interface ToastInput { tone?: "ok" | "warn" | "danger" | "info"; title: React.ReactNode; text?: React.ReactNode; action?: { label: string; onClick: () => void } }
export declare function toast(t: ToastInput): void;
export declare function Toaster(): React.ReactElement;

export declare function EmptyState(props: { icon: IconName; title: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }): React.ReactElement;
export declare function Skeleton(props: { w?: number | string; h?: number; r?: number }): React.ReactElement;

export interface ConsoleLine { text: string; kind?: "cmd" | "dim" | "ok" | "err" }
export interface ConsoleProps { lines: ConsoleLine[]; height?: number }
export declare function Console(props: ConsoleProps): React.ReactElement;

// --------------------------------------------------------------------- Gear
export type Knobs = Record<"gain" | "bass" | "middle" | "treble" | "presence" | "level", number>;
export interface KnobProps { label: string; value: number; changed?: boolean; size?: "sm" | "md"; onPedal?: boolean }
export declare function Knob(props: KnobProps): React.ReactElement;
export declare function KnobRow(props: { values: Knobs; compareTo?: Knobs; size?: "sm" | "md"; onPedal?: boolean }): React.ReactElement;

export interface LcdProps { children: React.ReactNode; size?: "md" | "lg" }
export declare function Lcd(props: LcdProps): React.ReactElement;

export type BlockKind = "fx1" | "od" | "preamp" | "fx2" | "delay" | "reverb";
export interface PedalProps { kind: BlockKind; type: string | null; detail?: React.ReactNode; changed?: boolean; children?: React.ReactNode }
export declare function Pedal(props: PedalProps): React.ReactElement;

export interface Tone {
  role: string; amp: string; drive: string; stereo: string; knobs: Knobs;
  od: { type: string; drive: number; level: number } | null;
  fx: { slot: string; name: string; detail: string }[];
  segments: number[][];
  claude?: { confidence: "high" | "medium" | "low"; why: string } | null;
}
export interface SignalChainProps { tone: Tone; compareTo?: Tone }
export declare function SignalChain(props: SignalChainProps): React.ReactElement;

export interface SlotInfo { slot: string; name: string; amp: string; gain: number; dual?: boolean }
export interface SlotGridProps { slots: SlotInfo[] | null; target?: string; current?: string; selected?: string; filter?: string; onPick?: (slot: string) => void }
export declare function SlotGrid(props: SlotGridProps): React.ReactElement;

// ------------------------------------------------------------------- Meters
export interface Stage { name: string; state: "pending" | "active" | "done" | "error"; time?: string; note?: string }
export interface PipelineProps { stages: Stage[] }
export declare function Pipeline(props: PipelineProps): React.ReactElement;

export interface Lane { label: string; segments: number[][]; tone?: "song" | "you" }
export interface SongMapProps { duration: number; lanes: Lane[]; highlight?: number[][] }
export declare function SongMap(props: SongMapProps): React.ReactElement;

export interface LevelMeterProps { db: number; peak?: number; size?: "md" | "lg" }
export declare function LevelMeter(props: LevelMeterProps): React.ReactElement;

export interface TunerReading { note: string | null; cents: number; in_tune: boolean }
export interface CentsMeterProps { reading: TunerReading | null }
export declare function CentsMeter(props: CentsMeterProps): React.ReactElement;
export interface StringMeterProps { n: number; reading: TunerReading | null; target?: string }
export declare function StringMeter(props: StringMeterProps): React.ReactElement;

export interface AxisRow { key: string; label: string; hint: string; song: number; you: number; close: boolean; unit: "db" | "ratio" }
export interface AxisCompareProps { rows: AxisRow[] }
export declare function AxisCompare(props: AxisCompareProps): React.ReactElement;

export interface BandDiffProps { bands: Record<string, number>; ignored?: string[]; range?: number }
export declare function BandDiff(props: BandDiffProps): React.ReactElement;

export interface SparklineProps { values: number[]; width?: number; height?: number; label: string }
export declare function Sparkline(props: SparklineProps): React.ReactElement;

// ------------------------------------------------------------------ Results
export interface PatchResult { group: string; name: string; slot: string | null; dual: boolean; assigns: string[]; tones: Tone[] }
export interface PatchCardProps {
  patch: PatchResult;
  duration: number;
  onCalibrate?: (tone: Tone, ctl: "off" | "on" | undefined) => void;
  calibrateDisabled?: boolean;
}
export declare function PatchCard(props: PatchCardProps): React.ReactElement;

export declare function slotLabel(n: number): string;
export declare function parseSlot(text: string): number | null;
export declare function mmss(seconds: number): string;
export declare function signed(v: number, digits?: number): string;
