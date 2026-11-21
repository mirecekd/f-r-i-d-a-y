// frontend/src/views/memory_glyphs.ts
import { glyphCanvas, type GlyphName } from "../core/glyphs";
import type { Kind } from "./memory_orbs";

export { glyphCanvas, type GlyphName };

const URL_RE = /^(https?:\/\/|www\.)|\.(com|org|net|io|cz|dev)(\/|$)/i;
const EXT: [RegExp, GlyphName][] = [
  [/\.(pdf|docx?|odt|epub)$/i, "book"],
  [/(\.(py|ts|tsx|js|mjs|json|ya?ml|sh|toml|html|css)|(^|\/)dockerfile)$/i, "code"],
  [/\.(png|jpe?g|gif|webp|svg|bmp)$/i, "image"],
  [/\.(csv|tsv|xlsx?|ods)$/i, "table"],
];
const BY_KIND: Record<Kind, GlyphName> = { project: "gantt", session: "bubble", memory: "brain", concept: "bulb", file: "doc" };

/** Kind picks the glyph; file extensions and URL-looking labels refine it. */
export function glyphFor(kind: Kind, label: string): GlyphName {
  if (URL_RE.test(label.trim())) return "globe";
  if (kind === "file") for (const [re, name] of EXT) if (re.test(label.trim())) return name;
  return BY_KIND[kind] ?? "doc";
}

/** Fresh small canvas showing the kind's default glyph, for the colour key. */
export function glyphIcon(kind: Kind, color: string, px = 18): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = px * 2;
  c.className = "mg-gl";
  c.getContext("2d")!.drawImage(glyphCanvas(BY_KIND[kind], color), 0, 0, px * 2, px * 2);
  return c;
}
