// frontend/src/views/markdown.ts
import "./content.css";
import { el, safeUrl } from "./dom";
import type { Renderer } from "./types";

/** Inline markdown -> DOM nodes. Every text run goes through textContent; raw HTML stays literal text. */
function inline(parent: HTMLElement, src: string): void {
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(\[[^\]]+\]\([^)\s]+\))/g;
  let last = 0;
  for (const m of src.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) parent.append(document.createTextNode(src.slice(last, i)));
    const tok = m[0];
    if (m[1]) parent.append(el("code", "", tok.slice(1, -1)));
    else if (m[2]) parent.append(el("strong", "", tok.slice(2, -2)));
    else if (m[3]) parent.append(el("em", "", tok.slice(1, -1)));
    else {
      const [, label, href] = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok) ?? [];
      const url = safeUrl(href);
      if (url) {
        const a = el("a", "", label);
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        parent.append(a);
      } else parent.append(document.createTextNode(tok));
    }
    last = i + tok.length;
  }
  if (last < src.length) parent.append(document.createTextNode(src.slice(last)));
}

function list(lines: string[], ordered: boolean): HTMLElement {
  const l = el(ordered ? "ol" : "ul");
  for (const ln of lines) {
    const li = el("li");
    inline(li, ln.replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*+]\s+/, ""));
    l.append(li);
  }
  return l;
}

/** Block-level pass: headings, fenced code, lists, quotes, rules, paragraphs. */
export function markdownToDom(text: string): HTMLElement {
  const root = el("div", "v-md");
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  const isBlockStart = (s: string) => /^(#{1,6}\s|```|>\s?|\s*[-*+]\s|\s*\d+[.)]\s|---+\s*$)/.test(s);
  while (i < lines.length) {
    const ln = lines[i];
    let m: RegExpExecArray | null;
    if (!ln.trim()) { i++; continue; }
    if (ln.startsWith("```")) {
      const buf: string[] = [];
      for (i++; i < lines.length && !lines[i].startsWith("```"); i++) buf.push(lines[i]);
      i++;
      root.append(el("pre", "", buf.join("\n")));
    } else if ((m = /^(#{1,6})\s+(.*)$/.exec(ln))) {
      const h = el(`h${m[1].length}` as "h1");
      inline(h, m[2]);
      root.append(h);
      i++;
    } else if (/^---+\s*$/.test(ln)) {
      root.append(el("hr"));
      i++;
    } else if (/^>\s?/.test(ln)) {
      const q = el("blockquote");
      const buf: string[] = [];
      for (; i < lines.length && /^>\s?/.test(lines[i]); i++) buf.push(lines[i].replace(/^>\s?/, ""));
      inline(q, buf.join(" "));
      root.append(q);
    } else if (/^\s*[-*+]\s/.test(ln) || /^\s*\d+[.)]\s/.test(ln)) {
      const ordered = /^\s*\d/.test(ln);
      const re = ordered ? /^\s*\d+[.)]\s/ : /^\s*[-*+]\s/;
      const buf: string[] = [];
      for (; i < lines.length && re.test(lines[i]); i++) buf.push(lines[i]);
      root.append(list(buf, ordered));
    } else {
      const buf: string[] = [];
      for (; i < lines.length && lines[i].trim() && (buf.length === 0 || !isBlockStart(lines[i])); i++) buf.push(lines[i]);
      const p = el("p");
      inline(p, buf.join(" "));
      root.append(p);
    }
  }
  return root;
}

/** data: `{text: string}` markdown source. */
export const renderMarkdown: Renderer = (body, data) => {
  body.append(markdownToDom(String(data?.text ?? "")));
};
