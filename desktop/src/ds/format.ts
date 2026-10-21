// Small formatting rules shared by the design system and the app. Numbers stay in the GT-1's own units.

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** 0:00 style. */
export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** User slot U01–U99. */
export const slotLabel = (n: number) => `U${String(n).padStart(2, "0")}`;
export function parseSlot(v: string): number | null {
  const m = /^\s*[uU]?\s*0*(\d{1,2})\s*$/.exec(v);
  const n = m ? Number(m[1]) : NaN;
  return n >= 1 && n <= 99 ? n : null;
}

/** Signed number with a real minus sign: +3, −1.5, 0. */
export function signed(v: number, digits = 0) {
  const s = Math.abs(v).toFixed(digits);
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

const ROLE: Record<string, string> = { rhythm: "Ritim", lead: "Solo", clean: "Temiz", crunch: "Crunch" };
export const roleName = (r: string) => ROLE[r] ?? r;

const DRIVE: Record<string, string> = { clean: "Temiz", crunch: "Crunch", high_gain: "Yüksek gain" };
export const driveName = (d: string) => DRIVE[d] ?? d;

/** "3 dk önce", "dün", "12 Eki". */
export function ago(ms: number, now = Date.now()) {
  const min = Math.round((now - ms) / 60000);
  if (min < 1) return "az önce";
  if (min < 60) return `${min} dk önce`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} sa önce`;
  if (h < 48) return "dün";
  return new Date(ms).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

/** YouTube video id from a URL, a bare id or a ytsearch; null for anything else. */
export function youtubeId(v: string): string | null {
  const s = v.trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(s)) return s;
  const m = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/.exec(s);
  return m ? m[1] : null;
}
export const thumbUrl = (id: string) => `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;

/** Turkish dative after a slot read aloud: U94'e, U96'ya, U20'ye. */
export function dative(n: number) {
  const tens = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"];
  const ones = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"];
  const word = n % 10 ? ones[n % 10] : tens[Math.floor(n / 10)];
  const vowels = "aeıioöuü";
  const last = [...word].reverse().find((c) => vowels.includes(c)) ?? "e";
  return `'${vowels.includes(word.at(-1)!) ? "y" : ""}${"aıou".includes(last) ? "a" : "e"}`;
}
