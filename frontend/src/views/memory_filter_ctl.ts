// frontend/src/views/memory_filter_ctl.ts
import type { ForceGraph3DInstance } from "3d-force-graph";
import type { Object3D } from "three";
import { buildDrawer } from "./memory_drawer";
import { defaultFilters, loadFilters, saveFilters, withPreset, type FilterState } from "./memory_filters";
import { applyFilters, dataStats, type FilterResult } from "./memory_filters_apply";
import type { MemoryUi } from "./memory_ui";
import { KINDS_ORDER, partsOf, type Kind, type MemLink, type MemNode } from "./memory_orbs";

export interface FilterCtx {
  graph: ForceGraph3DInstance;
  controls: { autoRotate: boolean };
  ui: MemoryUi;
  nodes: MemNode[];
  links: MemLink[];
  adj: Map<string, Set<string>>;
  heavy: boolean;
  matches(n: MemNode): boolean;
  focusId(): string | null;
  syncLabels(): void;
  restyle(): void;
  recenter(): void;
}

const DATA_KEYS = ["kinds", "hiddenProjects", "time", "hiddenLinks", "hideOrphans", "focusDepth"];
const FLAT_RADIUS = 4.5;
const DEBOUNCE_MS = 80;
const SETTLE_MS = 1500;

type Pinnable = MemNode & { fx?: number; fy?: number; fz?: number };

/** Owns the filter state, applies it to the graph without a rebuild (same node objects keep their positions) and drives the drawer. */
export function createFilters(c: FilterCtx) {
  let fs = loadFilters();
  const totals = Object.fromEntries(KINDS_ORDER.map((k) => [k, c.nodes.filter((n) => n.kind === k).length])) as Record<Kind, number>;
  let result: FilterResult = { nodes: c.nodes, links: c.links, kindCounts: totals };
  let first = true;
  let debounce = 0;
  let unpin = 0;
  let open = false;

  const drawer = buildDrawer(
    {
      patch: (p) => patch(p),
      preset: (id) => replace(withPreset(fs, id)),
      reset: () => replace(defaultFilters()),
      solo: (project) => patch({ hiddenProjects: dataStats(c.nodes, c.links).projects.map((p) => p[0]).filter((p) => p !== project) }),
      recenter: c.recenter,
      close: () => setOpen(false),
    },
    dataStats(c.nodes, c.links),
    totals,
  );
  c.ui.mountDrawer(drawer.root);

  function setOpen(on: boolean): void {
    open = on;
    drawer.root.classList.toggle("open", on);
    c.ui.setFiltersOpen(on);
    if (on) drawer.sync(fs, result);
  }
  const sizeOne = (group: Object3D | undefined, n: MemNode): void => {
    const p = partsOf(group);
    if (!p || !group) return;
    const flat = FLAT_RADIUS * (n.kind === "project" ? 1.5 : 1);
    group.scale.setScalar(fs.nodeSize * (fs.sizeByWeight ? 1 : flat / p.radius));
  };
  function status(): void {
    const shown = result.nodes.filter(c.matches).length;
    c.ui.setStatus(`zobrazeno ${shown} / ${c.nodes.length} uzlu a ${result.links.length} vazeb`);
    c.ui.setKey(result.kindCounts, fs.kinds);
  }
  function display(): void {
    c.controls.autoRotate = fs.autoRotate;
    c.graph.linkDirectionalParticles(c.heavy || !fs.particles ? 0 : 2);
    for (const n of c.graph.graphData().nodes as any[]) sizeOne(n.__threeObj, n);
    c.graph.cooldownTicks(fs.frozen ? 0 : Infinity);
    c.syncLabels();
  }
  function apply(): void {
    result = applyFilters(fs, c.nodes, c.links, c.adj, c.focusId(), Date.now());
    const keep = new Set(result.nodes.map((n) => n.id));
    for (const n of c.nodes as Pinnable[]) {
      if (n.x !== undefined) { n.fx = n.x; n.fy = n.y; n.fz = n.z; continue; }
      if (!keep.has(n.id)) continue;
      const at = [...(c.adj.get(n.id) ?? [])].map((id) => c.nodes.find((o) => o.id === id)).find((o) => o?.x !== undefined);
      if (at) { n.x = at.x! + Math.random() * 6 - 3; n.y = at.y! + Math.random() * 6 - 3; n.z = at.z! + Math.random() * 6 - 3; }
    }
    c.graph.cooldownTime(first ? 6000 : SETTLE_MS);
    first = false;
    c.graph.graphData({ nodes: result.nodes, links: result.links as any });
    clearTimeout(unpin);
    unpin = window.setTimeout(() => { for (const n of c.nodes as Pinnable[]) { delete n.fx; delete n.fy; delete n.fz; } }, fs.frozen ? 100 : SETTLE_MS + 300);
    c.graph.nodeVisibility(c.matches as any).linkVisibility(((l: any) => c.matches(l.source) && c.matches(l.target)) as any);
    display();
    window.setTimeout(() => { display(); c.restyle(); }, 60);
    status();
    drawer.sync(fs, result);
  }
  function commit(next: FilterState, data: boolean): void {
    fs = next;
    saveFilters(fs);
    drawer.sync(fs, result);
    if (data) { clearTimeout(debounce); debounce = window.setTimeout(apply, DEBOUNCE_MS); }
    else { display(); if (!fs.frozen) c.graph.d3ReheatSimulation(); }
  }
  function patch(p: Partial<FilterState>): void {
    const data = Object.keys(p).some((k) => DATA_KEYS.includes(k));
    commit({ ...fs, ...p, preset: data ? "custom" : fs.preset }, data);
  }
  function replace(next: FilterState): void {
    commit(next, true);
    display();
  }
  const onDown = (e: PointerEvent): void => {
    const t = e.target as Element | null;
    if (open && t && !drawer.root.contains(t) && !t.closest(".mg-gear")) setOpen(false);
  };
  document.addEventListener("pointerdown", onDown, true);

  return {
    state: () => fs,
    start: apply,
    sizeOne,
    status,
    toggle: () => setOpen(!open),
    /** Esc handler: true when it closed the drawer. */
    closeIfOpen(): boolean {
      if (!open) return false;
      setOpen(false);
      return true;
    },
    onSelect(): void {
      if (fs.focusDepth > 0) commit(fs, true);
    },
    dispose(): void {
      clearTimeout(debounce);
      clearTimeout(unpin);
      document.removeEventListener("pointerdown", onDown, true);
    },
  };
}
