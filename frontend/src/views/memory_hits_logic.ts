// frontend/src/views/memory_hits_logic.ts
// Pure logic of the memory search result view: no DOM, no three.js (imported by the app and by tests/memhits.mjs).

export const MAX_HITS = 12;
export const LABEL_MAX = 60;
export const HL_DIM = 0.35; // opacity level of orbs that are not part of the result

export interface Hit {
  id: string;
  label: string;
  kind: string;
  score: number;
  snippet: string;
  ts: number;
  project: string;
}

export interface SearchState {
  query: string;
  highlight: string[];
  hits: Hit[];
  summary: string;
}

const KINDS = ["project", "session", "memory", "concept", "file"];

export function truncate(text: string, max = LABEL_MAX): string {
  const chars = Array.from(text);
  return chars.length > max ? chars.slice(0, max - 1).join("") + "\u2026" : text;
}

/** Czech relative time without diacritics: "pred 2 h", "vcera", "12. 11." (with the year when it is not the current one). */
export function relTime(ts: number, now: number = Date.now()): string {
  if (!(ts > 0)) return "";
  const diff = now - ts;
  if (diff < 0 || diff < 60e3) return "prave ted";
  if (diff < 3600e3) return `pred ${Math.floor(diff / 60e3)} min`;
  if (diff < 86400e3) return `pred ${Math.floor(diff / 3600e3)} h`;
  const day = (t: number) => { const d = new Date(t); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); };
  const days = Math.round((day(now) - day(ts)) / 86400e3);
  if (days <= 1) return "vcera";
  if (days < 7) return `pred ${days} dny`;
  const d = new Date(ts);
  const date = `${d.getDate()}. ${d.getMonth() + 1}.`;
  return d.getFullYear() === new Date(now).getFullYear() ? date : `${date} ${d.getFullYear()}`;
}

/** Bar fill 0..1 relative to the best hit (never below 4% so a weak hit still shows a stub). */
export function scoreRatio(score: number, best: number): number {
  return best > 0 ? Math.max(0.04, Math.min(1, score / best)) : 0.04;
}

const text = (v: unknown): string => (typeof v === "string" ? v : "");

/** Validates the wire payload: at most 12 hits, best score first (stable), unknown kinds become concepts. */
export function cleanHits(raw: unknown): Hit[] {
  if (!Array.isArray(raw)) return [];
  const hits: Hit[] = [];
  for (const h of raw) {
    if (!h || typeof h.id !== "string" || !h.id) continue;
    hits.push({
      id: h.id,
      label: text(h.label) || h.id,
      kind: KINDS.includes(h.kind) ? h.kind : "concept",
      score: Number.isFinite(Number(h.score)) ? Number(h.score) : 0,
      snippet: text(h.snippet),
      ts: Number(h.ts) || 0,
      project: text(h.project),
    });
  }
  return hits.map((h, i) => ({ h, i })).sort((a, b) => b.h.score - a.h.score || a.i - b.i).map((x) => x.h).slice(0, MAX_HITS);
}

/** Search state of a `memory_graph` payload, or null for the generic overview (no query, highlight or hits). */
export function parseSearch(data: any): SearchState | null {
  const query = text(data?.query).trim().slice(0, 200);
  const highlight: string[] = Array.isArray(data?.highlight) ? data.highlight.filter((x: unknown) => typeof x === "string") : [];
  const hits = cleanHits(data?.hits);
  if (!query && !highlight.length && !hits.length) return null;
  return { query, highlight, hits, summary: text(data?.summary).slice(0, 400) };
}

/** Highlight ids in relevance order, de-duplicated; ids that are not nodes of the dataset are ignored. */
export function highlightIds(highlight: string[], known: (id: string) => boolean): string[] {
  const seen = new Set<string>();
  return highlight.filter((id) => known(id) && !seen.has(id) && !!seen.add(id));
}

/** Opacity of an orb: result nodes keep the focus level, the rest recede to HL_DIM unless the hover/selection focus reaches them. */
export function orbLevel(base: number, hasHighlight: boolean, highlighted: boolean, inFocus: boolean): number {
  if (!hasHighlight || highlighted || inFocus) return base;
  return Math.min(base, HL_DIM);
}

/** "nic nenalezeno" / "1 vysledek" / "3 vysledky" / "12 vysledku". */
export function countText(n: number): string {
  return n <= 0 ? "nic nenalezeno" : n === 1 ? "1 vysledek" : n < 5 ? `${n} vysledky` : `${n} vysledku`;
}
