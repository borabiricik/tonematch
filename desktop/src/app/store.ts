import * as React from "react";

// localStorage for per-machine conveniences (theme, last slot, recent runs). Never required to work.
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
export function useStored<T>(key: string, fallback: T): [T, (v: T) => void] {
  const [v, setV] = React.useState<T>(() => load(key, fallback));
  return [v, (nv: T) => { setV(nv); save(key, nv); }];
}

export type Recent = { title: string; source: string; slot: string | null; name: string; when: number };

/** Map CLI errors to what the person should do. */
export function friendly(msg: string): { title: string; text: string; kind: "warn" | "danger" } {
  if (/BOSS TONE STUDIO/i.test(msg) && /açık|running|close/i.test(msg))
    return { title: "BOSS TONE STUDIO açık", text: "Cihazla aynı anda tek editör konuşabilir. BTS'i kapatıp tekrar dene.", kind: "warn" };
  if (/port not found|cannot open/i.test(msg))
    return { title: "GT-1 bulunamadı", text: "USB kablosunu ve cihazın açık olduğunu kontrol et.", kind: "danger" };
  if (/no guitar parts/i.test(msg))
    return { title: "Gitar bulunamadı", text: "Bu kayıtta ayrıştırılabilen bir gitar partisi yok.", kind: "warn" };
  return { title: "İşlem tamamlanamadı", text: msg || "Ayrıntı çıktıda.", kind: "danger" };
}
