// frontend/src/views/memory_ui.ts
import "./memory.css";
import { el } from "./dom";
import { KINDS_ORDER, KIND_COLOR, type Kind, type MemNode } from "./memory_orbs";

export interface UiHooks {
  search(query: string): void;
  deselect(): void;
  toggleFilters(): void;
  toggleFull(): void;
  close(): void;
  ask(node: MemNode): void;
}

export interface MemoryUi {
  root: HTMLElement;
  holder: HTMLElement;
  setStatus(text: string): void;
  setKey(shown: Record<Kind, number>, enabled: Record<Kind, boolean>): void;
  setFiltersOpen(on: boolean): void;
  mountDrawer(drawer: HTMLElement): void;
  setFull(on: boolean): void;
  showCard(node: MemNode | null, links: number): void;
  tip(text: string | null, x: number, y: number): void;
}

const ICON_FULL = "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5";
const ICON_GEAR = ((): string => {
  const ring = (r: number) => `M${12 + r} 12a${r} ${r} 0 1 0-${2 * r} 0a${r} ${r} 0 1 0 ${2 * r} 0`;
  const teeth = Array.from({ length: 8 }, (_, i) => {
    const a = (i * Math.PI) / 4, c = Math.cos(a), s = Math.sin(a);
    return `M${(12 + 6.6 * c).toFixed(2)} ${(12 + 6.6 * s).toFixed(2)}L${(12 + 9.4 * c).toFixed(2)} ${(12 + 9.4 * s).toFixed(2)}`;
  });
  return [ring(2.8), ring(6.6), ...teeth].join("");
})();

function icon(path: string): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "22");
  svg.setAttribute("height", "22");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", path);
  svg.append(p);
  return svg;
}

function button(cls: string, title: string, child?: Node): HTMLButtonElement {
  const b = el("button", cls);
  b.type = "button";
  b.title = title;
  b.setAttribute("aria-label", title);
  if (child) b.append(child);
  return b;
}

export function buildMemoryUi(hooks: UiHooks): MemoryUi {
  const root = el("div", "mg");
  const holder = el("div", "mg-canvas");
  const search = el("input", "mg-search");
  search.type = "search";
  search.placeholder = "Hledat v pameti...";
  search.autocomplete = "off";
  search.oninput = () => hooks.search(search.value.trim().toLowerCase());
  const status = el("div", "mg-status");
  const gear = button("mg-btn mg-gear", "Filtry a zobrazeni", icon(ICON_GEAR));
  gear.setAttribute("aria-expanded", "false");
  gear.onclick = () => hooks.toggleFilters();
  const full = button("mg-btn mg-fs", "Cela obrazovka", icon(ICON_FULL));
  full.onclick = () => hooks.toggleFull();
  const close = button("mg-btn mg-close", "Zavrit", icon("M6 6l12 12M18 6L6 18"));
  close.onclick = () => hooks.close();
  const bar = el("div", "mg-bar");
  const barRow = el("div", "mg-bar-row");
  barRow.append(search, gear, full, close);
  bar.append(barRow, status);

  const key = el("div", "mg-key");
  key.setAttribute("aria-hidden", "true");
  const keyItems = Object.fromEntries(
    KINDS_ORDER.map((kind) => {
      const item = el("span", "mg-key-i");
      const dot = el("i", "mg-dot");
      dot.style.setProperty("--k", KIND_COLOR[kind]);
      const text = el("span");
      item.append(dot, text);
      key.append(item);
      return [kind, { item, text }];
    }),
  ) as Record<Kind, { item: HTMLElement; text: HTMLElement }>;

  const card = el("aside", "mg-card");
  card.hidden = true;
  const tip = el("div", "mg-tip");
  tip.hidden = true;
  root.append(holder, bar, key, card, tip);

  let current: MemNode | null = null;
  return {
    root,
    holder,
    setStatus: (text) => (status.textContent = text),
    setKey(shown, enabled) {
      for (const kind of KINDS_ORDER) {
        keyItems[kind].item.hidden = !enabled[kind];
        keyItems[kind].text.textContent = `${kind} ${shown[kind]}`;
      }
    },
    setFiltersOpen(on) {
      gear.classList.toggle("on", on);
      gear.setAttribute("aria-expanded", String(on));
    },
    mountDrawer: (drawer) => root.append(drawer),
    setFull(on) {
      full.title = on ? "Zpet do panelu" : "Cela obrazovka";
      full.classList.toggle("on", on);
    },
    showCard(node, links) {
      current = node;
      card.hidden = !node;
      if (!node) return;
      const ask = button("mg-ask", "Zeptat se Friday");
      ask.append(el("span", "", "Zeptat se Friday"));
      ask.onclick = () => current && hooks.ask(current);
      const x = button("mg-card-x", "Zavrit kartu", icon("M6 6l12 12M18 6L6 18"));
      x.onclick = () => hooks.deselect();
      const kind = el("span", "mg-kind", node.kind);
      kind.style.setProperty("--k", KIND_COLOR[node.kind]);
      const rows = [el("div", "mg-row", `Projekt: ${node.project || "-"}`), el("div", "mg-row", `Spojeni: ${links}`)];
      if (node.ts > 0) rows.push(el("div", "mg-row", `Cas: ${new Date(node.ts).toLocaleString("cs-CZ")}`));
      card.replaceChildren(x, kind, el("h3", "mg-label", node.label), ...rows, ask);
    },
    tip(text, x, y) {
      tip.hidden = !text;
      if (!text) return;
      tip.textContent = text;
      tip.style.left = `${x + 14}px`;
      tip.style.top = `${y + 14}px`;
    },
  };
}
