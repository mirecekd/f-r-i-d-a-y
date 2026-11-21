// frontend/src/ui/chat.ts
import type { Net } from "../net";
import { ChatImages } from "./chatimage";
import { ChatPanel, ChatStore, type ChatEntry, type ImageEntry } from "./chatpanel";

/** Chat log: message log, tool chips, live voice transcript, text input. Open/close, history and caption live in chatpanel.ts. */
export class Chat {
  private log = document.getElementById("log")!;
  private live = document.getElementById("live")!;
  private streams = new Map<string, { el: HTMLElement; entry: ChatEntry & { k: "msg" } }>();
  private chips = new Map<string, { el: HTMLElement; entry: ChatEntry & { k: "tool" } }>();
  private panel = new ChatPanel();
  private store = new ChatStore();
  readonly images = new ChatImages(this.log, () => this.store.save());

  constructor(net: Net) {
    const form = document.getElementById("form") as HTMLFormElement;
    const input = document.getElementById("input") as HTMLInputElement;
    form.onsubmit = (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      this.message("user", text);
      net.send({ t: "chat", text });
      input.value = "";
    };
    for (const entry of this.store.load()) {
      if (entry.k === "msg") this.render(entry);
      else if (entry.k === "img") this.images.add({ ...entry, state: entry.state === "failed" ? "failed" : "ready" });
      else {
        if (entry.status === "start") entry.status = "stale"; // the run that owned this chip is gone
        this.renderChip(entry);
      }
    }
    this.scroll();
  }

  message(role: string, text: string, id?: string): void {
    const entry = this.store.add({ k: "msg", role, text, id });
    const el = this.render(entry as ChatEntry & { k: "msg" });
    if (id) this.streams.set(id, { el, entry: entry as ChatEntry & { k: "msg" } });
    this.arrived(role, text);
    this.scroll();
  }

  /** Opens the chat panel (an upload started while it was closed). */
  open(): void {
    this.panel.setOpen(true);
  }

  /** Adds an upload bubble; `thumb` is an object URL shown until the stored url is known. */
  imageStart(entry: ImageEntry, thumb: string): void {
    this.store.add(entry);
    this.images.add(entry, thumb);
  }

  delta(id: string, text: string): void {
    const s = this.streams.get(id);
    if (!s) return this.message("assistant", text, id);
    s.entry.text += text;
    s.el.textContent = s.entry.text;
    this.store.save();
    this.panel.showCaption(s.entry.text);
    this.scroll();
  }

  transcript(role: string, text: string, final: boolean): void {
    if (final) {
      this.live.textContent = "";
      this.message(role, text);
    } else {
      this.live.textContent = text;
      if (role === "assistant") this.panel.showCaption(text);
    }
  }

  tool(id: string, name: string, status: string, ms?: number): void {
    let chip = this.chips.get(id);
    if (!chip) {
      const entry = this.store.add({ k: "tool", id, name, status, ms }) as ChatEntry & { k: "tool" };
      chip = { el: this.renderChip(entry), entry };
      this.chips.set(id, chip);
    }
    Object.assign(chip.entry, { name, status, ms });
    this.paintChip(chip.el, chip.entry);
    this.store.save();
    this.scroll();
  }

  private arrived(role: string, text: string): void {
    if (role === "user") return;
    this.panel.notifyArrival();
    if (role === "assistant") this.panel.showCaption(text);
  }

  private render(entry: ChatEntry & { k: "msg" }): HTMLElement {
    const el = document.createElement("div");
    el.className = `msg ${entry.role}`;
    el.textContent = entry.text; // textContent on purpose: model output is never injected as HTML
    this.log.append(el);
    return el;
  }

  private renderChip(entry: ChatEntry & { k: "tool" }): HTMLElement {
    const el = document.createElement("div");
    el.id = `tool-${entry.id}`;
    this.log.append(el);
    this.paintChip(el, entry);
    return el;
  }

  private paintChip(el: HTMLElement, e: ChatEntry & { k: "tool" }): void {
    el.className = `chip ${e.status}`;
    el.textContent = `${e.name}${e.ms ? ` - ${(e.ms / 1000).toFixed(1)} s` : ""}`;
  }

  private scroll(): void {
    this.log.scrollTop = this.log.scrollHeight;
  }
}
