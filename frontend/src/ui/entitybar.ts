// frontend/src/ui/entitybar.ts
import * as THREE from "three";
import "./entitybar.css";
import type { ScenePlayer } from "../scene/player";
import { isTypingTarget, keyAction, ndcToPixels, placeBar, projectPoint } from "./entitybar_logic";
import type { Send } from "./entity_menu";

export interface BarActions {
  isEntity(id: string): boolean;
  open(id: string): void;
  startLink(id: string): void;
}

const BLOCKING_LAYERS = ".dk-panel:not([hidden]), .cf-back, #ctxmenu:not([hidden])";

/** Floating [Zavrit x] [Otevrit] [Spojit] [Zeptat se] bar that follows the single selected entity; also the Delete / Esc / Enter keys. */
export class EntityBar {
  private bar = document.createElement("div");
  private box = new THREE.Box3();

  constructor(
    private player: ScenePlayer,
    private camera: THREE.PerspectiveCamera,
    private actions: BarActions,
    private send: Send,
    private ask: (text: string) => void,
  ) {
    this.bar.className = "eb-bar";
    this.bar.hidden = true;
    this.bar.setAttribute("role", "toolbar");
    this.bar.setAttribute("aria-label", "Akce s polozkou");
    this.button("Zavrit x", "eb-close", "Odebrat z plochy (zustane v Decku)", () => this.remove());
    this.button("Otevrit", "", "Otevrit kartu polozky", () => this.run((id) => this.actions.open(id)));
    this.button("Spojit", "", "Spojit s dalsi polozkou", () => this.run((id) => this.actions.startLink(id)));
    this.button("Zeptat se", "", "Zeptat se na polozku", () => this.run((id) => this.ask(`Co je to za soubor ${this.titleOf(id)}?`)));
    document.body.append(this.bar);
    addEventListener("keydown", (e) => this.onKey(e), true);
  }

  private button(text: string, cls: string, title: string, run: () => void): void {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.title = title;
    if (cls) b.className = cls;
    b.onclick = run;
    this.bar.append(b);
  }

  /** The one selected entity id, or null. */
  current(): string | null {
    const ids = this.player.selection.ids;
    return ids.length === 1 && this.actions.isEntity(ids[0]) ? ids[0] : null;
  }

  private titleOf(id: string): string {
    const o = this.player.entries.get(id)?.obj;
    return String(o?.title ?? o?.label ?? id);
  }

  private run(fn: (id: string) => void): void {
    const id = this.current();
    if (id) fn(id);
  }

  private remove(): void {
    this.run((id) => this.send({ t: "entity_remove", id }));
  }

  private deselect(): void {
    this.player.selection.set([]);
    this.player.onSelect([]);
  }

  private onKey(e: KeyboardEvent): void {
    const action = keyAction(e.key);
    if (!action || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTypingTarget(e.target as HTMLElement | null) || document.querySelector(BLOCKING_LAYERS)) return;
    if (action === "open" && (e.target as HTMLElement | null)?.closest("button")) return;
    if (!this.current()) return;
    e.preventDefault(); // also keeps the global Esc = stop-everything handler from firing for a plain deselect
    if (action === "remove") this.remove();
    else if (action === "open") this.run((id) => this.actions.open(id));
    else this.deselect();
  }

  /** Per frame: show the bar above the selected entity's top edge, hide it when nothing or several things are selected. */
  update(): void {
    const id = this.current();
    const node = id ? this.player.entries.get(id)?.node : undefined;
    if (!id || !node || !node.visible) return this.hide();
    this.box.setFromObject(node);
    if (this.box.isEmpty()) return this.hide();
    const top = projectPoint(this.camera.matrixWorldInverse.elements, this.camera.projectionMatrix.elements, [
      (this.box.min.x + this.box.max.x) / 2, this.box.max.y, (this.box.min.z + this.box.max.z) / 2,
    ]);
    if (!top) return this.hide();
    this.bar.hidden = false;
    const px = ndcToPixels(top.nx, top.ny, innerWidth, innerHeight);
    const at = placeBar(px, { w: this.bar.offsetWidth, h: this.bar.offsetHeight }, { w: innerWidth, h: innerHeight });
    this.bar.style.left = `${Math.round(at.left)}px`;
    this.bar.style.top = `${Math.round(at.top)}px`;
  }

  private hide(): void {
    this.bar.hidden = true;
  }
}
