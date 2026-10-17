"""Stage the ToneMatch design system files (project/...) from the desktop app sources."""
import json
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) / "project"  # usage: python scripts/stage-design-system.py <dir>  (after npm run ds)
COMP = OUT / "components"
if COMP.exists():
    shutil.rmtree(COMP)
COMP.mkdir(parents=True)
(OUT / "fonts").mkdir(parents=True, exist_ok=True)

shutil.copy(APP / "design/tokens.json", OUT / "tokens.json")
for f in ("Archivo.woff2", "MartianMono.woff2"):
    shutil.copy(APP / "src/assets/fonts" / f, OUT / "fonts" / f)
shutil.copy(APP / "src/styles/components.css", COMP / "bundle.css")
shutil.copy(APP / "design/README.md", OUT / "README.md")
shutil.copy(APP / "design/index.d.ts", COMP / "index.d.ts")
(COMP / "Cover").mkdir()
shutil.copy(APP / "design/cover.html", COMP / "Cover" / "preview.html")

NAMES = ["Button", "Field", "Segmented", "SlotPicker", "Tabs", "Panel", "Status", "Steps", "Notice", "Dialog",
         "Console", "Knob", "Timeline", "Chip", "PatchCard", "SlotGrid"]
header = {"format": 4, "namespace": "ToneMatch", "components": [{"name": n} for n in NAMES]}
bundle = (APP / "design/dist/bundle.js").read_text(encoding="utf-8")
assert "</script" not in bundle and "<!--" not in bundle
(COMP / "bundle.js").write_text(f"/* @ds-bundle: {json.dumps(header)} */\n" + bundle, encoding="utf-8")

SWEET = {
    "group": "rhythm+clean", "name": "GUNS N RHY/CLN", "slot": "U95", "dual": True, "assigns": [],
    "tones": [
        {"role": "rhythm", "amp": "BG DRIVE", "drive": "crunch", "stereo": "stereo",
         "knobs": {"gain": 78, "bass": 52, "middle": 55, "treble": 53, "presence": 9, "level": 42},
         "od": {"type": "T-SCREAM", "drive": 30, "level": 62},
         "fx": [{"slot": "FX1", "name": "PITCHSHIFTER", "detail": "-1"}, {"slot": "DELAY", "name": "STANDARD", "detail": "240 ms"},
                {"slot": "REVERB", "name": "ROOM", "detail": "0.8s"}],
         "segments": [[0.3, 45.6], [76.4, 105.4], [134.1, 354.4]],
         "claude": {"confidence": "high", "why": "Kayıt modifiyeli bir JCM800 ile yapıldığı için Marshall tipi amfi ve hafif T-SCREAM boost."}},
        {"role": "clean", "amp": "CLEAN TWIN", "drive": "clean", "stereo": "wide/double-tracked",
         "knobs": {"gain": 43, "bass": 52, "middle": 55, "treble": 53, "presence": 9, "level": 50},
         "od": None,
         "fx": [{"slot": "FX1", "name": "PITCHSHIFTER", "detail": "-1"}, {"slot": "FX2", "name": "COMPRESSOR", "detail": ""},
                {"slot": "REVERB", "name": "PLATE", "detail": "0.8s"}],
         "segments": [[45.6, 76.4], [105.4, 134.1]]},
    ],
}
ARCTIC = {
    "group": "rhythm", "name": "ARCTIC RHY", "slot": "U94", "dual": False, "assigns": [],
    "tones": [{"role": "rhythm", "amp": "COMBO CRUNCH", "drive": "crunch", "stereo": "wide/double-tracked",
               "knobs": {"gain": 82, "bass": 40, "middle": 51, "treble": 57, "presence": 0, "level": 41},
               "od": None, "fx": [{"slot": "REVERB", "name": "ROOM", "detail": "0.8s"}],
               "segments": [[3.7, 122.3], [142.1, 265.7]]}],
}
SLOTS = [{"slot": "U93", "name": "SONNE RHY", "amp": "BGNR UB METAL", "gain": 73, "dual": False},
         {"slot": "U94", "name": "ARCTIC RHY", "amp": "COMBO CRUNCH", "gain": 82, "dual": False},
         {"slot": "U95", "name": "GUNS N RHY/CLN", "amp": "BG DRIVE", "gain": 78, "dual": True},
         {"slot": "U96", "name": "GITAROO RHY/CLN", "amp": "MS1959 I", "gain": 78, "dual": True},
         {"slot": "U97", "name": "RUNNING RHY", "amp": "POWER DRIVE", "gain": 83, "dual": False},
         {"slot": "U98", "name": "NOTHING CLN", "amp": "CLEAN TWIN", "gain": 40, "dual": False},
         {"slot": "U99", "name": "MASTER OF RHY", "amp": "CORE METAL", "gain": 95, "dual": False}]

STYLE = "<style>body{margin:0;padding:16px;background:var(--canvas)}.row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}.col{display:grid;gap:14px}</style>"


def card(name, group, height, subtitle, body):
    """body: JS expression (an element) using h = React.createElement and T = window.ToneMatch."""
    return (f'<!-- @dsCard group="{group}" height={height} subtitle="{subtitle}" -->\n{STYLE}\n<div id="root"></div>\n'
            "<script>\nconst h = React.createElement, T = window.ToneMatch;\n"
            f"{body.strip()}\n</script>\n")


def render(expr):
    return f'ReactDOM.createRoot(document.getElementById("root")).render({expr.strip()});'


C = {}
C["Button"] = ("Actions", 72, "One primary per view, default for the rest, ghost for tools.", render("""
h("div", { className: "row" },
  h(T.Button, { variant: "primary" }, "Tonu çıkar ve U94'e yaz"),
  h(T.Button, null, "Listeyi oku"),
  h(T.Button, { variant: "ghost", size: "sm" }, "Listeden seç"),
  h(T.Button, { variant: "danger" }, "Durdur"),
  h(T.Button, { disabled: true }, "Tümünü yedekle"),
  h(T.Button, { variant: "ghost", size: "sm", iconOnly: true, "aria-label": "Tema" }, h(T.Icon, { name: "auto" })))"""),
"""Buttons trigger one action each; the label says what happens, verb first.

- `variant="primary"` (accent fill, `on-accent` text): the single main action of a view ("Tonu çıkar ve U94'e yaz"). Never two in one view.
- `variant="default"`: secondary actions ("Listeyi oku", "Tümünü yedekle").
- `variant="ghost"`: inline tools inside a panel ("Listeden seç") and the header's icon buttons.
- `variant="danger"`: stops or destroys ("Durdur"); confirm it with a Dialog.
- `size="sm"` is 28px high (default 34px); `iconOnly` makes it square and needs an `aria-label`; `block` fills the width.
- Consumer provides: `children` (the label), `onClick`, `disabled`; every other `<button>` prop passes through.""")

C["Field"] = ("Forms", 170, "Labelled input or select on a sunken well, with live feedback.", """
function Demo() {
  const [v, setV] = React.useState("https://www.youtube.com/watch?v=bpOSxM0rNPM");
  const [t, setT] = React.useState("D#G#C#F#A#D#");
  return h("div", { className: "col", style: { maxWidth: 340 } },
    h(T.Field, { label: "Şarkı", htmlFor: "f-src", hint: "YouTube linki ya da şarkı adı" },
      h(T.TextInput, { id: "f-src", value: v, onChange: (e) => setV(e.target.value) })),
    h(T.Field, { label: "Şarkının akordu", htmlFor: "f-tun",
        hint: h("span", null, "Sen ", h("strong", null, "EADGBE"), " çal · pitch shifter ", h("strong", null, "-1"), " yarım ses") },
      h(T.Select, { id: "f-tun", value: t, onChange: setT, options: [
        { value: "", label: "E standart · EADGBE" }, { value: "D#G#C#F#A#D#", label: "Eb standart · D#G#C#F#A#D#" }] })));
}
""" + render("h(Demo)"),
"""A Field is an engraved `tm-label`, one control and an optional hint line.

- Controls: `TextInput` (`mono` for note names and codes, `invalid` for a danger edge) or `Select` (`options`, `onChange(value)`).
- Controls sit on `well` with a `line-strong` edge.
- The hint gives live feedback in plain words with the decisive value in `<strong>` ("Sen EADGBE çal · pitch shifter -1"); when the input is invalid it says how to fix it.
- `action` puts one ghost tool on the label row ("Listeden seç").
- Consumer provides: `label`, `htmlFor` matching the control's `id`, the control as `children`, `hint`.""")

C["Segmented"] = ("Forms", 120, "Two or three exclusive modes as one sunken strip.", """
function Demo() {
  const [t, setT] = React.useState("slot");
  const hints = { slot: "Patch cihaza kaydedilir ve seçilir.", listen: "Edit buffer'a yüklenir, hiçbir slot değişmez.", file: "Cihaza dokunmaz; .tsl dosyası BTS ile açılabilir." };
  return h("div", { style: { maxWidth: 340 } }, h(T.Segmented, { name: "target", legend: "Nereye", value: t, onChange: setT, hint: hints[t],
    options: [{ value: "slot", label: "Slota yaz" }, { value: "listen", label: "Sadece dinle" }, { value: "file", label: "Dosyaya" }] }));
}
""" + render("h(Demo)"),
"""Segmented chooses one of two or three modes that change what the main action does.

- Radio inputs underneath, so arrow keys move between options; the checked option lifts onto `surface-raised`.
- With `legend` it renders as a `fieldset` Field with an optional `hint` explaining the chosen mode.
- Up to three short options; more belong in a Select.
- Consumer provides: `name`, `value`, `options` (`{ value, label, disabled? }`), `onChange(value)`.""")

C["SlotPicker"] = ("Forms", 60, "GT-1 user slot U01–U99: − / +, typing, arrow keys.", """
function Demo() { const [n, setN] = React.useState(94);
  return h("div", { style: { maxWidth: 220 } }, h(T.SlotPicker, { value: n, onChange: setN })); }
""" + render("h(Demo)"),
"""SlotPicker selects the user slot a patch is written to.

- Shows `U01`…`U99` in `accent-ink` mono. Typing "94", "u94" or "U94" works; ↑/↓ and the buttons step and wrap U99 → U01.
- Pair it with a Field hint naming what is in the slot now ("Şu an ARCTIC RHY. Önce yedeklenir.").
- `slotLabel(n)` and `parseSlot(text)` are exported for the same formatting elsewhere.
- Consumer provides: `value` (1–99), `onChange(n)`, optional `id`.""")

C["Tabs"] = ("Layout", 60, "The app's top-level views in the header.", """
function Demo() { const [v, setV] = React.useState("run");
  return h("div", { style: { paddingBottom: 12 } }, h(T.Tabs, { label: "Görünüm", value: v, onChange: setV,
    tabs: [{ id: "run", label: "Ton çıkar" }, { id: "device", label: "Cihaz" }] })); }
""" + render("h(Demo)"),
"""Tabs switch the app's views ("Ton çıkar", "Cihaz").

- `role="tablist"` with `aria-selected`; the selected tab gets an accent underline sitting on the header's bottom edge.
- Two or three views at most.
- Consumer provides: `tabs` (`{ id, label }`), `value`, `onChange(id)`, `label` for screen readers.""")

C["Panel"] = ("Layout", 140, "A faceplate section with an engraved head.", render("""
h("div", { style: { maxWidth: 420 } }, h(T.Panel, { title: "Hedef", action: h(T.Button, { variant: "ghost", size: "sm" }, "Listeden seç") },
  h("p", { className: "tm-field__hint", style: { margin: 0 } }, "Patch cihaza kaydedilir ve seçilir. Mevcut patch önce yedeklenir.")))"""),
"""A Panel groups related controls on `surface` with a lit top edge (`shadow-panel`).

- The head carries a `tm-label` title and at most one ghost tool on the right.
- The body pads `space-4` and stacks its children with the same gap.
- Never nest panels; separate groups inside one with `line` hairlines.
- Consumer provides: `title`, optional `action`, `children`.""")

C["Status"] = ("Feedback", 56, "LED plus a word: device and job state.", render("""
h("div", { className: "row" },
  h(T.Status, { state: "ok", onClick: () => {} }, "GT-1 · U94"),
  h(T.Status, { state: "busy" }, "GT-1 aranıyor"),
  h(T.Status, { state: "warn" }, "BOSS TONE STUDIO açık"),
  h(T.Status, { state: "err" }, "GT-1 bulunamadı"),
  h(T.Status, { state: "off" }, "Bekliyor"))"""),
"""Status reports a state with an LED and a short phrase.

- LED states: `off`, `on` (amber, active), `ok`, `warn`, `err`, `busy` (pulsing amber). `Led` is exported on its own for steps and notices.
- The text always names the state; the LED never stands alone.
- With `onClick` it becomes a button: in the header it re-checks the GT-1 connection, with the detail in `title`.
- Consumer provides: `state`, `children`, optional `onClick`, `title`, `disabled`.""")

C["Steps"] = ("Feedback", 96, "The four real pipeline stages with elapsed time.", render("""
h(T.Steps, { steps: [
  { name: "İndir", state: "done", time: "0:03", note: "indirildi" },
  { name: "Ayrıştır", state: "done", time: "0:41" },
  { name: "Analiz", state: "active", time: "0:12", note: "ton analizi…" },
  { name: "GT-1", state: "pending" }] })"""),
"""Steps shows progress through İndir → Ayrıştır → Analiz → GT-1, the order the engine really runs.

- Each step is `pending`, `active` (accent rule, busy LED), `done` (success rule, check) or `error` (danger rule, x).
- `time` is elapsed mm:ss in mono; `note` one short line about the current action.
- Only for real sequences, never as decoration.
- Consumer provides: `steps` (`{ name, state, time?, note? }`).""")

C["Notice"] = ("Feedback", 170, "Inline message: an error with its fix, file paths, confirmations.", render("""
h("div", { className: "col" },
  h(T.Notice, { tone: "warn", title: "BOSS TONE STUDIO açık", action: h(T.Button, { size: "sm" }, "Çıktıyı göster") },
    "Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene."),
  h(T.Notice, { tone: "ok", title: "Tüm slotlar yedeklendi" }, h("span", { className: "tm-readout" }, "backups\\\\20261017-141502_all_U01-U99.tsl")),
  h(T.Notice, { title: "Dosyalar" }, "Patch: ", h("span", { className: "tm-readout" }, "output\\\\Arctic_Monkeys_Do_I_Wanna_Know.tsl")))"""),
"""Notices report something the person should know or do.

- `tone`: `danger` (failed; announced as an alert), `warn` (needs attention), `ok` (done), `busy` (in progress), `info` (default, file paths).
- The title says what happened; the text says what to do. Paths and slots in `tm-readout` mono.
- At most one action button, on the right.
- Consumer provides: `title`, `children`, `tone`, optional `action`.""")

C["Dialog"] = ("Feedback", 220, "Confirms anything that overwrites a slot or stops a job.", """
function Demo() { const [open, setOpen] = React.useState(false);
  return h("div", null, h(T.Button, { onClick: () => setOpen(true) }, "Onay penceresini aç"),
    h(T.Dialog, { open, title: "U94 üzerine yazılsın mı?", confirmLabel: "Yaz", onCancel: () => setOpen(false), onConfirm: () => setOpen(false) },
      "Şu an ", h("strong", null, "ARCTIC RHY"), " var. Mevcut patch önce ", h("strong", null, "backups"), " klasörüne yedeklenir.")); }
""" + render("h(Demo)"),
"""Dialog (a native `<dialog>` opened modally) asks before an action the app cannot undo.

- The title is the question with the concrete slot; the text names what is there now and what protects it (the backup).
- Two buttons: `cancelLabel` ("Vazgeç") and the verb (`confirmLabel`: "Yaz", "Durdur") as primary; focus starts on the verb, Escape cancels.
- Consumer provides: `open`, `title`, `children`, `confirmLabel`, `onConfirm`, `onCancel`.""")

C["Console"] = ("Feedback", 140, "Raw CLI output, dark in both themes.", render("""
h(T.Console, { lines: [
  { text: "$ tonematch run https://www.youtube.com/watch?v=bpOSxM0rNPM --slot U94 --yes --json", kind: "cmd" },
  { text: "1/4 indiriliyor / hazırlanıyor ..." },
  { text: "    Official Arctic Monkeys - Arctic Monkeys - Do I Wanna Know?" },
  { text: "WARNING  read [16, 93, 0, 0] size 64: got 0 bytes (attempt 1)", kind: "dim" },
  { text: "4/4 GT-1 eşleştirmesi ..." }] })"""),
"""Console shows exactly what the engine printed, for a closer look when something goes wrong.

- Line kinds: `cmd` (the echoed command), plain stdout, `dim` (stderr and warnings), `ok`, `err`.
- Follows the end of the output automatically. In the app it lives in the bottom drawer, collapsed, with the last line visible in the bar.
- Consumer provides: `lines` (`{ text, kind? }`), optional `height`.""")

C["Knob"] = ("Readouts", 100, "A GT-1 knob: 270° arc, value and engraved name.", render("""
h("div", { style: { maxWidth: 440 } }, h(T.KnobRow, {
  values: { gain: 78, bass: 52, middle: 55, treble: 53, presence: 9, level: 42 },
  compareTo: { gain: 43, bass: 52, middle: 55, treble: 53, presence: 9, level: 50 } }))"""),
"""Knob shows a patch parameter the way the GT-1 front panel does: 0–100 on a 270° sweep from seven to five o'clock.

- The arc is `led` on a `well` track; the value is mono, the name an engraved label.
- `KnobRow` lays out the six preamp knobs in front-panel order (GAIN, BASS, MIDDLE, TREBLE, PRESENCE, LEVEL). With `compareTo` (the other tone of a CTL patch) values that differ turn `accent-ink`.
- Consumer provides: `label` and `value` for `Knob`; `values` (and `compareTo`) for `KnobRow`.""")

C["Timeline"] = ("Readouts", 60, "Where in the song a tone plays.", render("""
h("div", { className: "col", style: { maxWidth: 440 } },
  h(T.Timeline, { duration: 354.4, segments: [[0.3, 45.6], [76.4, 105.4], [134.1, 354.4]] }),
  h(T.Timeline, { duration: 354.4, segments: [[45.6, 76.4], [105.4, 134.1]], alt: true }))"""),
"""Timeline maps a tone's segments onto the length of the song.

- The main tone's segments are `accent`; the CTL-on tone (`alt`) uses `ink-muted`, so the two differ in lightness, not hue alone.
- The 0:00 and total-length scale sits under the bar; the segment list is the bar's `aria-label`.
- Consumer provides: `duration` (s), `segments` (`[[start, end], …]` in s), `alt`.""")

C["Chip"] = ("Readouts", 60, "One block of a patch, or a state with an LED.", render("""
h("div", { className: "tm-chips" },
  h(T.Chip, { tone: "accent", keyLabel: "OD/DS", detail: "d30" }, "T-SCREAM"),
  h(T.Chip, { keyLabel: "FX1", detail: "-1" }, "PITCHSHIFTER"),
  h(T.Chip, { keyLabel: "DELAY", detail: "240 ms" }, "STANDARD"),
  h(T.Chip, { keyLabel: "REVERB", detail: "0.8s" }, "ROOM"),
  h(T.Chip, { tone: "ok" }, "Cihaza yazıldı"),
  h(T.Chip, { icon: "file" }, "Sadece dosya"))"""),
"""Chip names one active block of a patch: an engraved key (OD/DS, FX1, DELAY, REVERB), the type as the GT-1 names it, and an optional mono detail.

- `tone="accent"` (accent-soft) only for the boost (OD/DS), the block that most changes the tone.
- State chips (`ok`, `warn`, `err`) carry an LED and a word ("Cihaza yazıldı").
- Consumer provides: `children` (the type or the word), `keyLabel`, `detail`, `tone`, `icon`.""")

C["PatchCard"] = ("Results", 440, "The result of a run: one GT-1 patch, its tones and where they play.",
                  f"const patch = {json.dumps(SWEET, ensure_ascii=False)};\n" + render("h(T.PatchCard, { patch, duration: 354.4 })"),
"""PatchCard shows one patch the engine built, from `tonematch run --json` (`@@RESULT` → `patches[]`).

- Head: the slot in large mono (or "—" when only a file was written), the patch name in the `well` readout in `accent-ink` as the unit shows it, one line on what the patch does, and a state Chip.
- Body: one column per tone. A CTL patch shows "CTL kapalı" and "CTL açık" side by side (stacked below 900px); knob values that change between them are marked.
- Each tone lists the amp model, a KnobRow, Chips for boost and effects, and a Timeline. In Claude mode (`tone.claude`) a CLAUDE chip with the confidence and Claude's one-line reason follow the amp.
- Consumer provides: `patch` (`PatchResult`), `duration` of the song in seconds.""")

C["SlotGrid"] = ("Results", 170, "All 99 user slots: pick a target, see what is where.",
                 f"const slots = {json.dumps(SLOTS, ensure_ascii=False)};\n" + """
function Demo() { const [t, setT] = React.useState("U94");
  return h(T.SlotGrid, { slots, target: t, current: "U95", onPick: setT }); }
""" + render("h(Demo)"),
"""SlotGrid lists U01–U99 with patch name and amp model, read with `tonematch gt1 list --json`.

- `target`: the slot the next run writes to (accent edge, accent-soft fill). `current`: the slot selected on the unit, marked "seçili" in `success`.
- `slots={null}` renders the 99-cell skeleton while the device is being read.
- A dual-tone patch shows "· CTL" after its amp.
- Consumer provides: `slots` (`SlotInfo[]` or null), `target`, `current`, `onPick(slot)`.""")

for name, (group, height, sub, body, readme) in C.items():
    d = COMP / name
    d.mkdir()
    (d / "preview.html").write_text(card(name, group, height, sub, body), encoding="utf-8")
    (d / "README.md").write_text(f"# {name}\n\n{readme}\n", encoding="utf-8")
print("components:", len(C))
