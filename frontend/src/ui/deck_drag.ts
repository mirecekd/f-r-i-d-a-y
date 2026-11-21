// frontend/src/ui/deck_drag.ts
import type * as THREE from "three";
import { el } from "../views/dom";
import { dropPositionOnDesk, type Vec3 } from "./entitybar_logic";
import type { DeckItem } from "./deck_logic";

const MOVE_THRESHOLD_PX = 6;

export interface DragTargets {
  canvas: HTMLElement;
  camera: THREE.PerspectiveCamera;
  /** Tile dropped on the 3D desk at this world position (null: no position, the server chooses). */
  onDesk(item: DeckItem, pos: Vec3 | null): void;
  /** Tile dropped on the chat panel. */
  onChat(item: DeckItem): void;
}

/** Pointer-based drag of a tile (mouse and touch) with a ghost; the panel turns click-through while dragging so the canvas is reachable. */
export function startTileDrag(item: DeckItem, down: PointerEvent, panel: HTMLElement, t: DragTargets): void {
  const sx = down.clientX, sy = down.clientY;
  let ghost: HTMLElement | null = null;
  const move = (e: PointerEvent): void => {
    if (!ghost) {
      if (Math.hypot(e.clientX - sx, e.clientY - sy) < MOVE_THRESHOLD_PX) return;
      ghost = el("div", "dk-ghost", item.title);
      document.body.append(ghost);
      panel.classList.add("dragging");
    }
    ghost.style.left = `${e.clientX}px`;
    ghost.style.top = `${e.clientY}px`;
    e.preventDefault();
  };
  const finish = (e: PointerEvent, drop: boolean): void => {
    removeEventListener("pointermove", move);
    removeEventListener("pointerup", up);
    removeEventListener("pointercancel", cancel);
    if (!ghost) return;
    ghost.remove();
    panel.classList.remove("dragging");
    if (!drop) return;
    const over = document.elementFromPoint(e.clientX, e.clientY);
    if (over?.closest("#chat")) return t.onChat(item);
    if (over !== t.canvas) return;
    t.camera.updateMatrixWorld();
    const pos = dropPositionOnDesk(t.canvas.getBoundingClientRect(), e.clientX, e.clientY, t.camera.matrixWorld.elements, t.camera.projectionMatrixInverse.elements);
    t.onDesk(item, pos);
  };
  const up = (e: PointerEvent): void => finish(e, true);
  const cancel = (e: PointerEvent): void => finish(e, false);
  addEventListener("pointermove", move, { passive: false });
  addEventListener("pointerup", up);
  addEventListener("pointercancel", cancel);
}
