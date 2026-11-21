// frontend/src/scene/gestures.ts

export const TAP_SLOP_PX = 8;
export const LONG_PRESS_MS = 500;
const DOUBLE_TAP_MS = 350;
const DOUBLE_TAP_PX = 30;

export interface GestureHandlers {
  tap: (x: number, y: number, shift: boolean) => void;
  doubleTap: (x: number, y: number) => void;
  longPress: (x: number, y: number) => void;
}

/**
 * Pointer-event recogniser for mouse, pen and touch: tap (moved <= 8 px), double tap, and long press (500 ms still).
 * A second finger, a drag or a long press cancels the pending tap. The second tap of a double tap fires only `doubleTap`.
 */
export function attachGestures(canvas: HTMLElement, h: GestureHandlers): void {
  const active = new Map<number, { x: number; y: number }>();
  let press: { id: number; x: number; y: number; shift: boolean } | null = null;
  let timer = 0;
  let lastTap: { x: number; y: number; t: number } | null = null;

  const cancel = (): void => {
    clearTimeout(timer);
    press = null;
  };

  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener("pointerdown", (e) => {
    active.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (active.size > 1 || (e.pointerType === "mouse" && e.button !== 0)) return cancel();
    press = { id: e.pointerId, x: e.clientX, y: e.clientY, shift: e.shiftKey };
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      if (!press) return;
      const { x, y } = press;
      press = null;
      lastTap = null;
      h.longPress(x, y);
    }, LONG_PRESS_MS);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (press && e.pointerId === press.id && Math.hypot(e.clientX - press.x, e.clientY - press.y) > TAP_SLOP_PX) cancel();
  });
  canvas.addEventListener("pointerup", (e) => {
    active.delete(e.pointerId);
    const p = press;
    if (!p || p.id !== e.pointerId) return;
    cancel();
    if (Math.hypot(e.clientX - p.x, e.clientY - p.y) > TAP_SLOP_PX) return;
    const now = e.timeStamp; // event time, so main-thread jank does not break the double-tap window
    if (lastTap && now - lastTap.t < DOUBLE_TAP_MS && Math.hypot(p.x - lastTap.x, p.y - lastTap.y) < DOUBLE_TAP_PX) {
      lastTap = null;
      h.doubleTap(p.x, p.y);
      return;
    }
    lastTap = { x: p.x, y: p.y, t: now };
    h.tap(p.x, p.y, p.shift);
  });
  canvas.addEventListener("pointercancel", (e) => {
    active.delete(e.pointerId);
    cancel();
  });
}
