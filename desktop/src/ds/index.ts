// ToneMatch design system: React components over styles/components.css (tm- classes) and
// styles/tokens.css (generated from design/tokens.json). Built as window.ToneMatch for the
// design-system artifact by `npm run ds` (vite.ds.config.ts). Rules: design/README.md, docs/13-design-system.md.
export { Icon, Mark, type IconName } from "./icons";
export { cx, mmss, slotLabel, parseSlot, signed, roleName, driveName, ago, youtubeId, thumbUrl, dative } from "./format";
export {
  Button, IconButton, Kbd, Field, TextInput, Select, Segmented, Switch, SlotPicker,
  type ButtonProps, type IconButtonProps, type FieldProps, type TextInputProps, type SelectProps, type SegmentedProps,
  type SwitchProps, type SlotPickerProps,
} from "./controls";
export {
  Led, Chip, Status, Card, SectionHead, Notice, Dialog, Sheet, Toaster, toast, EmptyState, Skeleton, Console,
  type LedState, type ChipProps, type StatusProps, type NoticeProps, type DialogProps, type SheetProps, type ToastInput, type ConsoleLine,
} from "./feedback";
export {
  Knob, KnobRow, Lcd, Pedal, SignalChain, SlotGrid,
  type Knobs, type KnobProps, type Tone, type PatchResult, type RunResult, type SlotInfo, type BlockKind, type PedalProps, type SlotGridProps,
} from "./gear";
export {
  Pipeline, SongMap, LevelMeter, CentsMeter, StringMeter, AxisCompare, BandDiff, Sparkline, tunerTone,
  type Stage, type Lane, type TunerReading, type AxisRow,
} from "./meters";
export { PatchCard, type PatchCardProps } from "./results";
