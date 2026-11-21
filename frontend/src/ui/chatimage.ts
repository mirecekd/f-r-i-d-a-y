// frontend/src/ui/chatimage.ts
import { exifChips } from "../views/exif";
import { fileChip } from "../views/file_icon";
import type { ImageEntry } from "./chatpanel";

const STATE_TEXT: Record<ImageEntry["state"], string> = {
  sending: "Odesilam...",
  analysing: "Analyzuji obrazek...",
  ready: "",
  failed: "",
};

/** Image bubbles in the chat log. Thumbnails come from object URLs until the server stored the image. */
export class ChatImages {
  private bubbles = new Map<string, { el: HTMLElement; entry: ImageEntry; thumb?: string }>();

  constructor(private log: HTMLElement, private persist: () => void) {}

  /** Drops every bubble (new conversation) and frees the thumbnail object URLs. */
  clear(): void {
    for (const b of this.bubbles.values()) if (b.thumb) URL.revokeObjectURL(b.thumb);
    this.bubbles.clear();
  }

  has(id: string): boolean {
    return this.bubbles.has(id);
  }

  add(entry: ImageEntry, thumb?: string): void {
    const el = document.createElement("div");
    this.bubbles.set(entry.id, { el, entry, thumb });
    this.log.append(el);
    this.paint(entry.id);
  }

  update(id: string, patch: Partial<ImageEntry>): void {
    const b = this.bubbles.get(id);
    if (!b) return;
    Object.assign(b.entry, patch);
    if (patch.url && b.thumb) {
      URL.revokeObjectURL(b.thumb);
      b.thumb = undefined;
    }
    this.paint(id);
    this.persist();
  }

  /** Marks every bubble still analysing as done (the analysis finished or failed server side). */
  settle(url?: string): void {
    for (const [id, b] of this.bubbles) if (b.entry.state === "analysing" && (!url || b.entry.url === url)) this.update(id, { state: "ready" });
  }

  private paint(id: string): void {
    const b = this.bubbles.get(id)!;
    const e = b.entry;
    b.el.className = `msg user img ${e.state}`;
    const children: HTMLElement[] = [];
    const src = e.file ? undefined : e.url ?? b.thumb;
    if (e.file) children.push(fileChip(e.file.kind, e.name, e.file.size));
    if (src) {
      const img = document.createElement("img");
      img.className = "chat-thumb";
      img.alt = e.name;
      img.src = src;
      children.push(img);
    }
    if (!e.file) {
      const name = document.createElement("div");
      name.className = "chat-imgname";
      name.textContent = e.w && e.h ? `${e.name} (${e.w} x ${e.h})` : e.name;
      children.push(name);
    }
    const status = e.state === "failed" ? e.error ?? "Nahrani selhalo" : e.file && e.state === "sending" ? "Nahravam soubor..." : STATE_TEXT[e.state];
    if (status) {
      const st = document.createElement("div");
      st.className = `chat-imgstate ${e.state}`;
      st.textContent = status;
      children.push(st);
    }
    const chips = exifChips(e.exif);
    if (chips.length) {
      const row = document.createElement("div");
      row.className = "ic-chips";
      row.append(...chips);
      children.push(row);
    }
    b.el.replaceChildren(...children);
    this.log.scrollTop = this.log.scrollHeight;
  }
}
