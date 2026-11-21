// frontend/src/views/memory_filters_apply.ts
import type { FilterState, TimeRange } from "./memory_filters";
import { KINDS_ORDER, type Kind, type MemLink, type MemNode } from "./memory_orbs";

export const idOf = (e: string | MemNode): string => (typeof e === "string" ? e : e.id);

export interface FilterResult {
  nodes: MemNode[];
  links: MemLink[];
  kindCounts: Record<Kind, number>;
}

/** What the drawer lists: distinct projects and link kinds with their totals. */
export interface DataStats {
  projects: [string, number][];
  linkKinds: [string, number][];
}

export function dataStats(nodes: MemNode[], links: MemLink[]): DataStats {
  const count = (items: string[]): [string, number][] => {
    const m = new Map<string, number>();
    for (const i of items) m.set(i, (m.get(i) ?? 0) + 1);
    return [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  };
  return { projects: count(nodes.map((n) => n.project)), linkKinds: count(links.map((l) => l.kind)) };
}

export function sinceOf(range: TimeRange, now: number): number {
  const day = 864e5;
  if (range === "30d") return now - 30 * day;
  if (range === "7d") return now - 7 * day;
  if (range === "24h") return now - day;
  if (range === "today") return new Date(now).setHours(0, 0, 0, 0);
  return 0;
}

function reach(adj: Map<string, Set<string>>, from: string, depth: number): Set<string> {
  const seen = new Set([from]);
  let edge = [from];
  for (let d = 0; d < depth; d++) {
    const next: string[] = [];
    for (const id of edge) for (const o of adj.get(id) ?? []) if (!seen.has(o)) { seen.add(o); next.push(o); }
    edge = next;
  }
  return seen;
}

/**
 * Pure filter pipeline: project, time and selection neighbourhood define the candidates; a node is an orphan when none of
 * its enabled link kinds reaches another candidate (so hiding a type never turns its neighbours into orphans); then type filter.
 * Project nodes stay as anchors.
 */
export function applyFilters(s: FilterState, nodes: MemNode[], links: MemLink[], adj: Map<string, Set<string>>, focusId: string | null, now: number): FilterResult {
  const since = sinceOf(s.time, now);
  const hiddenProjects = new Set(s.hiddenProjects);
  const hiddenLinks = new Set(s.hiddenLinks);
  const near = s.focusDepth > 0 && focusId ? reach(adj, focusId, s.focusDepth) : null;
  const candidates = nodes.filter((n) => !hiddenProjects.has(n.project) && (n.ts === 0 || n.ts >= since) && (!near || near.has(n.id)));
  const candidateIds = new Set(candidates.map((n) => n.id));
  const linked = new Set<string>();
  for (const l of links) {
    if (hiddenLinks.has(l.kind) || !candidateIds.has(idOf(l.source)) || !candidateIds.has(idOf(l.target))) continue;
    linked.add(idOf(l.source));
    linked.add(idOf(l.target));
  }
  const pool = candidates.filter((n) => s.kinds[n.kind] && (!s.hideOrphans || linked.has(n.id) || n.kind === "project" || n.id === focusId));
  const kindCounts = Object.fromEntries(KINDS_ORDER.map((k) => [k, 0])) as Record<Kind, number>;
  for (const n of pool) kindCounts[n.kind]++;
  const final = new Set(pool.map((n) => n.id));
  const shown = links.filter((l) => !hiddenLinks.has(l.kind) && final.has(idOf(l.source)) && final.has(idOf(l.target)));
  return { nodes: pool, links: shown, kindCounts };
}
