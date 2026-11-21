// frontend/src/views/memory_graph.ts
import { params } from "../core/params";
import { buildOrb, partsOf, setOrbEmphasis, setOrbLevel, type MemNode } from "./memory_orbs";
import { adjacency, cleanGraph } from "./memory_data";
import { createHoverGate } from "./memory_hover";
import { createFilters } from "./memory_filter_ctl";
import { alwaysLabel, syncLabels } from "./memory_labels";
import { buildMemoryUi } from "./memory_ui";
import type { Renderer } from "./types";

const HEAVY = 400; // above this many nodes: no labels, no particles

const idOf = (e: string | MemNode): string => (typeof e === "string" ? e : e.id);

/** data: `{nodes, links}` (see docs/protocol.md). 3d-force-graph is lazy-loaded; panel or full-screen "immersive" mode. */
export const renderMemoryGraph: Renderer = async (body, data) => {
  const { nodes, links } = cleanGraph(data);
  const heavy = nodes.length > HEAVY;
  let query = "";
  let hover: MemNode | null = null;
  let selected: MemNode | null = null;
  let neighbours = new Set<string>();
  let idleAt = 0;
  let fitted = false; // zoomToFit after the first settle only; "Vycentrovat" fits on demand
  let touched = false; // the user moved the camera before the first settle
  const adj = adjacency(nodes, links);
  const matches = (n: MemNode) => !query || `${n.label} ${n.project}`.toLowerCase().includes(query);

  const ui = buildMemoryUi({
    search: (q) => { query = q; refresh(); },
    deselect: () => select(null),
    toggleFilters: () => filters.toggle(),
    toggleFull: () => setFull(!root.classList.contains("mg-full")),
    close: () => body.closest(".vp")?.querySelector<HTMLElement>(".vp-x")?.click(),
    ask: (n) => (window as any).__friday?.send({ t: "chat", text: `Rekni mi o ${n.label}` }),
  });
  const root = ui.root;
  body.append(root);
  const { default: ForceGraph3D } = await import("3d-force-graph");
  const graph = new ForceGraph3D(ui.holder, { controlType: "orbit", rendererConfig: { alpha: true, antialias: !heavy } });
  graph.renderer().setPixelRatio(Math.min(devicePixelRatio, params.pixelRatio, 1.5));
  const controls = graph.controls() as any;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.55;
  controls.enableDamping = true;
  controls.zoomSpeed = 1.4;
  controls.minDistance = 30;
  controls.maxDistance = 4000;
  controls.zoomToCursor = true;

  const dim = (n: MemNode): number => {
    const focus = selected ?? hover;
    return !focus || n === focus || neighbours.has(n.id) ? 1 : selected ? 0.3 : 0.55; // hover only softens, selection focuses
  };
  const restyle = () => graph.graphData().nodes.forEach((n: any) => { const p = partsOf(n.__threeObj); if (p) { setOrbLevel(p, dim(n)); setOrbEmphasis(p, n === (selected ?? hover)); } });
  const light = (l: any) => { const f = selected ?? hover; return !!f && (idOf(l.source) === f.id || idOf(l.target) === f.id); };
  const labels = () => {
    if (heavy) return;
    syncLabels({ mode: filters.state().labels, nodes: graph.graphData().nodes, camera: graph.camera().position, hover, selected, matches, level: dim });
  };
  const fit = () => {
    const r = ui.holder.getBoundingClientRect();
    if (r.width > 10 && r.height > 10) graph.width(r.width).height(r.height);
  };
  const filters = createFilters({
    graph, controls, ui, nodes, links, adj, heavy, matches,
    focusId: () => selected?.id ?? null,
    syncLabels: labels,
    restyle,
    recenter: () => graph.zoomToFit(700, 30),
  });
  function refresh(): void {
    graph.nodeVisibility(matches as any).linkVisibility(((l: any) => matches(l.source) && matches(l.target)) as any);
    filters.status();
  }
  let styled: MemNode | null | undefined;
  let restyleFrame = 0;
  function setFocus(): void {
    const f = selected ?? hover;
    if (f === styled) return; // restyle only when the focus node actually changes
    styled = f;
    neighbours = f ? adj.get(f.id)! : new Set();
    graph.linkColor((l: any) => (light(l) ? "#ffffff" : "#4fd8ff")).linkOpacity(0.3).linkWidth((l: any) => (light(l) ? 1.4 : 0.35));
    if (!restyleFrame) restyleFrame = requestAnimationFrame(() => { restyleFrame = 0; restyle(); });
  }
  function select(n: MemNode | null): void {
    selected = n;
    ui.showCard(n, n ? adj.get(n.id)!.size : 0);
    setFocus();
    filters.onSelect();
    if (!n || n.x === undefined) return;
    const d = 1 + 85 / Math.max(1, Math.hypot(n.x, n.y!, n.z!));
    graph.cameraPosition({ x: n.x * d, y: n.y! * d, z: n.z! * d }, n as any, 900);
  }
  function setFull(on: boolean): void {
    root.classList.toggle("mg-full", on);
    const panel = body.closest<HTMLElement>(".vp");
    if (panel) panel.style.visibility = on ? "hidden" : "";
    if (on) document.body.insertBefore(root, document.getElementById("hud")); // below the HUD in stacking order
    else body.append(root);
    ui.setFull(on);
    fit();
  }

  graph
    .backgroundColor("rgba(0,0,0,0)")
    .showNavInfo(false)
    .nodeLabel(() => "") // the lib's tooltip is HTML; ours uses textContent
    .nodeThreeObject(((n: MemNode) => {
      const mode = filters.state().labels;
      return buildOrb(n, !heavy && (mode === "always" || (mode === "auto" && alwaysLabel(n))), heavy);
    }) as any)
    .linkDirectionalParticleWidth(1.3)
    .linkDirectionalParticleSpeed(0.005)
    .linkDirectionalParticleColor(() => "#bff4ff")
    .d3VelocityDecay(0.3)
    .onEngineStop(() => { if (!fitted && !touched) graph.zoomToFit(700, 30); fitted = true; }) // once; later settles never move the camera
    .onNodeHover(((n: MemNode | null) => { ui.tip(n?.label ?? null, px, py); gate.set(n); }) as any)
    .onNodeClick(((n: MemNode) => select(n)) as any)
    .onBackgroundClick(() => select(null));
  let px = 0, py = 0;
  const gate = createHoverGate<MemNode>((n) => { hover = n; setFocus(); });
  const stopAuto = () => { touched = true; controls.autoRotate = false; idleAt = performance.now(); };
  // Wheel stays inside the graph: no page scroll, no zoom of the 3D scene underneath.
  ui.holder.addEventListener("wheel", (e) => { e.preventDefault(); e.stopPropagation(); stopAuto(); gate.interact(); }, { passive: false });
  ui.holder.addEventListener("pointerup", () => gate.pointers(false));
  ui.holder.addEventListener("pointercancel", () => gate.pointers(false));
  ui.holder.addEventListener("pointermove", (e) => {
    const r = ui.holder.getBoundingClientRect();
    px = e.clientX - r.left; py = e.clientY - r.top;
    if (hover) ui.tip(hover.label, px, py);
  });
  ui.holder.addEventListener("pointerdown", () => { stopAuto(); gate.pointers(true); });

  // Idle auto-rotate and distance-based labels.
  const timer = setInterval(() => {
    if (!selected && filters.state().autoRotate && performance.now() - idleAt > 5000) controls.autoRotate = true;
    labels();
  }, 400);
  const onKey = (e: KeyboardEvent) => {
    if (e.key !== "Escape") return;
    if (!filters.closeIfOpen() && root.classList.contains("mg-full")) setFull(false);
  };
  addEventListener("keydown", onKey);
  const ro = new ResizeObserver(fit);
  ro.observe(ui.holder);
  filters.start();
  setFocus();
  fit();
  (root as any).__graph = graph; // test hook: screen position of nodes

  return () => {
    clearInterval(timer);
    gate.dispose();
    cancelAnimationFrame(restyleFrame);
    removeEventListener("keydown", onKey);
    filters.dispose();
    ro.disconnect();
    graph._destructor();
    root.remove();
  };
};
