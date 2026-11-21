// frontend/src/gesture/demo.ts - `?gesturedemo`: drives the mapper from the mouse so the scene mapping can be tried without a camera.
import type { GestureEvent } from "./events";

export const DEMO_HELP = "G+tazeni scale, R+tazeni rotate, M+tazeni move, F+tazeni flatten, H zavrit, S stop, Esc zrusit";

/** Hold a key and drag: G scale (right = bigger), R rotate, M move, F flatten. H = close, S = stop. */
export function attachDemo(emit: (e: GestureEvent) => void): void {
  const held = new Set<string>();
  let drag: { x: number; y: number; mode: string; sent: boolean } | null = null;
  const at = (x: number, y: number) => ({ x: x / innerWidth, y: y / innerHeight });
  const finish = (x: number, y: number): void => {
    if (!drag) return;
    if (drag.mode === "f") emit({ type: "flatten", value: 0, anchor: at(x, y) });
    emit({ type: "release", value: 0, anchor: at(x, y) });
    drag = null;
  };
  addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    held.add(k);
    if (k === "h") emit({ type: "close", value: 0, anchor: { x: 0.5, y: 0.5 } });
    if (k === "s") emit({ type: "stop", value: 1, anchor: { x: 0.5, y: 0.5 } });
    if (k === "escape" && drag) emit({ type: "close", value: 1, anchor: at(drag.x, drag.y) }), (drag = null);
  });
  addEventListener("keyup", (e) => held.delete(e.key.toLowerCase()));
  addEventListener("pointerdown", (e) => {
    const mode = ["g", "r", "m", "f"].find((k) => held.has(k));
    if (!mode || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    drag = { x: e.clientX, y: e.clientY, mode, sent: false };
    emit({ type: "grab", value: mode === "m" ? 1 : 2, anchor: at(e.clientX, e.clientY) });
  }, true);
  addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = (e.clientX - drag.x) / innerWidth;
    const a = at(e.clientX, e.clientY);
    if (drag.mode === "g") emit({ type: "scale", value: Math.max(0.1, 1 + dx * 3), anchor: a });
    else if (drag.mode === "r") emit({ type: "rotate", value: dx * 6, anchor: a });
    else if (drag.mode === "f") emit({ type: "flatten", value: Math.min(1, Math.max(0, dx * 2)), anchor: a });
    else {
      emit({ type: "move", value: 0, anchor: a, delta: { x: (e.clientX - drag.x) / innerWidth, y: (e.clientY - drag.y) / innerHeight } });
      drag.x = e.clientX;
      drag.y = e.clientY;
    }
  }, true);
  addEventListener("pointerup", (e) => finish(e.clientX, e.clientY), true);
}
