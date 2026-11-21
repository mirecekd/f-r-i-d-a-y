// frontend/src/views/memory_hits.ts
import "./memory_hits.css";
import { el } from "./dom";
import { glyphIcon } from "./memory_glyphs";
import { KIND_COLOR, type Kind } from "./memory_orbs";
import { countText, relTime, scoreRatio, truncate, type Hit, type SearchState } from "./memory_hits_logic";

export interface HitsHooks {
  pick(id: string): void;
  cancel(): void;
}

export interface HitsPanel {
  root: HTMLElement;
  /** Fills the panel; `hits` must already be limited to nodes that exist in the graph. */
  set(state: SearchState, hits: Hit[], now?: number): void;
  setActive(id: string | null): void;
}

const CHEVRON = "M6 9l6 6 6-6";

function chevron(): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", width: "20", height: "20", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round" })) svg.setAttribute(k, v);
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", CHEVRON);
  svg.append(p);
  return svg;
}

function row(h: Hit, best: number, now: number): HTMLElement {
  const r = el("div", "mg-hit");
  r.setAttribute("role", "option");
  r.tabIndex = -1;
  r.dataset.id = h.id;
  const bar = el("span", "mg-hit-bar");
  bar.title = `skore ${h.score.toFixed(2)}`;
  const fill = el("i");
  fill.style.width = `${Math.round(scoreRatio(h.score, best) * 100)}%`;
  bar.append(fill);
  const meta = el("span", "mg-hit-meta");
  const when = relTime(h.ts, now);
  if (when) meta.append(el("span", "mg-hit-time", when));
  if (h.project) meta.append(el("span", "mg-chip", h.project));
  const top = el("span", "mg-hit-top");
  top.append(glyphIcon(h.kind as Kind, KIND_COLOR[h.kind as Kind]), el("span", "mg-hit-label", truncate(h.label)));
  r.append(top, bar, meta);
  if (h.snippet) r.append(el("span", "mg-hit-snip", h.snippet));
  return r;
}

/** Collapsible result list: query chip with count, summary, up to 12 keyboard-reachable rows. All text via textContent. */
export function buildHitsPanel(hooks: HitsHooks): HitsPanel {
  const root = el("aside", "mg-hits");
  root.hidden = true;
  root.setAttribute("aria-label", "Vysledky hledani v pameti");
  const toggle = el("button", "mg-hits-toggle");
  toggle.type = "button";
  toggle.title = "Sbalit / rozbalit vysledky";
  toggle.setAttribute("aria-expanded", "true");
  toggle.append(chevron());
  toggle.onclick = () => {
    const min = root.classList.toggle("mg-hits-min");
    toggle.setAttribute("aria-expanded", String(!min));
  };
  const chip = el("span", "mg-qchip");
  const chipQ = el("span", "mg-qchip-q");
  const chipN = el("span", "mg-qchip-n");
  chip.append(chipQ, chipN);
  const cancel = el("button", "mg-cancel", "Zrusit hledani");
  cancel.type = "button";
  cancel.onclick = () => hooks.cancel();
  const head = el("div", "mg-hits-head");
  head.append(toggle, chip, cancel);
  const summary = el("div", "mg-hits-sum");
  const list = el("div", "mg-hit-list");
  list.setAttribute("role", "listbox");
  root.append(head, summary, list);

  const rows = (): HTMLElement[] => [...list.querySelectorAll<HTMLElement>(".mg-hit")];
  const focusRow = (r: HTMLElement | undefined): void => {
    if (!r) return;
    rows().forEach((x) => (x.tabIndex = x === r ? 0 : -1));
    r.focus();
  };
  list.addEventListener("click", (e) => {
    const r = (e.target as Element).closest<HTMLElement>(".mg-hit");
    if (r?.dataset.id) hooks.pick(r.dataset.id);
  });
  list.addEventListener("keydown", (e) => {
    const all = rows();
    const i = all.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") focusRow(all[Math.min(all.length - 1, i + 1)]);
    else if (e.key === "ArrowUp") focusRow(all[Math.max(0, i - 1)]);
    else if (e.key === "Home") focusRow(all[0]);
    else if (e.key === "End") focusRow(all[all.length - 1]);
    else if ((e.key === "Enter" || e.key === " ") && i >= 0) hooks.pick(all[i].dataset.id!);
    else return;
    e.preventDefault();
    e.stopPropagation();
  });

  return {
    root,
    set(state, hits, now = Date.now()) {
      root.hidden = false;
      chipQ.textContent = state.query;
      chipN.textContent = countText(hits.length);
      summary.textContent = state.summary;
      summary.hidden = !state.summary;
      const best = Math.max(0, ...hits.map((h) => h.score));
      list.replaceChildren(...hits.map((h) => row(h, best, now)));
      const first = rows()[0];
      if (first) first.tabIndex = 0;
    },
    setActive(id) {
      for (const r of rows()) r.setAttribute("aria-selected", String(r.dataset.id === id));
    },
  };
}
