import * as React from "react";
import * as cli from "../cli";
import { Button, Console, Icon, Mark, Status, Tabs, slotLabel, type ConsoleLine, type LedState, type SlotInfo } from "../ds";
import { DeviceView } from "./DeviceView";
import { RunView } from "./RunView";
import { TunerView } from "./TunerView";
import { friendly, useStored } from "./store";

// Every action is a tonematch CLI command (cli.ts → src-tauri run_cli); this file only holds app state.

const THEMES = ["system", "light", "dark"] as const;
type Theme = (typeof THEMES)[number];
type View = "run" | "device" | "tuner";

export type Device = {
  state: LedState;
  label: string;
  detail: string;
  connected: boolean;
  current: string;
  slots: SlotInfo[];          // last known list (cache file), [] = never read
  updated: number | null;     // when the list was last read from the unit (unix s)
  refreshing: boolean;        // reading the unit right now
};

export function App() {
  const [theme, setTheme] = useStored<Theme>("theme", "system");
  const [view, setView] = React.useState<View>("run");
  const [slot, setSlot] = useStored<number>("slot-n", 20);
  const [busy, setBusy] = React.useState(false);
  const [lines, setLines] = React.useState<ConsoleLine[]>([]);
  const [drawer, setDrawer] = React.useState(false);
  const [device, setDevice] = React.useState<Device>({ state: "busy", label: "GT-1 aranıyor", detail: "", connected: false,
    current: "", slots: [], updated: null, refreshing: false });
  const [env, setEnv] = React.useState<cli.EnvInfo | null>(null);

  React.useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);

  React.useEffect(() => {
    cli.onBusy(setBusy);
    cli.onLog((l) => setLines((prev) => {
      const next: ConsoleLine = "cmd" in l ? { text: `$ ${l.cmd}`, kind: "cmd" } : { text: l.text, kind: l.stream === "stderr" ? "dim" : undefined };
      return prev.length > 3000 ? [...prev.slice(-2500), next] : [...prev, next];
    }));
    // the last known slot list shows at once; the unit is read in the background
    loadCache().then(() => cli.environment()).then((e) => { setEnv(e); if (e.ready) refreshDevice(); });
  }, []);

  async function loadCache() {
    const c = await cli.cachedSlots<SlotInfo>();
    setDevice((d) => ({ ...d, slots: c.slots, updated: c.updated }));
  }

  type Info = { current: string; edit_buffer: string; preamp_from_system: boolean; slots?: SlotInfo[] };
  function applyInfo(r: cli.Outcome<Info>) {
    if (r.result) {
      const i = r.result;
      setDevice((d) => ({ ...d, connected: true, current: i.current, state: i.preamp_from_system ? "warn" : "ok",
        label: `GT-1 · ${i.current}`, refreshing: false,
        ...(i.slots ? { slots: i.slots, updated: Date.now() / 1000 } : {}),
        detail: i.preamp_from_system ? "Cihazda PREAMP tercihi SYSTEM: patch'lerin amfi ayarı yok sayılır." : `Seçili: ${i.current} ${i.edit_buffer.trim()}` }));
      return null;
    }
    const f = friendly(r.error?.message ?? "");
    setDevice((d) => ({ ...d, connected: false, refreshing: false, state: f.kind === "warn" ? "warn" : "err", label: f.title, detail: f.text }));
    return r.error?.message ?? "Cihaz okunamadı.";
  }

  /** Connection + all 99 slots in one go (~4 s); the cached list stays on screen meanwhile. */
  async function refreshDevice(): Promise<string | null> {
    setDevice((d) => ({ ...d, refreshing: true, ...(d.connected ? {} : { state: "busy" as LedState, label: "GT-1 aranıyor" }) }));
    return applyInfo(await cli.run<Info>(["gt1", "status"]));
  }

  /** After a run wrote slots: the cache file already has them; only the selected slot changed on the unit. */
  async function afterWrite() {
    await loadCache();
    applyInfo(await cli.run<Info>(["gt1", "info", "--json"]));
  }

  const lastLine = [...lines].reverse().find((l) => l.text.trim())?.text.trim() ?? "Henüz bir şey çalışmadı.";
  const nextTheme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <Mark />
          <span className="brand__name">ToneMatch</span>
          <span className="tm-label brand__device">GT-1</span>
        </div>
        <Tabs<View> label="Görünüm" value={view} onChange={setView}
          tabs={[{ id: "run", label: "Ton çıkar" }, { id: "device", label: "Cihaz" }, { id: "tuner", label: "Tuner" }]} />
        <div className="header-tools">
          <Status state={device.state} onClick={refreshDevice} disabled={busy || device.refreshing}
            title={device.detail || "GT-1 bağlantısını yeniden kontrol et"}>{device.label}</Status>
          <Button variant="ghost" size="sm" iconOnly onClick={() => setTheme(nextTheme)}
            title={`Tema: ${theme === "system" ? "sistem" : theme === "light" ? "açık" : "koyu"}`} aria-label="Temayı değiştir">
            <Icon name={theme === "system" ? "auto" : theme === "light" ? "sun" : "moon"} />
          </Button>
        </div>
      </header>

      {view === "run" ? (
        <RunView slot={slot} setSlot={setSlot} device={device} env={env}
          openLog={() => setDrawer(true)} onFinished={(wrote) => { if (wrote) afterWrite(); }} />
      ) : view === "tuner" ? (
        <TunerView device={device} busy={busy} />
      ) : (
        <DeviceView device={device} busy={busy} target={slotLabel(slot)} refresh={refreshDevice}
          onPick={(s) => { setSlot(Number(s.slice(1))); setView("run"); }} />
      )}

      <footer className="drawer" data-open={drawer}>
        <button className="drawer__bar" type="button" aria-expanded={drawer} aria-controls="drawer-body" onClick={() => setDrawer(!drawer)}>
          <span className="tm-label">Çıktı</span>
          <span className="drawer__last">{lastLine}</span>
          <Icon name="chevron" className="drawer__chev" />
        </button>
        {drawer && <div className="drawer__body" id="drawer-body"><Console lines={lines} height={220} /></div>}
      </footer>
    </>
  );
}
