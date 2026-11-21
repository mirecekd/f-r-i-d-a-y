// frontend/src/core/glyphs.ts
import { BASE_PATHS, type BaseGlyph, type Draw } from "./glyph_paths";
import { EXTRA_PATHS, type ExtraGlyph } from "./glyph_paths_more";

export type GlyphName = BaseGlyph | ExtraGlyph;

/** Canvas 2D paths on a 64x64 grid, drawn with the stroke style the caller has set. No fonts, no emoji. */
const DRAW: Record<GlyphName, Draw> = { ...BASE_PATHS, ...EXTRA_PATHS };

/** Kind colour lightened towards white: crisp on the dark disc yet still recognisably the kind's hue. */
function tint(hex: string): string {
  const mix = (i: number) => Math.round(parseInt(hex.slice(i, i + 2), 16) * 0.72 + 255 * 0.28);
  return `rgb(${mix(1)},${mix(3)},${mix(5)})`;
}

const cache = new Map<string, HTMLCanvasElement>();

/** Glyph in `color` blended towards white, on a faint tinted disc; cached per glyph+colour. */
export function glyphCanvas(name: GlyphName, color: string, size = 64): HTMLCanvasElement {
  const key = `${name}|${color}|${size}`;
  let c = cache.get(key);
  if (c) return c;
  c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d")!;
  g.scale(size / 64, size / 64);
  g.fillStyle = "rgba(3,10,20,.72)";
  g.beginPath(); g.arc(32, 32, 31, 0, 7); g.fill();
  g.strokeStyle = color + "aa"; g.lineWidth = 2.4;
  g.beginPath(); g.arc(32, 32, 30, 0, 7); g.stroke();
  g.lineWidth = 4.2; g.lineCap = g.lineJoin = "round";
  g.strokeStyle = tint(color); g.fillStyle = color + "55";
  g.translate(32, 32); g.scale(0.78, 0.78); g.translate(-32, -32);
  g.shadowColor = color; g.shadowBlur = 4;
  DRAW[name](g);
  cache.set(key, c);
  return c;
}

