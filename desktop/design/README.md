ToneMatch turns a song into a BOSS GT-1 patch. The interface follows the guitar signal: song → analysis → patch chain → unit. Its chrome is quiet graphite (Stage) or daylight grey, with one warm accent: the cream of an amp's chicken-head knob. The only real color lives in the effect chain, where every GT-1 block is drawn as the pedal a guitarist already knows: the orange distortion box, the yellow compressor, the violet modulation, the teal delay, the blue reverb, and the cream amp faceplate with its six knobs.

Two distances shape every screen. **Desk mode** (matching a song, browsing slots) is read at arm's length: normal text sizes, dense controls. **Stage mode** (tuner, play-to-calibrate) is read from two meters away with a guitar in your hands: huge numerals, one obvious action, and the Space bar does it.

## Content fundamentals

- **Language.** The UI speaks Turkish, informally (*sen*), like a friend in the rehearsal room: "Gitarın EADGBE kalsın · pitch shifter yok." Short, active sentences. The control says exactly what happens ("Tonu çıkar ve U20'ye yaz"), the result confirms it with the same words ("U20 cihaza yazıldı ve doğrulandı").
- **Device words stay as the GT-1 prints them.** GAIN, BASS, MIDDLE, TREBLE, PRESENCE, LEVEL, CTL, FX1, OD/DS, amp models (COMBO CRUNCH, MS1959 I) and patch names are uppercase and untranslated, in the `param` or `patch-name` style. Everything we write ourselves is sentence case: no uppercase labels for our own words.
- **Numbers are real units.** Slots U01–U99, knobs 0–100, delay in ms, reverb in s, tuning as six notes low to high (D#G#C#F#A#D#), shifts in semitones (−1), cents (+3), dBFS. Minus signs are real (−), not hyphens.
- **Errors say what to do.** "BOSS TONE STUDIO açık. Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene." No apologies, no codes without a fix. Empty screens invite the next action.
- **Writes are always explained.** Every action that changes a slot says, before it happens, what is there now and what protects it ("Mevcut patch önce yedeklenir, yazdıktan sonra geri okunup doğrulanır").
- No emoji, no exclamation marks.

## Visual foundations

**Color.** Two themes from one token set: *Stage* (dark, first) and *Daylight* (light).
- Neutrals: `canvas` behind everything, `surface` for cards and the rail, `surface-raised` for dialogs, sheets and toasts, `well` for anything sunken (inputs, meters, knob tracks). `line` separates, `line-strong` edges controls.
- Text: `ink`; `ink-muted` for hints, captions and labels; `ink-faint` only for placeholders, scale ticks and disabled text.
- `primary` (knob cream on Stage, amp-tolex brown on Daylight) is the one main action per view and the active marker (current page, active pipeline jack, the target slot). Text on it is `on-primary`. A selected-but-secondary state (chosen segment's page, a selected slot) uses `select` with `ink`.
- Pedal colors (`pedal-od`, `pedal-fx1`, `pedal-fx2`, `pedal-delay`, `pedal-reverb`, `pedal-preamp`) appear only on effect blocks, always with `on-pedal` text and the block's name beside them. `pedal-edge` gives each enclosure its boundary in Daylight.
- `success`, `warning`, `danger` always sit beside a word, with `*-soft` backgrounds for notices. `record` is the recording LED and the pedal-on LED.
- `viz-song` and `viz-you` compare the song with your playing (and the two tones of a CTL patch on the song map). They differ in lightness as well as hue.
- `focus` is blue on purpose, so keyboard focus never reads as a selection.
- The console and the LCD (`console-*`) are dark in both themes, like the unit's screen.

**Type.** Three families, all variable, all bundled.
- **Saira** (width 50–125) is the panel printing: page questions (`display`), titles, headings, GT-1 parameter names (`param`, uppercase, wide), every number (`readout`, `readout-lg`, tabular), patch names on the LCD (`patch-name`) and the stage numerals (`stage`, 168px).
- **Atkinson Hyperlegible Next** is everything you read: `lead`, `body` (14.5/22), `body-strong`, `small`. Chosen for legibility at a distance and for its unambiguous letterforms (Il1, 0O).
- **Martian Mono** only for console output and file paths (`console`).

**Spacing and shape.** A 4px grid, `space-1` to `space-12`. Cards pad `space-5`, pages `space-8`. Radii: `radius-xs` (4px) for chips, keycaps and slot cells; `radius-sm` (7px) for controls; `radius-md` (11px) for cards, the console and pedal enclosures; `radius-lg` (16px) for dialogs and sheets; `radius-round` for LEDs and switches.

**Depth.** Cards get `shadow-card` (a lit top edge, almost no drop). Sunken things get `shadow-well`. Pedals get `shadow-pedal` (painted metal with a bevel). Dialogs, sheets and toasts get `shadow-raised`. Borders do most of the separating.

**Motion.** `dur-fast` (110ms) for hover and press (buttons move down 1px), `dur-base` (180ms) for the segmented thumb, switches and needles, `dur-slow` (320ms) for sheets and the pipeline cable. Busy LEDs pulse; the recording LED blinks. All of it stops under `prefers-reduced-motion`.

**Layout.** A 232px rail (64px below 1100px window width): the mark, four pages with their shortcuts (Ton çıkar ⌘1, Kütüphane ⌘2, Cihaz ⌘3, Tuner ⌘4), the device status card and Settings at the bottom. Pages are centered at most 1180px wide. The console is a drawer along the bottom (⌘J). Calibration opens as a full-window sheet in stage mode.

## Components

React 18 components exported on `window.ToneMatch` (`components/bundle.js`), styled by `tm-` classes in `components/bundle.css` over the tokens. In the app they are imported from `src/ds`.

- **Actions.** `Button` (`primary` once per view, `secondary`, `ghost` for tools, `danger` for stop and destructive), `IconButton` (always with a `label`), `Kbd` for shortcuts.
- **Forms.** `Field` (label, control, hint or error), `TextInput` (`lg` for the song field, an `icon`, an `end` tool), `Select`, `Segmented` (two to four exclusive modes, sliding thumb, arrow keys), `Switch`, `SlotPicker` (U01–U99, wraps).
- **Feedback.** `Led`, `Chip`, `Status`, `Notice`, `Dialog` (confirms every write and every stop), `Sheet` (stage-mode surface; focus lands on the sheet, never on its close button), `Toaster` + `toast()`, `EmptyState`, `Skeleton`, `Console`.
- **Gear.** `Knob` and `KnobRow` (the six PREAMP knobs; values that CTL changes are marked), `Lcd` (patch names), `Pedal` (one GT-1 block; bypassed blocks are a dashed outline) and `SignalChain` (a tone as FX1 → OD/DS → PREAMP → FX2 → DELAY → REVERB; blocks that CTL changes carry a CTL tag), `SlotGrid`.
- **Meters.** `Pipeline` (the four real run stages as jacks on a cable), `SongMap` (where each tone plays, minute ticks), `LevelMeter` (−60…0 dBFS LED ladder with peak hold), `CentsMeter` and `StringMeter` (tuner), `AxisCompare` (song vs you per measured axis), `BandDiff` (1/3-octave difference; ignored bands hatched), `Sparkline`.
- **Results.** `PatchCard`: slot, LCD name, state chip, the CTL switch for dual patches, "Çalarak karşılaştır", the signal chain, Claude's note, the song map.

The chain order in `SignalChain` is the GT-1's usual one. It shows which blocks are on and how they are set, not the routing stored in the patch.

## Iconography

An inline SVG set (`Icon`): 16×16 viewBox, `stroke: currentColor`, stroke-width 1.5, round caps and joins, no fill (play, stop and record are filled). Names cover navigation (wave, library, device, tuner, settings), actions (search, refresh, backup, folder, copy, play, stop, record, ear, footswitch), states (check, x, info, alert, sparkle for Claude mode) and chevrons. LEDs replace icons for state. No emoji, no icon font. The mark (`Mark`) is a cream chicken-head knob on a `primary` plate, pointer at two o'clock.

## Accessibility

- Every text pair named in a token's usage note meets 4.5:1 in both themes; control borders, the focus ring, LEDs, meters and pedal edges meet 3:1.
- The focus ring is 2px solid `focus` with a 2px offset on every interactive element. Moving between pages moves focus to the page.
- State is never color alone: every LED and state color comes with a word; tuner tones also change the status sentence ("Pes: teli sıkıştır").
- Knobs, pedals, meters, the song map and BandDiff carry their values as accessible names; Pipeline marks the active stage with `aria-current`.
- Stage mode works without a mouse: Space starts and stops, Escape closes (except while recording).
