// frontend/src/views/diagram.ts
import "./content.css";
import { el } from "./dom";
import type { Renderer } from "./types";

let seq = 0;

/** data: `{code: string}` mermaid source. Mermaid is lazy-loaded; strict security level sanitizes labels. */
export const renderDiagram: Renderer = async (body, data) => {
  const code = String(data?.code ?? "");
  const holder = el("div", "v-diagram");
  holder.append(el("div", "vp-loading", "rendering diagram..."));
  body.append(holder);
  const { default: mermaid } = await import("mermaid");
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "dark",
    themeVariables: { primaryColor: "#06324a", primaryTextColor: "#cfefff", lineColor: "#4fd8ff", primaryBorderColor: "#4fd8ff" },
  });
  try {
    const { svg } = await mermaid.render(`mmd-${++seq}`, code);
    // Mermaid output is generated SVG (strict mode runs DOMPurify over it), parsed as an image document.
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    const node = doc.documentElement;
    if (node.nodeName.toLowerCase() !== "svg") throw new Error("invalid svg");
    holder.replaceChildren(document.importNode(node, true));
  } catch (e) {
    document.getElementById("dmmd-" + seq)?.remove();
    holder.replaceChildren(el("div", "vp-err", "diagram error: " + (e instanceof Error ? e.message : String(e))));
  }
};
