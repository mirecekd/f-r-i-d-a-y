// frontend/src/ui/dropnotice.ts
import "./dropnotice.css";
import type { Msg, Net } from "../net";
import type { ScenePlayer } from "../scene/player";
import { el } from "../views/dom";

const TOAST_MS = 8000;
const CARD_SUPPRESS_MS = 2500;

interface Dropped { name: string }

/** After an upload: the new entity is selected once, the camera glides to it, a toast offers Otevrit / Zeptat se, and the automatic 2D card is held back. */
export class DropNotice {
  private ready = new Map<string, Dropped>(); // stored id -> upload
  private placed = new Map<string, string>(); // stored id -> scene object id
  private recent = new Map<string, number>(); // stored id -> upload time, to hold back the automatic card
  private toast = el("div", "dn-toast");
  private timer = 0;

  constructor(
    private net: Net,
    private player: ScenePlayer,
    private frame: (ids: string[]) => void,
    private ask: (text: string) => void,
  ) {
    this.toast.hidden = true;
    this.toast.setAttribute("role", "status");
    document.body.append(this.toast);
    net.on((m) => this.onMessage(m));
  }

  private onMessage(m: Msg): void {
    if (m.t === "file_ready" || m.t === "image_ready") {
      this.ready.set(String(m.id), { name: String(m.name ?? "soubor") });
      this.recent.set(String(m.id), Date.now());
      this.settle(String(m.id));
    } else if (m.t === "scene") {
      for (const op of (m.ops ?? []) as { op: string; obj?: { id: string; ref?: { id: string } } }[]) {
        if (op.op === "add" && op.obj?.ref) {
          this.placed.set(op.obj.ref.id, op.obj.id);
          this.settle(op.obj.ref.id);
        }
      }
    }
  }

  /** Once both the upload answer and the scene object are known: select, glide, toast (only once per item). */
  private settle(refId: string): void {
    const up = this.ready.get(refId);
    const obj = this.placed.get(refId);
    if (!up || !obj) return;
    this.ready.delete(refId);
    this.placed.delete(refId);
    setTimeout(() => { // the scene handler of main.ts applies the same message first
      if (!this.player.entries.has(obj)) return;
      this.player.selection.set([obj]);
      this.player.onSelect([obj]);
      this.frame([obj]);
      this.show(up.name, obj);
    }, 0);
  }

  /** False for a file_card / image_card that follows an upload within a few seconds (the file goes onto the desk instead). */
  keepsView(m: Msg): boolean {
    if (m.kind !== "file_card" && m.kind !== "image_card") return true;
    const key = String(m.id ?? "").replace(/^(file|image)-/, "");
    const hit = [...this.recent].find(([id, at]) => id.startsWith(key) && Date.now() - at < CARD_SUPPRESS_MS);
    return !hit;
  }

  private show(name: string, id: string): void {
    clearTimeout(this.timer);
    const text = el("span", "dn-text", `Soubor je na plose: ${name}`);
    const open = el("button", "", "Otevrit");
    open.type = "button";
    open.onclick = () => { this.net.send({ t: "entity_open", id }); this.hide(); };
    const askBtn = el("button", "", "Zeptat se");
    askBtn.type = "button";
    askBtn.onclick = () => { this.ask(`Co je to za soubor ${name}?`); this.hide(); };
    this.toast.replaceChildren(text, open, askBtn);
    this.toast.hidden = false;
    this.timer = window.setTimeout(() => this.hide(), TOAST_MS);
  }

  private hide(): void {
    clearTimeout(this.timer);
    this.toast.hidden = true;
  }
}
