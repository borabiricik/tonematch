import * as React from "react";
import type { LedState, RunResult, SlotInfo } from "../ds";

// localStorage for per-machine conveniences (theme, defaults, the library of past results). Never required:
// every read falls back, every write may silently fail (private mode, storage off).
export function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}
export function save(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage off: fine */ }
}
export function useStored<T>(key: string, fallback: T): [T, (v: T | ((prev: T) => T)) => void] {
  const [v, setV] = React.useState<T>(() => load(key, fallback));
  const set = React.useCallback((nv: T | ((prev: T) => T)) => {
    setV((prev) => {
      const next = typeof nv === "function" ? (nv as (p: T) => T)(prev) : nv;
      save(key, next);
      return next;
    });
  }, [key]);
  return [v, set];
}

// ------------------------------------------------------------------ types
export type View = "match" | "library" | "device" | "tuner" | "settings";
export type Target = "slot" | "listen" | "file";
export type DualMode = "dual" | "separate";
export type Engine = "algo" | "claude";
export type Theme = "system" | "dark" | "light";

/** What a run was asked to do: enough to run it again. */
export type RunRequest = { source: string; target: Target; slot: number; tuning: string; mode: DualMode; engine: Engine };

/** One finished run, kept in the library (localStorage, newest first). */
export type LibraryEntry = { id: string; when: number; request: RunRequest; result: RunResult };

export type Device = {
  state: LedState;
  label: string;
  detail: string;
  connected: boolean;
  current: string;
  editBuffer: string;
  preampFromSystem: boolean;
  slots: SlotInfo[];          // last known list (cache file), [] = never read
  updated: number | null;     // when the list was last read from the unit (unix s)
  refreshing: boolean;        // reading the unit right now
};

export const LIBRARY_KEY = "library";
const LIBRARY_MAX = 40;
export function addToLibrary(entry: LibraryEntry) {
  const all = load<LibraryEntry[]>(LIBRARY_KEY, []);
  const rest = all.filter((e) => !(e.request.source === entry.request.source && e.result.track_id === entry.result.track_id));
  save(LIBRARY_KEY, [entry, ...rest].slice(0, LIBRARY_MAX));
  libraryListeners.forEach((f) => f());
}
const libraryListeners = new Set<() => void>();
export function useLibrary(): [LibraryEntry[], (id: string) => void] {
  const [items, setItems] = React.useState(() => load<LibraryEntry[]>(LIBRARY_KEY, []));
  React.useEffect(() => {
    const f = () => setItems(load<LibraryEntry[]>(LIBRARY_KEY, []));
    libraryListeners.add(f);
    return () => { libraryListeners.delete(f); };
  }, []);
  const remove = (id: string) => {
    const next = load<LibraryEntry[]>(LIBRARY_KEY, []).filter((e) => e.id !== id);
    save(LIBRARY_KEY, next);
    setItems(next);
  };
  return [items, remove];
}

// --------------------------------------------------------------- messages
/** Map CLI errors to what the person should do. */
export function friendly(msg: string): { title: string; text: string; kind: "warn" | "danger" } {
  if (/BOSS TONE STUDIO/i.test(msg) && /açık|running|close/i.test(msg))
    return { title: "BOSS TONE STUDIO açık", text: "Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene.", kind: "warn" };
  if (/port not found|cannot open|no .*GT-1|GT-1 .*not found/i.test(msg))
    return { title: "GT-1 bulunamadı", text: "USB kablosunu ve cihazın açık olduğunu kontrol et. Cihaz olmadan da 'Dosyaya' seçeneğiyle ton çıkarabilirsin.", kind: "danger" };
  if (/gt1_spec\.json/i.test(msg))
    return { title: "GT-1 parametre tablosu yok", text: "src/tonematch/device/gt1/data/gt1_spec.json bu bilgisayarda yok. Diğer bilgisayardan kopyala ya da tools/build_gt1_spec.py ile üret (docs/09-setup.md).", kind: "danger" };
  if (/no guitar parts/i.test(msg))
    return { title: "Gitar bulunamadı", text: "Bu kayıtta ayrıştırılabilen bir gitar partisi yok.", kind: "warn" };
  if (/başka patch seçili/i.test(msg))
    return { title: "Kaydedilmedi", text: msg.charAt(0).toUpperCase() + msg.slice(1) + ". Cihazda doğru patch'i seçip tekrar dene.", kind: "warn" };
  return { title: "İşlem tamamlanamadı", text: msg || "Ayrıntı çıktıda.", kind: "danger" };
}

// -------------------------------------------------------------- shortcuts
export const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
export const MOD = IS_MAC ? "⌘" : "Ctrl";
export const kbd = (k: string) => (IS_MAC ? `⌘${k}` : `Ctrl+${k}`);

/** True when a key press belongs to a text field and must not trigger a shortcut. */
export function typing(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  if (!t) return false;
  if (t instanceof HTMLInputElement) return !["radio", "checkbox", "range", "button", "submit"].includes(t.type);
  return t.isContentEditable || /^(TEXTAREA|SELECT)$/.test(t.tagName);
}
