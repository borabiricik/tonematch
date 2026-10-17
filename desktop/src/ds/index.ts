// ToneMatch design system: React components over styles/components.css (tm- classes) and
// styles/tokens.css (generated from design/tokens.json). Built as window.ToneMatch for the
// design-system artifact by `npm run ds` (vite.ds.config.ts).
export { Icon, Mark, type IconName } from "./icons";
export {
  Button, Field, TextInput, Select, Segmented, SlotPicker, Tabs, Panel, slotLabel, parseSlot,
  type ButtonProps, type FieldProps, type TextInputProps, type SelectProps, type SegmentedProps, type SlotPickerProps, type TabsProps,
} from "./controls";
export { Led, Status, Steps, Notice, Dialog, Console, type LedState, type Step, type NoticeProps, type DialogProps, type ConsoleLine } from "./feedback";
export { Knob, KnobRow, Timeline, Chip, mmss, type Knobs, type KnobProps, type TimelineProps, type ChipProps } from "./readouts";
export { PatchCard, SlotGrid, roleName, type Tone, type PatchResult, type RunResult, type SlotInfo, type PatchCardProps, type SlotGridProps } from "./results";
