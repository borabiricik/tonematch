"""Stage the ToneMatch design system files (project/...) from the desktop app sources.

usage: npm run ds && python scripts/stage-design-system.py <dir>
Writes <dir>/project/: tokens.json, README.md, fonts/, components/ (bundle.js, bundle.css, index.d.ts, one folder per
component with preview.html + README.md, Cover). Publish <dir> to the design-system artifact (docs/13-design-system.md).
"""
import json
import re
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) / "project"  # usage: python scripts/stage-design-system.py <dir>  (after npm run ds)
COMP = OUT / "components"
if COMP.exists():
    shutil.rmtree(COMP)
COMP.mkdir(parents=True)
if (OUT / "fonts").exists():
    shutil.rmtree(OUT / "fonts")
(OUT / "fonts").mkdir(parents=True)

tokens = json.loads((APP / "design/tokens.json").read_text(encoding="utf-8"))
shutil.copy(APP / "design/tokens.json", OUT / "tokens.json")
for f in tokens["type"]["fonts"]:
    shutil.copy(APP / "src/assets" / f["file"], OUT / f["file"])
shutil.copy(APP / "design/README.md", OUT / "README.md")
shutil.copy(APP / "design/index.d.ts", COMP / "index.d.ts")
(COMP / "Cover").mkdir()
shutil.copy(APP / "design/cover.html", COMP / "Cover" / "preview.html")

# bundle.css: the page compiles tokens.css itself, but not the motion family nor our `.t-<style>` class names
# (it names them `.<style>`), so both travel with the components, plus the few base rules they rely on.
app_tokens = (APP / "src/styles/tokens.css").read_text(encoding="utf-8")
type_classes = "\n".join(re.findall(r"^\.t-[\w-]+ \{[^}]*\}", app_tokens, flags=re.M))
motion = ":root {\n" + "\n".join(f"  --{t['name']}: {t['value']};" for t in tokens["motion"]["tokens"]) + "\n}"
base = """.tm-icon { width: 16px; height: 16px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.tm-icon--fill { fill: currentColor; stroke: none; }
.tm-mark { flex: none; display: block; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; } }"""
(COMP / "bundle.css").write_text(
    "/* ToneMatch components — from desktop/src/styles (motion, type classes, base, components.css) */\n"
    + "\n\n".join([motion, type_classes, base, (APP / "src/styles/components.css").read_text(encoding="utf-8")]),
    encoding="utf-8")

# ------------------------------------------------------------------------------------------- demo data
SWEET = {
    "group": "rhythm+clean", "name": "GUNS N RHY/CLN", "slot": "U95", "dual": True,
    "assigns": ["PREAMP TYPE BG DRIVE → CLEAN TWIN", "PREAMP GAIN 78 → 43", "OD/DS OFF", "DELAY OFF", "FX2 ON (COMPRESSOR)", "REVERB ROOM → PLATE"],
    "tones": [
        {"role": "rhythm", "amp": "BG DRIVE", "drive": "crunch", "stereo": "stereo",
         "knobs": {"gain": 78, "bass": 52, "middle": 55, "treble": 53, "presence": 9, "level": 42},
         "od": {"type": "T-SCREAM", "drive": 30, "level": 62},
         "fx": [{"slot": "FX1", "name": "PITCHSHIFTER", "detail": "-1"}, {"slot": "DELAY", "name": "STANDARD", "detail": "240 ms"},
                {"slot": "REVERB", "name": "ROOM", "detail": "0.8s"}],
         "segments": [[0.3, 45.6], [76.4, 105.4], [134.1, 200.2], [214.5, 354.4]],
         "claude": {"confidence": "high", "why": "Kayıt modifiyeli bir JCM800 ile yapıldığı için Marshall tipi amfi ve hafif T-SCREAM boost."}},
        {"role": "clean", "amp": "CLEAN TWIN", "drive": "clean", "stereo": "wide/double-tracked",
         "knobs": {"gain": 43, "bass": 52, "middle": 55, "treble": 53, "presence": 9, "level": 50},
         "od": None,
         "fx": [{"slot": "FX1", "name": "PITCHSHIFTER", "detail": "-1"}, {"slot": "FX2", "name": "COMPRESSOR", "detail": ""},
                {"slot": "REVERB", "name": "PLATE", "detail": "0.8s"}],
         "segments": [[45.6, 76.4], [105.4, 134.1], [200.2, 214.5]]},
    ],
}
SLOTS = [{"slot": "U93", "name": "SONNE RHY", "amp": "BGNR UB METAL", "gain": 73, "dual": False},
         {"slot": "U94", "name": "ARCTIC RHY", "amp": "COMBO CRUNCH", "gain": 82, "dual": False},
         {"slot": "U95", "name": "GUNS N RHY/CLN", "amp": "BG DRIVE", "gain": 78, "dual": True},
         {"slot": "U96", "name": "GITAROO RHY/CLN", "amp": "MS1959 I", "gain": 78, "dual": True},
         {"slot": "U97", "name": "RUNNING RHY", "amp": "POWER DRIVE", "gain": 83, "dual": False},
         {"slot": "U98", "name": "NOTHING CLN", "amp": "CLEAN TWIN", "gain": 40, "dual": False},
         {"slot": "U99", "name": "MASTER OF RHY", "amp": "CORE METAL", "gain": 95, "dual": False}]
AXES = [
    {"key": "drive", "label": "Drive", "hint": "Distorsiyon miktarı", "song": 0.62, "you": 0.68, "close": False, "unit": "ratio"},
    {"key": "mid", "label": "Orta", "hint": "400–1200 Hz · eksi = oyuk", "song": -1.8, "you": -4.4, "close": False, "unit": "db"},
    {"key": "presence", "label": "Presence", "hint": "2–4.5 kHz ısırık", "song": 2.4, "you": -1.5, "close": False, "unit": "db"},
    {"key": "body", "label": "Gövde", "hint": "200–450 Hz alt-orta", "song": 0.6, "you": 1.8, "close": True, "unit": "db"},
]
BANDS = dict(zip(["63Hz", "80Hz", "100Hz", "125Hz", "160Hz", "200Hz", "250Hz", "315Hz", "400Hz", "500Hz", "630Hz", "800Hz", "1kHz",
                  "1.25kHz", "1.6kHz", "2kHz", "2.5kHz", "3.15kHz", "4kHz", "5kHz", "6.3kHz", "8kHz"],
                 [4.2, 3.6, 3.1, 2.4, 1.6, 1.2, 0.9, 0.4, -0.6, -1.4, -2.2, -2.6, -2.1, -1.6, -1.9, -3.2, -4.1, -4.4, -3.6, -1.8, -1.0, -0.6]))

STYLE = ("<style>body{margin:0;padding:16px;background:var(--canvas);color:var(--ink);font-family:var(--font-text);"
         "font-size:14.5px;line-height:22px}.row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}"
         ".col{display:grid;gap:14px}</style>")


def card(group, height, sub, body):
    """body: JS that renders, using h = React.createElement and T = window.ToneMatch."""
    return (f'<!-- @dsCard group="{group}" height={height} subtitle="{sub}" -->\n{STYLE}\n<div id="root"></div>\n'
            "<script>\nconst h = React.createElement, T = window.ToneMatch;\n" + body.strip() + "\n</script>\n")


def render(expr):
    return f'ReactDOM.createRoot(document.getElementById("root")).render({expr.strip()});'


def demo(fn):
    """A stateful demo: `function Demo() {...}` source, rendered."""
    return fn.strip() + "\n" + render("h(Demo)")


C = {}
C["Button"] = ("Actions", 120, "One primary per view; secondary, ghost and danger for the rest.", render("""
h("div", { className: "col" },
  h("div", { className: "row" },
    h(T.Button, { variant: "primary", size: "lg", kbd: "⌘↵" }, "Tonu çıkar ve U20'ye yaz"),
    h(T.Button, { variant: "primary", size: "lg", disabled: true, kbd: "⌘↵" }, "Tonu çıkar")),
  h("div", { className: "row" },
    h(T.Button, { icon: "refresh" }, "Yenile"),
    h(T.Button, { icon: "backup", loading: true }, "Yedekleniyor 42/99"),
    h(T.Button, { variant: "ghost", icon: "terminal" }, "Çıktıyı göster"),
    h(T.Button, { variant: "danger", icon: "stop" }, "Durdur"),
    h(T.IconButton, { icon: "copy", label: "Yolu kopyala" })))"""),
"""Buttons trigger one action each; the label says what happens, verb first, and the result repeats the same words.

- `variant="primary"` (`primary` fill, `on-primary` text): the single main action of a view ("Tonu çıkar ve U20'ye yaz"). Never two in one view. Disabled, it becomes an empty `well` socket instead of a faded cream.
- `secondary` (default): other actions ("Yenile", "Tümünü yedekle"). `ghost`: inline tools ("Çıktıyı göster"). `danger`: stop or overwrite ("Durdur"), always confirmed with a Dialog.
- `size`: `sm` 30px, `md` 36px, `lg` 48px (the page's main action and stage mode). `icon` leads, `kbd` shows the shortcut inside ("⌘↵", "Space"), `loading` swaps the icon for a spinner and disables.
- `IconButton` is square and requires `label` (accessible name and tooltip).
- Consumer provides: `children` (the label), `onClick`; every other `<button>` prop passes through.""")

C["Field"] = ("Forms", 230, "Label, sunken control, live hint or error.", demo("""
function Demo() {
  const [src, setSrc] = React.useState("arctic monkeys do i wanna know");
  const [t, setT] = React.useState("D#G#C#F#A#D#");
  return h("div", { className: "col", style: { maxWidth: 560 } },
    h(T.TextInput, { size: "lg", icon: "search", value: src, onChange: (e) => setSrc(e.target.value), placeholder: "YouTube linki ya da sanatçı ve şarkı adı", "aria-label": "Şarkı" }),
    h(T.Field, { label: "Şarkının akordu", htmlFor: "f-tun",
        hint: h("span", null, "Gitarın ", h("strong", null, "EADGBE"), " kalsın · FX1'e pitch shifter ", h("strong", null, "−1"), " yarım ses") },
      h(T.Select, { id: "f-tun", value: t, onChange: setT, options: [
        { value: "", label: "E standart · EADGBE" }, { value: "D#G#C#F#A#D#", label: "Eb standart · D#G#C#F#A#D#", group: "Pitch shifter ile" }] })),
    h(T.Field, { label: "Özel akort", htmlFor: "f-c", error: "6 tel gerekiyor, 5 nota var." },
      h(T.TextInput, { id: "f-c", value: "DGCFA", invalid: true, onChange: () => {} })));
}"""),
"""A Field is a sentence-case label (`label` style, `ink-muted`), one control and a hint line that gives live feedback.

- Controls sit on `well` with a `line-strong` edge; focus turns the edge `focus` with a soft ring.
- `TextInput`: `size="lg"` for the one question of a page (the song), `icon` leading, `end` for a tool (clear button, `/` keycap), `invalid` for a danger edge. `Select`: native, with optional option `group`s.
- The hint names the decisive value in `<strong>` ("Gitarın EADGBE kalsın · pitch shifter −1"); `error` replaces it in `danger` and is announced.
- Consumer provides: `label`, `htmlFor` matching the control's `id`, the control as `children`, `hint` or `error`.""")

C["Segmented"] = ("Forms", 150, "Two to four exclusive modes with a sliding thumb.", demo("""
function Demo() {
  const [t, setT] = React.useState("slot");
  const hints = { slot: "Patch seçtiğin slota yazılır ve cihazda seçilir.", listen: "Edit buffer'a yüklenir, hiçbir slot değişmez.", file: "Cihaza dokunmaz; .tsl dosyası yazılır." };
  return h("div", { style: { maxWidth: 460 } }, h(T.Segmented, { name: "target", label: "Nereye", value: t, onChange: setT, hint: hints[t], block: true,
    options: [{ value: "slot", label: "Slota yaz", icon: "device" }, { value: "listen", label: "Sadece dinle", icon: "ear" }, { value: "file", label: "Dosyaya", icon: "file" }] }));
}"""),
"""Segmented chooses one of two to four modes that change what the main action does.

- Native radios underneath: arrow keys move, the thumb (`surface-raised`, `line-strong`) slides in `dur-base`.
- With `label` it renders as a fieldset Field; `hint` explains the chosen mode in one sentence.
- `size="sm"` inside cards (the CTL switch on a PatchCard), `block` to fill the width.
- Consumer provides: `name`, `value`, `options` (`{ value, label, icon?, disabled? }`), `onChange(value)`.""")

C["Switch"] = ("Forms", 90, "An on/off setting with its label and consequence.", demo("""
function Demo() { const [on, setOn] = React.useState(true);
  return h("div", { style: { maxWidth: 460 } }, h(T.Switch, { checked: on, onChange: setOn, label: "Cihaz olmadan dene",
    hint: "Açıkken komutlar çalışmaz; slotlar, ton çıkarma, tuner ve kalibrasyon örnek veriyle canlandırılır." })); }"""),
"""Switch turns one setting on or off immediately (no Save button).

- Label left, a 42×24 track right; on = `primary` track, `on-primary` thumb.
- The hint says what changes when it is on.
- Consumer provides: `checked`, `onChange(v)`, `label`, optional `hint`, `disabled`.""")

C["SlotPicker"] = ("Forms", 70, "GT-1 user slot U01–U99: − / +, typing, arrow keys.", demo("""
function Demo() { const [n, setN] = React.useState(20);
  return h("div", { className: "row" }, h(T.SlotPicker, { value: n, onChange: setN }), h(T.SlotPicker, { value: n, onChange: setN, size: "lg" })); }"""),
"""SlotPicker selects the user slot a patch is written to.

- Shows `U01`…`U99` in `readout`. Typing "94", "u94" or "U94" works; ↑/↓ and the buttons step and wrap U99 → U01.
- Pair it with a Field hint naming what is in the slot now ("Şu an: U2 STREETS · VO DRIVE").
- Consumer provides: `value` (1–99), `onChange(n)`, optional `id`, `size`.""")

C["Chip"] = ("Feedback", 70, "A state with an LED, a parameter with its value, a tag.", render("""
h("div", { className: "row" },
  h(T.Chip, { tone: "ok", led: "ok" }, "Cihaza yazıldı"),
  h(T.Chip, { tone: "warn", led: "warn" }, "Edit buffer'da"),
  h(T.Chip, { icon: "file" }, "Sadece dosya"),
  h(T.Chip, { icon: "sparkle", tone: "info" }, "Claude · emin"),
  h(T.Chip, { param: "PREAMP" }, "COMBO CRUNCH"))"""),
"""Chip labels a state or a fact in one short phrase.

- State chips (`ok`, `warn`, `err`) carry an LED and a `*-soft` ground; text stays `ink`.
- `param` puts a GT-1 parameter name before the value in the `param` style.
- Consumer provides: `children`, `tone`, `led`, `icon`, `param`.""")

C["Status"] = ("Feedback", 120, "LED plus a label and one line of detail: the device card.", render("""
h("div", { className: "col", style: { maxWidth: 260 } },
  h(T.Status, { state: "ok", label: "GT-1 bağlı", detail: "U94 · ARCTIC RHY", onClick: () => {} }),
  h(T.Status, { state: "busy", label: "GT-1 aranıyor", detail: "Cihaz okunuyor…", onClick: () => {} }),
  h(T.Status, { state: "warn", label: "BOSS TONE STUDIO açık", detail: "Tekrar denemek için tıkla", onClick: () => {} }))"""),
"""Status reports a state with an LED and words; the LED never stands alone.

- LED states: `off`, `on`, `ok`, `warn`, `err`, `busy` (pulses), `rec` (blinks, recording).
- With `onClick` it becomes a button on a `well` ground: in the rail it opens the Device page.
- Consumer provides: `state`, `label`, optional `detail`, `onClick`.""")

C["Notice"] = ("Feedback", 220, "Inline message: what happened and what to do.", render("""
h("div", { className: "col", style: { maxWidth: 640 } },
  h(T.Notice, { tone: "warn", title: "BOSS TONE STUDIO açık", action: h(T.Button, { size: "sm", variant: "ghost", icon: "terminal" }, "Çıktı") },
    "Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene."),
  h(T.Notice, { tone: "danger", title: "GT-1 bulunamadı" }, "USB kablosunu ve cihazın açık olduğunu kontrol et. Cihaz olmadan da 'Dosyaya' seçeneğiyle ton çıkarabilirsin."),
  h(T.Notice, { tone: "busy", title: "Cihazdan okunuyor" }))"""),
"""Notices report something the person should know or do, in place.

- `tone`: `danger` (failed, announced as an alert), `warn` (needs attention), `ok` (done), `busy` (in progress, spinner), `info` (default).
- The title says what happened; the text says what to do. At most one action, on the right.
- Something that happened elsewhere on screen ("U20 seçildi") is a `toast`, not a Notice.
- Consumer provides: `title`, `children`, `tone`, optional `action`.""")

C["Dialog"] = ("Feedback", 70, "Confirms every write to a slot and every stop.", demo("""
function Demo() { const [open, setOpen] = React.useState(false);
  return h("div", null, h(T.Button, { onClick: () => setOpen(true) }, "Onay penceresini aç"),
    h(T.Dialog, { open, title: "U20 üzerine yazılsın mı?", confirmLabel: "U20'ye yaz", onCancel: () => setOpen(false), onConfirm: () => setOpen(false) },
      h("p", null, "Şu an ", h("strong", null, "U2 STREETS"), " (VO DRIVE) var. Mevcut patch önce ", h("strong", null, "backups"), " klasörüne yedeklenir, yazdıktan sonra geri okunup doğrulanır."))); }"""),
"""Dialog (a native `<dialog>` opened modally) asks before an action the app cannot undo.

- The title is the question with the concrete slot; the text names what is there now and what protects it.
- Two buttons: `cancelLabel` ("Vazgeç") and the verb with the slot ("U20'ye yaz"); `tone="danger"` for stops. Focus starts on the verb, Escape cancels.
- Full-window work (calibration) uses `Sheet` instead: focus lands on the sheet, never its close button, so Space stays free.
- Consumer provides: `open`, `title`, `children`, `confirmLabel`, `onConfirm`, `onCancel`, optional `tone`.""")

C["Toaster"] = ("Feedback", 150, "Confirms an action that happened elsewhere on screen.", demo("""
function Demo() {
  React.useEffect(() => { T.toast({ tone: "ok", title: "U21 seçildi", text: "PINK FLOYD SOLO" }); }, []);
  return h("div", { style: { height: 110 } }, h(T.Button, { onClick: () => T.toast({ tone: "ok", title: "Hedef slot U20", text: "Sonraki ton buraya yazılır.", action: { label: "Ton çıkar", onClick: () => {} } }) }, "Bildirim göster"),
    h("div", { style: { position: "relative" } }, h(T.Toaster)));
}"""),
"""Toasts confirm what just happened in a short phrase that repeats the action's verb ("U21 seçildi", "U20 kaydedildi ve doğrulandı").

- Mount one `Toaster`; call `toast({ tone, title, text?, action? })` from anywhere.
- They stack bottom-right, stay 5 s (9 s for `danger`) and pause on hover; one optional action.
- Consumer provides: the `toast()` input.""")

C["Console"] = ("Feedback", 150, "Raw CLI output, dark in both themes.", render("""
h(T.Console, { height: 120, lines: [
  { text: "$ tonematch run ytsearch1:guns n roses sweet child --json --slot U20 --yes", kind: "cmd" },
  { text: "1/4 indiriliyor / hazırlanıyor ..." },
  { text: "  BS-Roformer-SW 60%", kind: "dim" },
  { text: "4/4 GT-1 eşleştirmesi ..." },
  { text: ".tsl: output/Guns_N_Roses_Sweet_Child_O_Mine.tsl", kind: "ok" }] })"""),
"""Console shows exactly what the engine printed, for a closer look when something goes wrong.

- Line kinds: `cmd` (the echoed command), plain stdout, `dim` (stderr and progress noise), `ok`, `err`.
- Follows the end unless you scrolled up. In the app it is the bottom drawer (⌘J) with the last line in the bar.
- Consumer provides: `lines` (`{ text, kind? }`), optional `height`.""")

C["Knob"] = ("Gear", 110, "A GT-1 knob: 0–100 on a 270° sweep.", render("""
h("div", { className: "col" },
  h(T.KnobRow, { values: { gain: 78, bass: 52, middle: 55, treble: 53, presence: 9, level: 42 } }),
  h(T.Knob, { label: "Gain", value: 82 }))"""),
"""Knob shows a patch parameter the way the GT-1's front panel does: 0–100, seven to five o'clock.

- Off a pedal: a `surface` cap with an `ink` pointer, the arc in `primary` on a `well` track. On the PREAMP pedal (`onPedal`): dark chicken heads on the cream faceplate.
- `KnobRow` lays out the six PREAMP knobs in front-panel order (GAIN, BASS, MIDDLE, TREBLE, PRESENCE, LEVEL). With `compareTo` (the other tone of a CTL patch) the values CTL changes are marked.
- Consumer provides: `label`, `value` (`Knob`); `values`, `compareTo` (`KnobRow`).""")

C["Lcd"] = ("Gear", 70, "A patch name as the unit's screen shows it.", render("""
h("div", { className: "row" }, h(T.Lcd, null, "GUNS N RHY/CLN"), h(T.Lcd, { size: "lg" }, "ARCTIC RHY"))"""),
"""Lcd shows a GT-1 patch name (16 characters, uppercase) on a backlit screen: `console-bg` with `console-cmd` text in `patch-name`.

- Dark in both themes, like the unit. Whitespace is kept, so names line up as on the device.
- Consumer provides: the name as `children`, `size`.""")

C["Pedal"] = ("Gear", 150, "One GT-1 block as the effect pedal a guitarist knows.", render("""
h("div", { className: "row", style: { alignItems: "stretch" } },
  h(T.Pedal, { kind: "fx1", type: "PITCHSHIFTER", detail: "-1" }),
  h(T.Pedal, { kind: "od", type: "T-SCREAM", detail: "DRIVE 30", changed: true }),
  h(T.Pedal, { kind: "fx2", type: null }),
  h(T.Pedal, { kind: "delay", type: "STANDARD", detail: "240 ms" }),
  h(T.Pedal, { kind: "reverb", type: "ROOM", detail: "0.8s" }))"""),
"""Pedal draws one block of a patch as an enclosure in its block's color: OD/DS orange, FX1 yellow, FX2 violet, DELAY teal, REVERB blue, PREAMP cream.

- On: the enclosure color with `on-pedal` text, a lit `record` LED, `shadow-pedal`. Off (`type={null}`): a dashed `line-strong` outline reading "Kapalı".
- `changed` adds a CTL tag: this block is different when CTL is on.
- The block name (`param`) is always on the pedal, so color is never the only cue.
- Consumer provides: `kind`, `type` (the GT-1's type name or null), `detail`, `changed`, `children` (the PREAMP's KnobRow).""")

C["SignalChain"] = ("Gear", 190, "A tone as a chain of pedals from IN to OUT.", f"const t = {json.dumps(SWEET['tones'][0], ensure_ascii=False)};\nconst o = {json.dumps(SWEET['tones'][1], ensure_ascii=False)};\n"
                    + render("h(T.SignalChain, { tone: t, compareTo: o })"),
"""SignalChain shows a tone the way a guitarist reads a pedalboard: FX1 → OD/DS → PREAMP (with its six knobs) → FX2 → DELAY → REVERB.

- Bypassed blocks stay in place as dashed outlines, so every chain has the same shape.
- With `compareTo` (the other side of a CTL patch) every block and knob CTL changes is marked.
- Below 940px of width the PREAMP takes the first row and the five pedals share the second.
- The order is the GT-1's usual one: it shows which blocks are on and how, not the routing stored in the patch.
- Consumer provides: `tone`, optional `compareTo`.""")

C["SlotGrid"] = ("Gear", 260, "The unit's user slots: target, current, selected, filter.",
                 f"const slots = {json.dumps(SLOTS, ensure_ascii=False)};\n" + demo("""
function Demo() { const [s, setS] = React.useState("U96");
  return h(T.SlotGrid, { slots, target: "U94", current: "U95", selected: s, onPick: setS }); }"""),
"""SlotGrid lists U01–U99 with patch name and amp model, from `tonematch gt1 list --json`.

- `target` (where the next run writes): a 2px `primary` edge and "· hedef". `current` (selected on the unit): a lit LED. `selected` (shown in the inspector): `select` ground.
- `filter` dims the slots whose name, amp or number do not match. `slots={null}` renders the loading skeleton.
- A dual-tone patch shows a CTL tag after its amp.
- Consumer provides: `slots`, `target`, `current`, `selected`, `filter`, `onPick(slot)`.""")

C["Pipeline"] = ("Meters", 120, "The run's four real stages as jacks on a cable.", render("""
h(T.Pipeline, { stages: [
  { name: "İndir", state: "done", time: "0:03", note: "indirildi" },
  { name: "Ayrıştır", state: "done", time: "1:41" },
  { name: "Analiz", state: "active", time: "0:12" },
  { name: "GT-1'e yaz", state: "pending" }] })"""),
"""Pipeline shows progress through İndir → Ayrıştır → Analiz → GT-1'e yaz, the order the engine really runs.

- Each stage is `pending`, `active` (pulsing `primary` ring), `done` (filled jack with a check) or `error`. The cable fills to the active stage in `dur-slow`.
- `time` is elapsed mm:ss; `note` one short line.
- Only for real sequences, never as decoration.
- Consumer provides: `stages` (`{ name, state, time?, note? }`).""")

C["SongMap"] = ("Meters", 110, "Where each tone plays in the song.", render(f"""
h(T.SongMap, {{ duration: 356, lanes: [
  {{ label: "Ritim", segments: {json.dumps(SWEET['tones'][0]['segments'])}, tone: "song" }},
  {{ label: "Temiz", segments: {json.dumps(SWEET['tones'][1]['segments'])}, tone: "you" }}] }})"""),
"""SongMap maps each tone's segments onto the song: one lane per tone, minute ticks, a time scale.

- The first tone uses `viz-song`, the CTL-on tone `viz-you`; they differ in lightness as well as hue.
- `highlight` shades a range (the part to play while calibrating).
- Each lane's segments are its accessible name.
- Consumer provides: `duration` (s), `lanes` (`{ label, segments, tone }`), optional `highlight`.""")

C["LevelMeter"] = ("Meters", 140, "Input level in dBFS as an LED ladder.", render("""
h("div", { className: "col" }, h(T.LevelMeter, { db: -14, peak: -6 }), h(T.LevelMeter, { db: -2.5, peak: -1, size: "lg" }))"""),
"""LevelMeter shows the GT-1's USB input while recording, −60…0 dBFS.

- Segments light `success`, then `warning` from −13, `danger` from −5; a thin `ink` mark holds the peak.
- `size="lg"` (40px) in stage mode. Pair it with a sentence that says what to do ("Sinyal tavana yakın: clip olabilir").
- Consumer provides: `db`, `peak`, `size`.""")

C["CentsMeter"] = ("Meters", 330, "The GT-1 tuner: cents needle and the six strings.", render("""
h("div", { className: "col" },
  h(T.CentsMeter, { reading: { note: "A", cents: -7, in_tune: false } }),
  h("div", { className: "row", style: { justifyContent: "center", gap: 24 } },
    [[6,"E",-2],[5,"A",-10],[4,"D",1],[3,"G",-15],[2,"B",1],[1,"E",0]].map(([n, note, c]) =>
      h(T.StringMeter, { key: n, n, reading: { note, cents: c, in_tune: Math.abs(c) <= 3 } }))))"""),
"""CentsMeter and StringMeter draw the GT-1's own tuner readings (`gt1 tuner --json`).

- CentsMeter: −50…+50 cents, the ±3 cent window in `success`, a needle colored `success` (in tune), `warning` (within 15) or `danger`.
- StringMeter: one vertical meter per string; ±5 cents snap to the center line, as BOSS TONE STUDIO does.
- In the app both live in stage mode, with the note in the `stage` style and a sentence ("Pes: teli sıkıştır"), so color is never the only cue.
- Consumer provides: `reading` (`{ note, cents, in_tune }` or null), `n` and `target` for StringMeter.""")

C["AxisCompare"] = ("Meters", 300, "Song vs your playing, axis by axis.", f"const rows = {json.dumps(AXES, ensure_ascii=False)};\n" + render("h(T.AxisCompare, { rows })"),
"""AxisCompare shows the calibration's measured axes: the song (`viz-song`) and your take (`viz-you`) as two marks on one scale, the gap between them shaded.

- dB axes run −12…+12 with a zero line; `drive` runs 0…1.
- Each row ends with the signed difference and a "yakın" / "farklı" tag.
- Consumer provides: `rows` (`{ key, label, hint, song, you, close, unit }`).""")

C["BandDiff"] = ("Meters", 220, "Your take minus the song, per 1/3 octave.", f"const bands = {json.dumps(BANDS)};\n" + render('h(T.BandDiff, { bands, ignored: ["63Hz", "80Hz", "100Hz", "125Hz"] })'),
"""BandDiff draws `compare.third_oct_diff` from `calibrate --json`: one bar per 1/3-octave band, up where your patch is louder (`viz-you`), down where the song is (`viz-song`).

- `ignored` bands (63–125 Hz: bass bleed in the stem) are hatched and dimmed; they do not count toward the spectral distance.
- ±8 dB by default (`range`); every value is in the accessible name.
- Consumer provides: `bands` (`{ "1kHz": -2.1, … }`), `ignored`, `range`.""")

C["PatchCard"] = ("Results", 520, "One GT-1 patch the engine built: chain, CTL, where it plays.",
                  f"const patch = {json.dumps(SWEET, ensure_ascii=False)};\n" + render("h(T.PatchCard, { patch, duration: 356, onCalibrate: () => {} })"),
"""PatchCard shows one patch from `tonematch run --json` (`@@RESULT` → `patches[]`).

- Head: the slot in `readout-lg` ("TEMP" for the edit buffer, "—" for a file), the name on an `Lcd`, one line on what it does, a state Chip ("Cihaza yazıldı").
- A dual patch gets a CTL switch ("CTL kapalı · Ritim" / "CTL açık · Temiz") that flips the SignalChain; what CTL changes is tagged.
- "Çalarak karşılaştır" opens play-to-calibrate for the tone on screen. In Claude mode the tone shows Claude's confidence and reason.
- The SongMap shows where every tone of the patch plays; the CTL assigns fold out below it.
- Consumer provides: `patch`, `duration`, optional `onCalibrate(tone, ctl)`.""")

NAMES = list(C)
header = {"format": 4, "namespace": "ToneMatch", "components": [{"name": n} for n in NAMES]}
bundle = (APP / "design/dist/bundle.js").read_text(encoding="utf-8")
assert "</script" not in bundle and "<!--" not in bundle
(COMP / "bundle.js").write_text(f"/* @ds-bundle: {json.dumps(header)} */\n" + bundle, encoding="utf-8")

for name, (group, height, sub, body, readme) in C.items():
    d = COMP / name
    d.mkdir()
    (d / "preview.html").write_text(card(group, height, sub, body), encoding="utf-8")
    (d / "README.md").write_text(f"# {name}\n\n{readme}\n", encoding="utf-8")
print("components:", len(C), "->", OUT)
