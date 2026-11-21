// frontend/src/ui/entitybar_logic.ts

/** Pure screen/desk maths (no THREE, no DOM) so node can test it. Matrices are column-major arrays of 16, as THREE stores them. */
type Mat = ArrayLike<number>;
export type Vec3 = [number, number, number];

/** Height of the desk plane: the same BASE_Y the backend layout puts entities on. */
export const DESK_Y = 1.2;
/** Drops further from the origin than this are treated as misses. */
export const DESK_LIMIT = 40;
const BAR_GAP = 10;
const EDGE = 8;

function apply(m: Mat, x: number, y: number, z: number, w: number): [number, number, number, number] {
  const row = (i: number) => m[i] * x + m[4 + i] * y + m[8 + i] * z + m[12 + i] * w;
  return [row(0), row(1), row(2), row(3)];
}

/** World point to normalised device coords; null when it is behind the camera. */
export function projectPoint(viewInverse: Mat, projection: Mat, p: Vec3): { nx: number; ny: number } | null {
  const v = apply(viewInverse, p[0], p[1], p[2], 1);
  const c = apply(projection, v[0], v[1], v[2], v[3]);
  if (c[3] <= 1e-6) return null;
  return { nx: c[0] / c[3], ny: c[1] / c[3] };
}

/** Device coords (-1..1, y up) to CSS pixels inside a viewport of the given size. */
export function ndcToPixels(nx: number, ny: number, width: number, height: number): { x: number; y: number } {
  return { x: ((nx + 1) / 2) * width, y: ((1 - ny) / 2) * height };
}

/** Point at depth `nz` (-1 near, 1 far) under a device-coords position. */
export function unprojectPoint(cameraWorld: Mat, projectionInverse: Mat, nx: number, ny: number, nz: number): Vec3 {
  const v = apply(projectionInverse, nx, ny, nz, 1);
  const w = apply(cameraWorld, v[0] / v[3], v[1] / v[3], v[2] / v[3], 1);
  return [w[0], w[1], w[2]];
}

/** Where the camera ray through (nx, ny) meets the horizontal plane y = planeY; null when it never does. */
export function rayHitsPlaneY(cameraWorld: Mat, projectionInverse: Mat, nx: number, ny: number, planeY: number): Vec3 | null {
  const a = unprojectPoint(cameraWorld, projectionInverse, nx, ny, -1);
  const b = unprojectPoint(cameraWorld, projectionInverse, nx, ny, 1);
  const dy = b[1] - a[1];
  if (Math.abs(dy) < 1e-9) return null;
  const t = (planeY - a[1]) / dy;
  if (!(t > 0)) return null;
  return [a[0] + (b[0] - a[0]) * t, planeY, a[2] + (b[2] - a[2]) * t];
}

export interface Rect { left: number; top: number; width: number; height: number }

/** Desk position for a tile dropped at client pixel (cx, cy) on the canvas `rect`; null when outside or not on the desk. */
export function dropPositionOnDesk(rect: Rect, cx: number, cy: number, cameraWorld: Mat, projectionInverse: Mat): Vec3 | null {
  if (rect.width <= 0 || rect.height <= 0) return null;
  const nx = ((cx - rect.left) / rect.width) * 2 - 1;
  const ny = -(((cy - rect.top) / rect.height) * 2 - 1);
  if (Math.abs(nx) > 1 || Math.abs(ny) > 1) return null;
  const hit = rayHitsPlaneY(cameraWorld, projectionInverse, nx, ny, DESK_Y);
  if (!hit || Math.abs(hit[0]) > DESK_LIMIT || Math.abs(hit[2]) > DESK_LIMIT) return null;
  return [Math.round(hit[0] * 100) / 100, DESK_Y, Math.round(hit[2] * 100) / 100];
}

/** Top-left of a bar of `size` anchored at pixel (ax, ay): above the anchor, flipped below when there is no room, clamped to the viewport. */
export function placeBar(anchor: { x: number; y: number }, size: { w: number; h: number }, view: { w: number; h: number }): { left: number; top: number } {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, Math.max(lo, hi)));
  let top = anchor.y - size.h - BAR_GAP;
  if (top < EDGE) top = anchor.y + BAR_GAP;
  return {
    left: clamp(anchor.x - size.w / 2, EDGE, view.w - size.w - EDGE),
    top: clamp(top, EDGE, view.h - size.h - EDGE),
  };
}

const TYPING = /^(input|textarea|select)$/i;
/** True when a key press belongs to a text field, so desk shortcuts must stay out of the way. */
export function isTypingTarget(t: { tagName?: string; isContentEditable?: boolean } | null): boolean {
  return !!t && (TYPING.test(t.tagName ?? "") || t.isContentEditable === true);
}

/** What a key does to the selected entity: remove, deselect, open, or nothing. */
export function keyAction(key: string): "remove" | "deselect" | "open" | null {
  if (key === "Delete" || key === "Backspace") return "remove";
  if (key === "Escape") return "deselect";
  if (key === "Enter") return "open";
  return null;
}
