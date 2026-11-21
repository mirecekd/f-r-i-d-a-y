// frontend/src/views/file_card.ts
import "./file_card.css";
import { el, safeUrl } from "./dom";
import { fileIcon, formatSize } from "./file_icon";
import { renderTable } from "./table";
import type { Renderer } from "./types";

/** Hooks wired by ui/imagedrop.ts: the buttons send chat messages. */
export const fileCardActions = { chat: (_text: string): void => {} };

function section(title: string): HTMLElement {
  const s = el("div", "fc-sec");
  s.append(el("div", "fc-h", title));
  return s;
}

/**
 * data: `{id, name, kind, size, title, summary, meta, outline[], tables?: [{name, columns, rows}], text_excerpt,
 * truncated, download_url, note?}`. All text goes through textContent.
 */
export const renderFileCard: Renderer = (body, data) => {
  const name = String(data?.name ?? "soubor");
  const card = el("div", "v-filecard");
  const head = el("div", "fc-head");
  const titles = el("div", "fc-titles");
  titles.append(el("div", "fc-title", String(data?.title || name)), el("div", "fc-sub", `${name} - ${formatSize(Number(data?.size) || 0)}`));
  const badge = el("span", `fc-badge k-${String(data?.kind)}`, String(data?.kind ?? "file"));
  head.append(fileIcon(String(data?.kind)), titles, badge);
  card.append(head);

  const metaBits = Object.entries(data?.meta ?? {}).filter(([, v]) => typeof v === "string" || typeof v === "number").slice(0, 5);
  if (metaBits.length) card.append(el("div", "fc-meta", metaBits.map(([k, v]) => `${k}: ${v}`).join("  |  ")));
  if (data?.note) card.append(el("div", "fc-note", String(data.note)));
  if (data?.summary) card.append(el("p", "fc-summary", String(data.summary)));

  const excerpt = el("pre", "fc-excerpt", String(data?.text_excerpt ?? ""));
  const outline: string[] = Array.isArray(data?.outline) ? data.outline.map(String) : [];
  if (outline.length) {
    const sec = section(data?.kind === "zip" ? "Obsah" : "Osnova");
    const list = el("ul", "fc-outline");
    for (const h of outline) {
      const li = el("li", "", h);
      li.onclick = () => {
        const at = excerpt.textContent?.indexOf(h) ?? -1;
        if (at < 0) return;
        excerpt.scrollTop = (at / Math.max(excerpt.textContent!.length, 1)) * excerpt.scrollHeight;
      };
      list.append(li);
    }
    sec.append(list);
    card.append(sec);
  }

  for (const t of Array.isArray(data?.tables) ? data.tables : []) {
    const sec = section(String(t?.name ?? "Tabulka"));
    const holder = el("div", "fc-table");
    try {
      renderTable(holder, t);
    } catch (e) {
      holder.textContent = (e as Error).message;
    }
    sec.append(holder);
    card.append(sec);
  }

  if (excerpt.textContent) {
    const sec = section(data?.truncated ? "Text (zacatek)" : "Text");
    sec.append(excerpt);
    card.append(sec);
  }

  const bar = el("div", "fc-actions");
  const href = safeUrl(data?.download_url);
  if (href) {
    const a = el("a", "fc-btn", "Stahnout");
    a.href = href;
    a.setAttribute("download", name);
    bar.append(a);
  }
  const more = el("button", "fc-btn", "Precist dal");
  more.onclick = () => fileCardActions.chat(`Precti dalsi cast souboru ${name}`);
  const sum = el("button", "fc-btn", "Shrnout");
  sum.onclick = () => fileCardActions.chat(`Shrn soubor ${name}`);
  bar.append(more, sum);
  card.append(bar);
  body.append(card);
};
