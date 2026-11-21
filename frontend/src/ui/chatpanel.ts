// frontend/src/ui/chatpanel.ts
import type { Exif } from "../views/exif";

/** One persisted chat entry: a message or a tool chip. */
export type ChatEntry =
  | { k: "msg"; role: string; text: string; id?: string }
  | { k: "tool"; id: string; name: string; status: string; ms?: number }
  | ImageEntry;

/** An uploaded image bubble. Only the stored `url` is persisted, never base64 or object URLs. */
export interface ImageEntry {
  k: "img";
  id: string;
  name: string;
  state: "sending" | "analysing" | "ready" | "failed";
  url?: string;
  w?: number;
  h?: number;
  exif?: Exif;
  error?: string;
  /** Set for non-image files: the bubble shows a chip instead of a thumbnail. */
  file?: { kind: string; size: number };
}

const STORAGE_KEY = "friday.chat";
const MAX_ENTRIES = 500;
const CAPTION_MS = 6000;

/** Chat history in localStorage, capped at MAX_ENTRIES; saves are debounced. */
export class ChatStore {
  private entries: ChatEntry[] = [];
  private timer = 0;

  load(): ChatEntry[] {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
      if (Array.isArray(raw)) this.entries = raw.filter((e) => e && (e.k === "msg" || e.k === "tool" || (e.k === "img" && typeof e.url === "string"))).slice(-MAX_ENTRIES);
    } catch {
      this.entries = [];
    }
    return this.entries;
  }

  add(entry: ChatEntry): ChatEntry {
    this.entries.push(entry);
    if (this.entries.length > MAX_ENTRIES) this.entries.splice(0, this.entries.length - MAX_ENTRIES);
    this.save();
    return entry;
  }

  /** Messages only (tool chips and image bubbles do not count as conversation). */
  messages(): number {
    return this.entries.filter((e) => e.k === "msg").length;
  }

  /** Forget the whole history, in memory and in localStorage. */
  clear(): void {
    clearTimeout(this.timer);
    this.entries = [];
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage blocked: nothing to remove */
    }
  }

  save(): void {
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.entries.filter((e) => e.k !== "img" || e.url)));
      } catch {
        /* storage full or blocked: history stays in memory only */
      }
    }, 250);
  }
}

/** Open/close shell around #chat: toggle button, unread badge, Esc, and the closed-state live caption. */
export class ChatPanel {
  private panel = document.getElementById("chat")!;
  private button = document.getElementById("chatbtn")!;
  private badge = document.getElementById("chatbadge")!;
  private caption = document.getElementById("caption")!;
  private input = document.getElementById("input") as HTMLInputElement;
  private unread = 0;
  private captionTimer = 0;

  constructor() {
    this.button.onclick = () => this.setOpen(!this.isOpen());
    addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) this.setOpen(false);
    });
    this.setOpen(false);
  }

  isOpen(): boolean {
    return this.panel.classList.contains("open");
  }

  setOpen(open: boolean): void {
    this.panel.classList.toggle("open", open);
    this.panel.setAttribute("aria-hidden", String(!open));
    this.button.setAttribute("aria-expanded", String(open));
    this.button.classList.toggle("on", open);
    if (open) {
      this.unread = 0;
      this.renderBadge();
      this.hideCaption();
      this.input.focus({ preventScroll: true });
    } else {
      this.input.blur();
    }
  }

  /** A message arrived from the assistant side; counts as unread while closed. */
  notifyArrival(): void {
    if (this.isOpen()) return;
    this.unread++;
    this.renderBadge();
  }

  /** Latest assistant sentence, shown near the bottom centre while the panel is closed. */
  showCaption(text: string): void {
    if (this.isOpen()) return;
    const sentence = lastSentence(text);
    if (!sentence) return;
    this.caption.textContent = sentence;
    this.caption.classList.add("show");
    clearTimeout(this.captionTimer);
    this.captionTimer = window.setTimeout(() => this.hideCaption(), CAPTION_MS);
  }

  /** Hides the closed-state caption now. */
  clearCaption(): void {
    this.hideCaption();
  }

  private hideCaption(): void {
    clearTimeout(this.captionTimer);
    this.caption.classList.remove("show");
  }

  private renderBadge(): void {
    this.badge.textContent = this.unread > 9 ? "9+" : String(this.unread);
    this.badge.hidden = this.unread === 0;
  }
}

/** Last non-empty sentence of a text (split on . ! ? and newlines). */
export function lastSentence(text: string): string {
  const parts = text.trim().split(/(?<=[.!?])\s+|\n+/).filter((p) => p.trim());
  return (parts[parts.length - 1] ?? "").trim();
}
