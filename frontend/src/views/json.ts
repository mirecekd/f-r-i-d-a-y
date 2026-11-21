// frontend/src/views/json.ts
import "./content.css";
import { el } from "./dom";
import type { Renderer } from "./types";

const OPEN_DEPTH = 2;

function leaf(v: unknown): HTMLElement {
  if (v === null) return el("span", "j-null", "null");
  if (typeof v === "string") return el("span", "j-str", JSON.stringify(v));
  if (typeof v === "number") return el("span", "j-num", String(v));
  if (typeof v === "boolean") return el("span", "j-bool", String(v));
  return el("span", "", String(v));
}

function node(key: string | null, v: unknown, depth: number): HTMLElement {
  const row = el("div", "j-row");
  const keyEl = key === null ? null : el("span", "j-key", key + ": ");
  if (typeof v !== "object" || v === null) {
    if (keyEl) row.append(keyEl);
    row.append(leaf(v));
    return row;
  }
  const isArr = Array.isArray(v);
  const entries: [string, unknown][] = isArr ? v.map((x, i) => [String(i), x]) : Object.entries(v);
  const [open, close] = isArr ? ["[", "]"] : ["{", "}"];
  const head = el("div", "j-head");
  const caret = el("span", "j-caret", "");
  const summary = el("span", "j-sum", `${open}${entries.length}${close}`);
  head.append(caret);
  if (keyEl) head.append(keyEl);
  head.append(summary);
  const kids = el("div", "j-kids");
  kids.append(...entries.map(([k, x]) => node(k, x, depth + 1)));
  const set = (o: boolean) => {
    row.classList.toggle("closed", !o);
    caret.textContent = o ? "\u25BE" : "\u25B8";
  };
  head.onclick = () => set(row.classList.contains("closed"));
  set(depth < OPEN_DEPTH);
  row.append(head, kids);
  return row;
}

/** data: `{value: any}` (falls back to the data object itself); collapsible tree. */
export const renderJson: Renderer = (body, data) => {
  const tree = el("div", "v-json");
  tree.append(node(null, data && "value" in data ? data.value : data, 0));
  body.append(tree);
};
