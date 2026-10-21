// desktop/design/tokens.json -> desktop/src/styles/tokens.css
// tokens.json is the single source (same file as the ToneMatch design system artifact). Run: npm run tokens
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const t = JSON.parse(readFileSync(join(root, "design/tokens.json"), "utf8"));
const [first, ...rest] = t.color.themes.map((th) => th.id);

const val = (v, theme) => (typeof v === "string" ? v : (v[theme] ?? v[first]));
const ref = (v) => v.replace(/^\{(.+)\}$/, "var(--$1)");
const themed = [...t.color.tokens, ...(t.shadow?.tokens ?? [])];
const block = (theme) => themed.map((x) => `  --${x.name}: ${ref(val(x.value, theme))};`).join("\n");
const flat = (fam) => (t[fam]?.tokens ?? []).map((x) => `  --${x.name}: ${x.value};`).join("\n");

const out = [];
out.push(`/* ${t.name} — generated from design/tokens.json by scripts/build-tokens.mjs. Do not edit. */`);
for (const f of t.type.fonts) {
  const lines = [`font-family: "${f.family}"`, `src: url("../assets/${f.file}") format("woff2")`, `font-weight: ${f.weight}`];
  if (f.stretch) lines.push(`font-stretch: ${f.stretch}`);
  if (f.unicodeRange) lines.push(`unicode-range: ${f.unicodeRange}`);
  lines.push("font-display: block");
  out.push(`@font-face {\n  ${lines.join(";\n  ")};\n}`);
}
out.push(`:root {\n${block(first)}\n  color-scheme: ${first};\n${flat("spacing")}\n${flat("radius")}\n${flat("motion")}\n` +
  Object.entries(t.type.families).map(([k, v]) => `  --font-${k}: ${v};`).join("\n") + "\n}");
for (const theme of rest) {
  // "system" = follow the OS; an explicit data-theme wins both ways
  out.push(`@media (prefers-color-scheme: ${theme}) {\n  :root:not([data-theme="${first}"]) {\n` +
    block(theme).replace(/^/gm, "  ") + `\n    color-scheme: ${theme};\n  }\n}`);
  out.push(`:root[data-theme="${theme}"] {\n${block(theme)}\n  color-scheme: ${theme};\n}`);
}
const CSS_PROPS = { fontStretch: "font-stretch", letterSpacing: "letter-spacing", textTransform: "text-transform",
  fontVariantNumeric: "font-variant-numeric" };
for (const g of t.type.groups) {
  for (const s of g.styles) {
    const fam = s.family ?? g.family;
    const lines = [`font-family: var(--font-${fam})`, `font-size: ${s.fontSize}`, `line-height: ${s.lineHeight}`,
      `font-weight: ${s.fontWeight}`];
    for (const [k, prop] of Object.entries(CSS_PROPS)) if (s[k]) lines.push(`${prop}: ${s[k]}`);
    out.push(`.t-${s.name} {\n  ${lines.join(";\n  ")};\n}`);
  }
}
writeFileSync(join(root, "src/styles/tokens.css"), out.join("\n\n") + "\n");
console.log("tokens.css written");
