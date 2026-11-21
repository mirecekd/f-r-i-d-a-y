// frontend/src/views/memory_drawer_ui.ts
import { el } from "./dom";

export interface Section {
  root: HTMLElement;
  body: HTMLElement;
}

export function section(title: string): Section {
  const root = el("section", "mgf-sec");
  const body = el("div", "mgf-body");
  root.append(el("h4", "mgf-h", title), body);
  return { root, body };
}

export function action(label: string, onClick: () => void, cls = ""): HTMLButtonElement {
  const b = el("button", `mgf-act ${cls}`.trim(), label);
  b.type = "button";
  b.onclick = onClick;
  return b;
}

/** Switch row: a button with role=switch so it is keyboard and screen reader friendly. */
export function toggle(label: string, count: number | null, on: boolean, onChange: (on: boolean) => void, color?: string): HTMLButtonElement {
  const b = el("button", "mgf-sw");
  b.type = "button";
  b.setAttribute("role", "switch");
  b.setAttribute("aria-checked", String(on));
  if (color) {
    const dot = el("i", "mg-dot");
    dot.style.setProperty("--k", color);
    b.append(dot);
  }
  b.append(el("span", "mgf-sw-l", label));
  if (count !== null) b.append(el("span", "mgf-n", String(count)));
  b.append(el("span", "mgf-knob"));
  b.onclick = () => onChange(!on);
  return b;
}

export function segmented<T extends string>(options: [T, string][], value: T, onChange: (v: T) => void, name: string): HTMLElement {
  const g = el("div", "mgf-seg");
  g.setAttribute("role", "group");
  g.setAttribute("aria-label", name);
  for (const [v, label] of options) {
    const b = el("button", v === value ? "on" : "", label);
    b.type = "button";
    b.setAttribute("aria-pressed", String(v === value));
    b.onclick = () => onChange(v);
    g.append(b);
  }
  return g;
}

export const row = (...kids: HTMLElement[]): HTMLElement => {
  const r = el("div", "mgf-row");
  r.append(...kids);
  return r;
};
