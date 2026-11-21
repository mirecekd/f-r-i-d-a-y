// frontend/src/views/file_icon.ts
import "./file_card.css";
import { el } from "./dom";

const NS = "http://www.w3.org/2000/svg";
const BASE = "M6 2h8l5 5v15H6z M14 2v5h5";
const GLYPH: Record<string, string> = {
  pdf: "M9 15h6 M9 18h4",
  docx: "M9 12h7 M9 15h7 M9 18h5",
  odt: "M9 12h7 M9 15h7 M9 18h5",
  rtf: "M9 12h7 M9 15h7 M9 18h5",
  text: "M9 12h7 M9 15h7 M9 18h5",
  markdown: "M9 12h7 M9 15h7 M9 18h5",
  xlsx: "M8 11h9 M8 15h9 M8 19h9 M12 11v8",
  csv: "M8 11h9 M8 15h9 M8 19h9 M12 11v8",
  code: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  json: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  yaml: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  toml: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  xml: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  html: "M10 12l-2 3 2 3 M15 12l2 3-2 3",
  zip: "M12 8v2 M12 12v2 M12 16v3",
  epub: "M8 11h8 M8 14h8 M8 17h5",
  audio: "M11 18V12l5-1v6 M9.5 18a1.5 1.5 0 100 .01 M14.5 17a1.5 1.5 0 100 .01",
  video: "M9 12l6 3.5-6 3.5z",
};

/** Inline SVG document icon; the glyph depends on the kind (nothing is fetched). */
export function fileIcon(kind: string): SVGSVGElement {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "28");
  svg.setAttribute("height", "28");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.6");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", `${BASE} ${GLYPH[kind] ?? "M9 14h6 M9 17h6"}`);
  svg.append(path);
  return svg;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
}

/** Chat bubble chip: icon, name and size. */
export function fileChip(kind: string, name: string, size: number): HTMLElement {
  const chip = el("div", "file-chip");
  const label = el("div", "file-chip-text");
  label.append(el("div", "file-chip-name", name), el("div", "file-chip-meta", `${kind.toUpperCase()} - ${formatSize(size)}`));
  chip.append(fileIcon(kind), label);
  return chip;
}
