// frontend/src/views/code.ts
import "./content.css";
import { el } from "./dom";
import { highlight } from "./highlight";
import type { Renderer } from "./types";

/** data: `{code: string, lang?: string}`; monospace, light syntax highlighting, copy button. */
export const renderCode: Renderer = (body, data) => {
  const code = String(data?.code ?? "");
  const lang = String(data?.lang ?? "");
  const wrap = el("div", "v-code");
  const bar = el("div", "v-code-bar");
  bar.append(el("span", "v-lang", lang || "text"));
  const copy = el("button", "v-copy", "COPY");
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(code);
      copy.textContent = "COPIED";
    } catch {
      copy.textContent = "FAILED";
    }
    setTimeout(() => (copy.textContent = "COPY"), 1200);
  };
  bar.append(copy);
  const pre = el("pre");
  pre.append(highlight(code, lang));
  wrap.append(bar, pre);
  body.append(wrap);
};
