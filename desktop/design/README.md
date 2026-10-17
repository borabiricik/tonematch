ToneMatch turns a song into a BOSS GT-1 patch. The interface is built like the faceplate of the gear it controls: engraved uppercase labels, sunken wells for every control, one amber "valve" light for the action and the selection, LEDs for state, and mono readouts for anything the GT-1 shows as a number. Calm, precise, a little warm. Nothing decorative that a piece of hardware would not have.

## Content fundamentals

- **Language.** The UI speaks Turkish, informally (*sen*), the way a friend in the rehearsal room explains a pedal: "Gitarını EADGBE akortla, pitch shifter yok." Short, active sentences. The control says exactly what happens ("Tonu çıkar ve U94'e yaz") and the result confirms it ("U94 cihaza yazıldı").
- **Device terms stay as the GT-1 prints them.** GAIN, BASS, MIDDLE, TREBLE, PRESENCE, LEVEL, CTL, FX1, OD/DS, amp models (COMBO CRUNCH, MS1959 I) and patch names are uppercase and untranslated: that is what the player sees on the unit and in BOSS TONE STUDIO.
- **Numbers are real units.** Slots U01–U99, knobs 0–100, delay in ms, reverb in s, tuning as six notes low to high (D#G#C#F#A#D#), shifts in semitones (−1). Never turn them into words.
- **Errors say what to do.** "BOSS TONE STUDIO açık. Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene." No apologies, no codes without a fix.
- No emoji, no exclamation marks.

## Visual foundations

**Color.** Two themes from one token set: *Aluminium* (light, first) and *Graphite* (dark). Neutrals carry a faint green-grey bias, like anodised panels.
- `canvas` behind everything, `surface` for panels and the header, `surface-raised` for dialogs and buttons, `well` for anything sunken (inputs, knob tracks, the patch-name readout).
- Text: `ink` on every ground; `ink-muted` for hints and engraved labels; `ink-faint` only for placeholders and disabled text.
- `accent` (valve amber) appears once per view: the primary button, the active pipeline step, the target slot. Text on it is `on-accent`. Selected fills use `accent-soft` with `ink`. Accent as text (patch names, the target slot number, the active step) uses `accent-ink`.
- `led` is for lit LEDs and knob arcs only, never text.
- `success`, `warning`, `danger` always sit beside a word ("Cihaza yazıldı"), never alone.
- `focus` is blue on purpose, so keyboard focus never reads as a selection.
- The console (`console-bg`, `console-ink`, `console-dim`, `console-cmd`, `console-ok`, `console-err`) is dark in both themes, like the unit's screen.

**Type.** Two families, both variable.
- **Archivo** (width 62–125) for everything read. The `label` style at width 118, uppercase, letter-spaced 0.09em, is the engraving: field labels, knob names, panel heads. Titles run at width 106–112.
- **Martian Mono** for readouts: slot numbers (`readout`, `readout-lg`), knob values, patch names (`patch-name`) and the console (`console`).
- Body text is `body` (14/21); hints and metadata `small` (12.5/18); the empty-state headline `display`.

**Spacing and shape.** A 4px grid, `space-1` to `space-8`. Panels pad `space-4`, result cards `space-5`, views `space-6`. Radii are machined, not soft: `radius-sm` (4px) for controls, chips and slot cells, `radius-md` (7px) for panels, cards and the console, `radius-lg` (11px) for dialogs only, `radius-round` for LEDs and pills.

**Depth.** No drop shadows on content. `shadow-panel` gives panels and buttons a lit top edge, `shadow-well` sinks controls, `shadow-raised` lifts dialogs. Borders do the separating: `line` for hairlines between groups, `line-strong` for control edges.

**Motion.** 120–200ms ease-out on hover, press (buttons move down 1px) and dialog entry; a busy LED pulses. All of it stops under `prefers-reduced-motion`.

**Layout.** A 52px header (mark, view tabs, device Status, theme), a 340px control panel on the left ("Yeni ton"), the workspace on the right, the console drawer along the bottom. The workspace opens on a real state (the four pipeline stages and recent runs), then shows the running job, then the result cards.

## Components

React 18 components exported on `window.ToneMatch` (`components/bundle.js`), styled by `tm-` classes in `components/bundle.css` over the tokens. In the app they are imported from `src/ds`.
- Use `Button` with `variant="primary"` for the one action of a view; everything else is the default variant or `ghost`.
- Use `Segmented` for two or three exclusive modes ("Slota yaz / Sadece dinle / Dosyaya"), `SlotPicker` for U01–U99, `Field` with `TextInput` or `Select` for everything typed or chosen.
- `Steps` shows the four real pipeline stages (İndir, Ayrıştır, Analiz, GT-1) with elapsed time; never use it for anything that is not a sequence.
- `PatchCard` is the result: slot readout, patch name in the well, then per tone a `KnobRow`, `Chip`s for boost and effects and a `Timeline`; two columns when the patch switches tones with CTL. In Claude mode a tone also shows a `CLAUDE` chip with its confidence and Claude's reason under the amp.
- `Status` (with `Led`) is the device state in the header; `Notice` carries errors and file paths; `Dialog` confirms anything that overwrites a slot or stops a job; `SlotGrid` shows the unit's 99 slots.

## Iconography

A small inline SVG set (`Icon`): 16×16 viewBox, `stroke: currentColor`, stroke-width 1.6, round caps and joins, no fill. Names: check, x, file, minus, plus, chevron, sun, moon, auto. LEDs replace icons for state. No emoji, no icon font. The app mark (`Mark`) is a knob: an `accent` disc with an `on-accent` ring and pointer.

## Accessibility

- Every text pair named in a token's usage note meets 4.5:1 in both themes. Control borders, the focus ring, LEDs and knob arcs meet 3:1 on the grounds they sit on.
- The focus ring is 2px solid `focus` with a 2px offset on every interactive element.
- State is never color alone: every LED or state color comes with a word; the two Timeline tones differ in lightness.
- Knobs carry their label and value as text; Timelines carry their segments as an `aria-label`; Steps mark the active step with `aria-current`.
