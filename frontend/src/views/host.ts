// frontend/src/views/host.ts
import "./panel.css";
import { el } from "./dom";
import { KINDS } from "./index";
import type { Cleanup, ViewMsg } from "./types";

interface Panel {
  id: string;
  root: HTMLElement;
  cleanup?: Cleanup;
}

const MIN_W = 220;
const MIN_H = 120;

/** Manages floating, draggable, resizable glass panels above the canvas. */
export class ViewHost {
  private panels = new Map<string, Panel>();
  private alias = new Map<string, string>(); // id of a view folded into an open panel -> id of that panel
  private layer = el("div", "views-layer");
  private z = 10;
  private cascade = 0;

  constructor() {
    document.body.append(this.layer);
  }

  show(m: ViewMsg): void {
    const live = [...this.panels.values()].find((p) => p.root.dataset.kind === m.kind && p.cleanup?.update);
    if (live) { // same kind already open and able to refresh itself: update in place, no second window
      this.alias.set(m.id, live.id);
      live.cleanup!.update!(m.data);
      this.raise(live.root);
      return;
    }
    this.close(m.id);
    const kind = KINDS[m.kind];
    const root = el("section", "vp");
    root.dataset.kind = m.kind;
    root.dataset.id = m.id;
    const head = el("div", "vp-head");
    head.append(el("span", "vp-kind", m.kind.toUpperCase()), el("span", "vp-title", m.title ?? ""));
    const x = el("button", "vp-x", "\u2715");
    x.title = "close";
    x.onclick = () => this.close(m.id);
    head.append(x);
    const body = el("div", "vp-body");
    const grip = el("div", "vp-grip");
    root.append(head, body, grip);

    const [w, h] = kind?.size ?? [360, 260];
    const n = this.cascade++ % 8;
    root.style.width = `${Math.min(w, innerWidth - 20)}px`;
    root.style.height = `${Math.min(h, innerHeight - 20)}px`;
    root.style.left = `${60 + n * 28}px`;
    root.style.top = `${90 + n * 28}px`;
    this.layer.append(root);
    this.raise(root);
    this.dragMove(root, head);
    this.dragResize(root, grip);
    root.addEventListener("pointerdown", () => this.raise(root), true);
    body.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true }); // scroll the card, never zoom the scene under it

    const panel: Panel = { id: m.id, root };
    this.panels.set(m.id, panel);
    if (this.panels.size > 3) this.tile();
    if (!kind) return this.fail(body, `unknown view kind: ${m.kind}`);
    try {
      Promise.resolve(kind.render(body, m.data)).then(
        (c) => {
          if (typeof c === "function") {
            if (this.panels.get(m.id) === panel) panel.cleanup = c;
            else c();
          }
        },
        (e) => this.fail(body, e),
      );
    } catch (e) {
      this.fail(body, e);
    }
  }

  /** With more than 3 panels the 28 px cascade overlaps too much: lay all out in a grid left of the chat. */
  private tile(): void {
    const list = [...this.panels.values()];
    const left = 60, top = 90, gap = 10;
    const right = innerWidth > 700 ? Math.min(380, innerWidth * 0.4) + 48 : 12;
    const aw = Math.max(MIN_W, innerWidth - left - right);
    const ah = Math.max(MIN_H, innerHeight - top - 110);
    const cols = Math.max(1, Math.min(list.length, Math.floor((aw + gap) / (MIN_W + gap)), Math.ceil(Math.sqrt(list.length * aw / ah))));
    const rows = Math.ceil(list.length / cols);
    const w = Math.floor((aw - gap * (cols - 1)) / cols);
    const h = Math.max(MIN_H, Math.floor((ah - gap * (rows - 1)) / rows));
    list.forEach((p, i) => {
      p.root.style.width = `${w}px`;
      p.root.style.height = `${h}px`;
      p.root.style.left = `${left + (i % cols) * (w + gap)}px`;
      p.root.style.top = `${top + Math.floor(i / cols) * (h + gap)}px`;
    });
  }

  close(id: string): void {
    const p = this.panels.get(this.alias.get(id) ?? id);
    if (!p) return;
    for (const [k, v] of this.alias) if (v === p.id) this.alias.delete(k);
    p.cleanup?.();
    p.root.remove();
    this.panels.delete(p.id);
  }

  ids(): string[] {
    return [...this.panels.keys()];
  }

  private fail(body: HTMLElement, e: unknown): void {
    body.replaceChildren(el("div", "vp-err", e instanceof Error ? e.message : String(e)));
  }

  private raise(root: HTMLElement): void {
    root.style.zIndex = String(++this.z);
  }

  private dragMove(root: HTMLElement, handle: HTMLElement): void {
    handle.addEventListener("pointerdown", (ev) => {
      if ((ev.target as HTMLElement).closest("button")) return;
      const dx = ev.clientX - root.offsetLeft;
      const dy = ev.clientY - root.offsetTop;
      handle.setPointerCapture(ev.pointerId);
      const move = (e: PointerEvent) => {
        root.style.left = `${Math.max(-root.offsetWidth + 80, Math.min(innerWidth - 80, e.clientX - dx))}px`;
        root.style.top = `${Math.max(0, Math.min(innerHeight - 30, e.clientY - dy))}px`;
      };
      const up = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
    });
  }

  private dragResize(root: HTMLElement, grip: HTMLElement): void {
    grip.addEventListener("pointerdown", (ev) => {
      const w0 = root.offsetWidth, h0 = root.offsetHeight, x0 = ev.clientX, y0 = ev.clientY;
      grip.setPointerCapture(ev.pointerId);
      const move = (e: PointerEvent) => {
        root.style.width = `${Math.max(MIN_W, w0 + e.clientX - x0)}px`;
        root.style.height = `${Math.max(MIN_H, h0 + e.clientY - y0)}px`;
      };
      const up = () => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
    });
  }
}

export const views = new ViewHost();
