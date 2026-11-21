// frontend/src/scene/entity_logic.ts
import type { GlyphName } from "../core/glyphs";

/** Pure helpers of the `entity` kind (no THREE, so node can test them). */
const BY_SHAPE: Record<string, GlyphName> = {
  image: "image", doc: "doc", book: "book", table: "table", code: "code",
  audio: "audio", archive: "archive", tool: "tool", model: "model", note: "note", workshop: "workshop",
};
const BY_EXT: [RegExp, GlyphName][] = [
  [/\.(png|jpe?g|gif|webp|bmp|svg)$/i, "image"],
  [/\.(pdf|epub|odt)$/i, "book"],
  [/\.(csv|tsv|xlsx?|ods)$/i, "table"],
  [/\.(py|ts|tsx|js|mjs|json|ya?ml|sh|toml|html|css|c|h|cpp|rs|go|java)$/i, "code"],
  [/\.(mp3|wav|flac|ogg|m4a|opus)$/i, "audio"],
  [/\.(zip|tar|gz|7z|rar)$/i, "archive"],
];
export const TILE_LONG_SIDE = 3;
export const DEFAULT_TILE: [number, number] = [2.6, 1.9];
const MAX_TITLE = 28;

/** The shape names the glyph; a generic `doc` is refined by the file extension in the title. */
export function glyphForEntity(shape: string, title: string): GlyphName {
  const base = BY_SHAPE[shape] ?? "note";
  if (base !== "doc") return base;
  for (const [re, name] of BY_EXT) if (re.test(title.trim())) return name;
  return base;
}

/** Tile size keeping the thumbnail's real aspect: the longer side is TILE_LONG_SIDE, aspect clamped to 1:4 .. 4:1. */
export function tileSize(aspect: number): [number, number] {
  const a = Number.isFinite(aspect) && aspect > 0 ? Math.min(4, Math.max(0.25, aspect)) : 1;
  return a >= 1 ? [TILE_LONG_SIDE, TILE_LONG_SIDE / a] : [TILE_LONG_SIDE * a, TILE_LONG_SIDE];
}

export function shortTitle(title: string, max = MAX_TITLE): string {
  return title.length <= max ? title : `${title.slice(0, max - 1)}\u2026`;
}

/** Selected ids that are entity objects. */
export function isEntityRef(o: { kind: string; ref?: unknown }): boolean {
  const r = o.ref as { type?: unknown; id?: unknown } | undefined;
  return o.kind === "entity" && typeof r?.type === "string" && typeof r?.id === "string";
}
