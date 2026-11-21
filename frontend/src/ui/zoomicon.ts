// frontend/src/ui/zoomicon.ts
export const GLASS_PATHS = ["M15.5 15.5L21 21", "M10.5 7.5v6M7.5 10.5h6"];
export const BACK_PATHS = ["M9 7L4 12l5 5M4 12h11a5 5 0 0 1 5 5"];

const SVG_NS = "http://www.w3.org/2000/svg";

/** Builds a 24x24 stroke icon from path data (and an optional circle) without innerHTML. */
export function icon(size: number, paths: string[], circle?: [number, number, number]): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  const attrs: Record<string, string> = { viewBox: "0 0 24 24", width: String(size), height: String(size), fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" };
  for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, v);
  if (circle) {
    const c = document.createElementNS(SVG_NS, "circle");
    c.setAttribute("cx", String(circle[0]));
    c.setAttribute("cy", String(circle[1]));
    c.setAttribute("r", String(circle[2]));
    svg.appendChild(c);
  }
  for (const d of paths) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d);
    svg.appendChild(p);
  }
  return svg;
}

