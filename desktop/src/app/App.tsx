import * as React from "react";
import * as cli from "../cli";
import { Console, Icon, IconButton, Kbd, Led, Mark, Status, Toaster, cx, slotLabel, toast, type ConsoleLine, type IconName, type LedState, type SlotInfo } from "../ds";
import { DeviceView } from "./DeviceView";
import { LibraryView } from "./LibraryView";
import { MatchView } from "./MatchView";
import { SettingsView } from "./SettingsView";
import { TunerView } from "./TunerView";
import { friendly, kbd, typing, useStored, type Device, type RunRequest, type Theme, type View } from "./state";

// Every action is a tonematch CLI command (cli.ts → src-tauri run_cli, or src/demo/mock.ts in demo mode);
// this file holds the shell: rail, device state, console drawer, shortcuts.

const NAV: { id: View; label: string; icon: IconName; key: string }[] = [
  { id: "match", label: "Ton çıkar", icon: "wave", key: "1" },
  { id: "library", label: "Kütüphane", icon: "library", key: "2" },
  { id: "device", label: "Cihaz", icon: "device", key: "3" },
  { id: "tuner", label: "Tuner", icon: "tuner", key: "4" },
];

type Info = { current: string; edit_buffer: string; preamp_from_system: boolean; slots?: SlotInfo[] };

export function App() {
  const [theme, setTheme] = useStored<Theme>("theme", "system");
  const [view, setView] = React.useState<View>("match");
  const [slot, setSlot] = useStored<number>("slot-n", 20);
  const [busy, setBusy] = React.useState(false);
  const [running, setRunning] = React.useState(false);       // a `run` is in progress (Match view)
  const [lines, setLines] = React.useState<ConsoleLine[]>([]);
  const [drawer, setDrawer] = React.useState(false);
  const [prefill, setPrefill] = React.useState<{ req: RunRequest; n: number } | null>(null);
  const [device, setDevice] = React.useState<Device>({ state: "busy", label: "GT-1 aranıyor", detail: "", connected: false,
    current: "", editBuffer: "", preampFromSystem: false, slots: [], updated: null, refreshing: false });
  const [env, setEnv] = React.useState<cli.EnvInfo | null>(null);

  React.useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);

  React.useEffect(() => {
    const offBusy = cli.onBusy(setBusy);
    const offLog = cli.onLog((l) => setLines((prev) => {
      const next: ConsoleLine = "cmd" in l ? { text: `$ ${l.cmd}`, kind: "cmd" }
        : { text: l.text, kind: l.stream === "stderr" ? "dim" : /^(\.tsl:|backup written|.*kaydedildi)/.test(l.text) ? "ok" : undefined };
      return prev.length > 3000 ? [...prev.slice(-2500), next] : [...prev, next];
    }));
    // the last known slot list shows at once; the unit is read in the background
    loadCache().then(() => cli.environment()).then((e) => { setEnv(e); if (e.ready) refreshDevice(); });
    return () => { offBusy(); offLog(); };
  }, []);

  async function loadCache() {
    const c = await cli.cachedSlots<SlotInfo>();
    setDevice((d) => ({ ...d, slots: c.slots, updated: c.updated }));
  }

  function applyInfo(r: cli.Outcome<Info>) {
    if (r.result) {
      const i = r.result;
      setDevice((d) => ({
        ...d, connected: true, current: i.current, editBuffer: i.edit_buffer.trim(), preampFromSystem: i.preamp_from_system,
        state: i.preamp_from_system ? "warn" : "ok", refreshing: false,
        label: i.preamp_from_system ? "GT-1 · PREAMP = SYSTEM" : "GT-1 bağlı",
        detail: `${i.current} · ${i.edit_buffer.trim()}`,
        ...(i.slots ? { slots: i.slots, updated: Date.now() / 1000 } : {}),
      }));
      return null;
    }
    const f = friendly(r.error?.message ?? "");
    setDevice((d) => ({ ...d, connected: false, refreshing: false, state: f.kind === "warn" ? "warn" : "err", label: f.title, detail: "Tekrar denemek için tıkla" }));
    return r.error?.message ?? "Cihaz okunamadı.";
  }

  /** Connection + all 99 slots in one go (~4 s); the cached list stays on screen meanwhile. */
  async function refreshDevice(): Promise<string | null> {
    setDevice((d) => ({ ...d, refreshing: true, ...(d.connected ? {} : { state: "busy" as LedState, label: "GT-1 aranıyor", detail: "" }) }));
    return applyInfo(await cli.run<Info>(["gt1", "status"]));
  }

  /** After a write: the cache file already has the new names; only the selection changed on the unit. */
  async function afterWrite() {
    await loadCache();
    applyInfo(await cli.run<Info>(["gt1", "info", "--json"]));
  }

  async function selectOnDevice(s: string) {
    const r = await cli.run<{ slot: string; name: string }>(["gt1", "select", s, "--json"]);
    if (r.result) {
      toast({ tone: "ok", title: `${r.result.slot} seçildi`, text: r.result.name.trim() });
      setDevice((d) => ({ ...d, current: r.result!.slot, editBuffer: r.result!.name.trim(), detail: `${r.result!.slot} · ${r.result!.name.trim()}` }));
    } else {
      const f = friendly(r.error?.message ?? "");
      toast({ tone: "danger", title: f.title, text: f.text });
    }
  }

  // ------------------------------------------------------------ shortcuts
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      const nav = NAV.find((n) => n.key === e.key);
      if (nav) { e.preventDefault(); setView(nav.id); return; }
      if (e.key === ",") { e.preventDefault(); setView("settings"); return; }
      if (e.key.toLowerCase() === "j") { e.preventDefault(); setDrawer((o) => !o); return; }
      if (e.key.toLowerCase() === "k" && !typing(e)) { e.preventDefault(); setView("match"); requestAnimationFrame(() => document.getElementById("source")?.focus()); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // moving between pages puts focus on the page (screen readers announce it; Space reaches the page, not the rail)
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const first = React.useRef(true);
  React.useEffect(() => {
    if (first.current) { first.current = false; return; }
    scrollRef.current?.scrollTo({ top: 0 });
    if (view !== "match") scrollRef.current?.focus({ preventScroll: true });
  }, [view]);

  const lastLine = [...lines].reverse().find((l) => l.text.trim() && l.kind !== "cmd")?.text.trim() ?? "Henüz bir komut çalışmadı.";
  const target = slotLabel(slot);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Bölümler">
        <div className="rail__brand">
          <Mark size={30} />
          <div className="rail__brand-text">
            <span className="rail__name">ToneMatch</span>
            <span className="rail__for t-small">BOSS GT-1</span>
          </div>
        </div>

        <ul className="rail__nav">
          {NAV.map((n) => (
            <li key={n.id}>
              <button type="button" className={cx("rail__item", view === n.id && "is-active")} aria-current={view === n.id ? "page" : undefined}
                onClick={() => setView(n.id)} title={`${n.label} (${kbd(n.key)})`}>
                <IconFor name={n.icon} />
                <span className="rail__label">{n.label}</span>
                {n.id === "match" && running && view !== "match" ? <span className="rail__live"><Led state="busy" /><span className="sr-only">çalışıyor</span></span>
                  : <Kbd>{kbd(n.key)}</Kbd>}
              </button>
            </li>
          ))}
        </ul>

        <div className="rail__foot">
          {cli.DEMO && (
            <button type="button" className="rail__demo" onClick={() => setView("settings")} title="Demo modu: cihaz ve Python yerine örnek veri">
              <Led state="warn" /><span className="rail__label">Demo modu</span>
            </button>
          )}
          <Status state={device.refreshing && !device.connected ? "busy" : device.state} label={<span className="rail__label">{device.label}</span>}
            detail={<span className="rail__label">{device.refreshing ? "Cihaz okunuyor…" : device.detail}</span>}
            onClick={() => setView("device")} title={device.connected ? "Cihaz sayfasını aç" : "Cihaz sayfasını aç ve tekrar dene"} />
          <button type="button" className={cx("rail__item", view === "settings" && "is-active")} aria-current={view === "settings" ? "page" : undefined}
            onClick={() => setView("settings")} title={`Ayarlar (${kbd(",")})`}>
            <IconFor name="settings" />
            <span className="rail__label">Ayarlar</span>
            <Kbd>{kbd(",")}</Kbd>
          </button>
        </div>
      </nav>

      <div className="main">
        <div className="main__scroll" ref={scrollRef} tabIndex={-1} aria-label="İçerik">
          {/* Match stays mounted: a run keeps going (and its result stays) while you look elsewhere */}
          <div hidden={view !== "match"} className="main__page">
            <MatchView active={view === "match"} slot={slot} setSlot={setSlot} device={device} env={env} prefill={prefill}
              onRunning={setRunning} openLog={() => setDrawer(true)} openTuner={() => setView("tuner")}
              onFinished={(wrote) => { if (wrote) afterWrite(); }} />
          </div>
          {view === "library" && (
            <div className="main__page">
              <LibraryView slot={slot} onRerun={(req) => { setPrefill((p) => ({ req, n: (p?.n ?? 0) + 1 })); setView("match"); }}
                onSaved={afterWrite} />
            </div>
          )}
          {view === "device" && (
            <div className="main__page">
              <DeviceView device={device} busy={busy} target={target} refresh={refreshDevice} select={selectOnDevice}
                onTarget={(s) => { setSlot(Number(s.slice(1))); toast({ tone: "ok", title: `Hedef slot ${s}`, text: "Sonraki ton buraya yazılır.", action: { label: "Ton çıkar", onClick: () => setView("match") } }); }} />
            </div>
          )}
          {view === "tuner" && <div className="main__page main__page--stage"><TunerView device={device} busy={busy} /></div>}
          {view === "settings" && (
            <div className="main__page">
              <SettingsView theme={theme} setTheme={setTheme} env={env} />
            </div>
          )}
        </div>

        <footer className="drawer" data-open={drawer}>
          <button className="drawer__bar" type="button" aria-expanded={drawer} aria-controls="drawer-body" onClick={() => setDrawer(!drawer)}
            title={`Çıktı (${kbd("J")})`}>
            <IconFor name="terminal" />
            <span className="drawer__title">Çıktı</span>
            {busy && <Led state="busy" />}
            <span className="drawer__last t-console">{lastLine}</span>
            <Kbd>{kbd("J")}</Kbd>
          </button>
          {drawer && (
            <div className="drawer__body" id="drawer-body">
              <div className="drawer__tools">
                <IconButton icon="copy" label="Tümünü kopyala" size="sm" onClick={() => { navigator.clipboard?.writeText(lines.map((l) => l.text).join("\n")); toast({ tone: "ok", title: "Çıktı kopyalandı" }); }} />
                <IconButton icon="x" label="Temizle" size="sm" onClick={() => setLines([])} />
              </div>
              <Console lines={lines} height={240} />
            </div>
          )}
        </footer>
      </div>
      <Toaster />
    </div>
  );
}

function IconFor({ name }: { name: IconName }) {
  return <span className="rail__icon"><Icon name={name} /></span>;
}
