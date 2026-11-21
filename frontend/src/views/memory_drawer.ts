// frontend/src/views/memory_drawer.ts
import "./memory_filters.css";
import { el } from "./dom";
import { action, row, section, segmented, toggle } from "./memory_drawer_ui";
import { LABEL_MODES, PRESETS, TIME_RANGES, type FilterState } from "./memory_filters";
import type { DataStats, FilterResult } from "./memory_filters_apply";
import { KINDS_ORDER, KIND_COLOR, type Kind } from "./memory_orbs";

export interface DrawerHooks {
  patch(p: Partial<FilterState>): void;
  preset(id: (typeof PRESETS)[number][0]): void;
  reset(): void;
  solo(project: string): void;
  recenter(): void;
  close(): void;
}

export interface Drawer {
  root: HTMLElement;
  sync(s: FilterState, r: FilterResult): void;
}

export function buildDrawer(hooks: DrawerHooks, stats: DataStats, totals: Record<Kind, number>): Drawer {
  const root = el("aside", "mgf");
  root.id = "mg-filters";
  root.setAttribute("aria-label", "Filtry pameti");
  const head = el("div", "mgf-head");
  const x = action("Zavrit", hooks.close, "mgf-x");
  x.setAttribute("aria-label", "Zavrit filtry");
  head.append(el("strong", "", "Filtry"), x);

  const presets = section("Predvolby");
  const types = section("Typy");
  const projects = section("Projekty");
  const time = section("Cas");
  const links = section("Vztahy");
  const view = section("Zobrazeni");
  const projSearch = el("input", "mgf-q");
  projSearch.type = "search";
  projSearch.placeholder = "Hledat projekt...";
  projSearch.setAttribute("aria-label", "Hledat projekt");
  const projList = el("div", "mgf-list");
  projects.body.append(projSearch, projList);
  let last: FilterState | null = null;
  projSearch.oninput = () => last && fillProjects(last);

  function fillProjects(s: FilterState): void {
    const q = projSearch.value.trim().toLowerCase();
    const hidden = new Set(s.hiddenProjects);
    const items = stats.projects.filter(([p]) => p.toLowerCase().includes(q));
    projList.replaceChildren(
      ...items.map(([p, n]) => {
        const r = row(
          toggle(p || "(bez projektu)", n, !hidden.has(p), (on) => hooks.patch({ hiddenProjects: on ? s.hiddenProjects.filter((h) => h !== p) : [...s.hiddenProjects, p] })),
          action("Jen tento", () => hooks.solo(p), "mgf-solo"),
        );
        r.classList.add("mgf-prow");
        return r;
      }),
    );
  }

  function fill(s: FilterState): void {
    presets.body.replaceChildren(
      segmented((s.preset === "custom" ? [...PRESETS, ["custom", "Vlastni"]] : PRESETS) as [string, string][], s.preset, (v) => v !== "custom" && hooks.preset(v as (typeof PRESETS)[number][0]), "Predvolba"),
      action("Vychozi", hooks.reset),
    );
    const setKinds = (on: (k: Kind) => boolean) => hooks.patch({ kinds: Object.fromEntries(KINDS_ORDER.map((k) => [k, on(k)])) as Record<Kind, boolean> });
    types.body.replaceChildren(
      ...KINDS_ORDER.map((k) => toggle(k === "memory" ? "memory (myslenky)" : k, totals[k], s.kinds[k], (on) => hooks.patch({ kinds: { ...s.kinds, [k]: on } }), KIND_COLOR[k])),
      row(action("Vse", () => setKinds(() => true)), action("Nic", () => setKinds(() => false)), action("Jen projekty", () => setKinds((k) => k === "project"))),
    );
    fillProjects(s);
    time.body.replaceChildren(segmented(TIME_RANGES, s.time, (time) => hooks.patch({ time }), "Casovy rozsah"));
    const hiddenLinks = new Set(s.hiddenLinks);
    links.body.replaceChildren(
      ...stats.linkKinds.map(([k, n]) => toggle(k || "(bez druhu)", n, !hiddenLinks.has(k), (on) => hooks.patch({ hiddenLinks: on ? s.hiddenLinks.filter((h) => h !== k) : [...s.hiddenLinks, k] }))),
      toggle("Skryt osamele uzly", null, s.hideOrphans, (hideOrphans) => hooks.patch({ hideOrphans })),
      el("div", "mgf-lab", "Jen okoli vybraneho uzlu"),
      segmented<"0" | "1" | "2">([["0", "Vyp"], ["1", "1 skok"], ["2", "2 skoky"]], String(s.focusDepth) as "0", (v) => hooks.patch({ focusDepth: Number(v) as 0 | 1 | 2 }), "Okoli vybraneho"),
    );
    const size = el("input", "mgf-range");
    size.type = "range";
    size.min = "0.5";
    size.max = "2";
    size.step = "0.1";
    size.value = String(s.nodeSize);
    size.setAttribute("aria-label", "Velikost uzlu");
    size.oninput = () => hooks.patch({ nodeSize: Number(size.value) });
    view.body.replaceChildren(
      el("div", "mgf-lab", "Popisky"),
      segmented(LABEL_MODES, s.labels, (labels) => hooks.patch({ labels }), "Popisky"),
      toggle("Castice na vazbach", null, s.particles, (particles) => hooks.patch({ particles })),
      toggle("Velikost podle vahy", null, s.sizeByWeight, (sizeByWeight) => hooks.patch({ sizeByWeight })),
      toggle("Automaticke otaceni", null, s.autoRotate, (autoRotate) => hooks.patch({ autoRotate })),
      el("div", "mgf-lab", "Velikost uzlu"),
      size,
      toggle("Zamrazit rozlozeni", null, s.frozen, (frozen) => hooks.patch({ frozen })),
      action("Vycentrovat", hooks.recenter),
    );
  }

  const scroll = el("div", "mgf-scroll");
  scroll.append(presets.root, types.root, projects.root, time.root, links.root, view.root);
  root.append(head, scroll);
  return {
    root,
    sync(s) {
      last = s;
      fill(s);
    },
  };
}
