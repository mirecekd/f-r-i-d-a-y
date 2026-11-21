// frontend/src/ui/deck_logic.ts

/** Pure Deck logic (filter, sort, counts, relative time, grid keys); no DOM, so node can test it. */
export interface DeckItem {
  id: string;
  type: string;
  title: string;
  subtitle?: string;
  created_at: number | string;
  updated_at: number | string;
  pinned: boolean;
  tags: string[];
  thumb_url?: string;
  source?: string;
  parent_ids: string[];
  size?: number;
}

export type SortMode = "newest" | "pinned" | "name";
export const SORT_LABELS: Record<SortMode, string> = { newest: "Nejnovejsi", pinned: "Pripnute prvni", name: "Nazev" };

/** Seconds since the epoch from either a number (s or ms) or an ISO string; 0 when unknown. */
export function toSeconds(v: number | string | undefined): number {
  if (typeof v === "number") return v > 1e11 ? v / 1000 : v;
  const ms = v ? Date.parse(v) : NaN;
  return Number.isFinite(ms) ? ms / 1000 : 0;
}

const PLURAL = (n: number, one: string, few: string, many: string): string => (n === 1 ? one : n >= 2 && n <= 4 ? few : many);

/** Czech relative time: 'pred chvili', 'pred 5 min', 'pred 3 hod', 'pred 2 dny', then a date. */
export function relativeTime(then: number | string | undefined, nowSeconds: number): string {
  const t = toSeconds(then);
  if (!t) return "";
  const d = Math.max(0, nowSeconds - t);
  if (d < 60) return "pred chvili";
  if (d < 3600) return `pred ${Math.floor(d / 60)} min`;
  if (d < 86400) return `pred ${Math.floor(d / 3600)} hod`;
  const days = Math.floor(d / 86400);
  if (days < 14) return `pred ${days} ${PLURAL(days, "dnem", "dny", "dny")}`;
  return new Date(t * 1000).toISOString().slice(0, 10);
}

/** Text of the provenance line, or '' when the item has no parents. */
export function provenance(item: Pick<DeckItem, "parent_ids">): string {
  const n = item.parent_ids.length;
  return n ? `vznikl z: ${n} polozek` : "";
}

/** Items matching the type (empty = all) and every word of the query in title, subtitle or tags. */
export function filterItems(items: DeckItem[], type: string, query: string): DeckItem[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return items.filter((it) => {
    if (type && it.type !== type) return false;
    const hay = `${it.title} ${it.subtitle ?? ""} ${it.tags.join(" ")}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

/** Sorted copy: newest (by update time), pinned first (then newest), or by name. */
export function sortItems(items: DeckItem[], mode: SortMode): DeckItem[] {
  const newest = (a: DeckItem, b: DeckItem) => toSeconds(b.updated_at) - toSeconds(a.updated_at);
  const out = [...items];
  if (mode === "name") out.sort((a, b) => a.title.localeCompare(b.title, "cs", { sensitivity: "base" }) || newest(a, b));
  else if (mode === "pinned") out.sort((a, b) => Number(b.pinned) - Number(a.pinned) || newest(a, b));
  else out.sort(newest);
  return out;
}

/** Type chips: 'all' first with the total, then the types by descending count then name. */
export function typeChips(byType: Record<string, number>, total: number): { type: string; count: number }[] {
  const rest = Object.entries(byType).map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));
  return [{ type: "", count: total }, ...rest];
}

/** Tags typed as 'a, b  c' to a clean unique list (max 12, 32 chars each). */
export function parseTags(text: string): string[] {
  const seen = new Set<string>();
  for (const raw of text.split(/[,\s]+/)) {
    const t = raw.trim().slice(0, 32);
    if (t) seen.add(t);
  }
  return [...seen].slice(0, 12);
}

/** Next focused tile index for an arrow / Home / End key in a grid of `cols` columns; the same index when nothing moves. */
export function gridMove(index: number, key: string, cols: number, count: number): number {
  if (count <= 0) return -1;
  const c = Math.max(1, cols);
  const to: Record<string, number> = { ArrowLeft: index - 1, ArrowRight: index + 1, ArrowUp: index - c, ArrowDown: index + c, Home: 0, End: count - 1 };
  const next = to[key];
  return next === undefined || next < 0 || next >= count ? index : next;
}

/** Glyph shape for a Deck item type. */
export function shapeOfType(type: string): string {
  return type === "file" ? "doc" : type;
}
