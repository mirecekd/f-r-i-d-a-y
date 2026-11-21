// frontend/src/views/memory_search_ctl.ts
import { buildHitsPanel } from "./memory_hits";
import { highlightIds, orbLevel, type SearchState } from "./memory_hits_logic";
import type { MemoryUi } from "./memory_ui";
import type { MemNode } from "./memory_orbs";

export interface SearchCtx {
  state: SearchState | null;
  nodes: MemNode[];
  ui: MemoryUi;
  graph: any;
  select(n: MemNode | null): void;
  cancel(): void;
}

/** Query-focused view of the graph: which orbs are results, how the rest recedes, the hits list and the one-time camera move. */
export function createSearchView(c: SearchCtx) {
  const byId = new Map(c.nodes.map((n) => [n.id, n]));
  const ids = c.state ? highlightIds(c.state.highlight, (id) => byId.has(id)) : [];
  const set = new Set(ids);
  const panel = buildHitsPanel({
    pick: (id) => { const n = byId.get(id); if (n) c.select(n); },
    cancel: c.cancel,
  });
  if (c.state) {
    panel.set(c.state, c.state.hits.filter((h) => byId.has(h.id)));
    c.ui.mountHits(panel.root);
    c.ui.setSearchText(c.state.query);
  }
  return {
    active: !!c.state,
    isResult: (n: MemNode) => set.has(n.id),
    level: (n: MemNode, base: number, inFocus: boolean) => orbLevel(base, set.size > 0, set.has(n.id), inFocus),
    setActive: (id: string | null) => panel.setActive(id),
    /** First settle of the layout: fly to the best hit, then fit the result subset. False when there is nothing to show. */
    settled(): boolean {
      const best = byId.get(ids[0] ?? "");
      if (!best) return false;
      const g = c.graph;
      if (best.x !== undefined) {
        const d = 1 + 85 / Math.max(1, Math.hypot(best.x, best.y!, best.z!));
        g.cameraPosition({ x: best.x * d, y: best.y! * d, z: best.z! * d }, best, 700);
      }
      if (ids.length > 1) window.setTimeout(() => g.zoomToFit(900, 50, (n: MemNode) => set.has(n.id)), 760);
      return true;
    },
  };
}
