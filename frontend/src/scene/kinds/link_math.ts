// frontend/src/scene/kinds/link_math.ts
export type V3 = [number, number, number];

export const SAMPLES = 28;
export const DOTS = 4;
const LIFT = 0.22; // control point height as a fraction of the endpoint distance
const MAX_LIFT = 1.6;

/** Shortens the segment a->b at both ends by `r` so the line starts at the tile edges, not the centres. */
export function trim(a: V3, b: V3, r: number): [V3, V3] {
  const d = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  if (d <= 2 * r || d < 1e-9) return [a, b];
  const k = r / d;
  return [
    [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k],
    [b[0] - (b[0] - a[0]) * k, b[1] - (b[1] - a[1]) * k, b[2] - (b[2] - a[2]) * k],
  ];
}

/** Point of the quadratic curve a -> (mid lifted) -> b at t in [0,1]. */
export function curveAt(a: V3, b: V3, t: number): V3 {
  const d = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  const c: V3 = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + Math.min(MAX_LIFT, d * LIFT), (a[2] + b[2]) / 2];
  const u = 1 - t;
  return [0, 1, 2].map((i) => u * u * a[i] + 2 * u * t * c[i] + t * t * b[i]) as V3;
}

export function curvePoints(a: V3, b: V3, n = SAMPLES): V3[] {
  return Array.from({ length: n + 1 }, (_, i) => curveAt(a, b, i / n));
}

/** Position of flowing dot `i` of `count` along the curve at time `t` seconds, in [0,1). */
export function flowAt(i: number, count: number, t: number): number {
  const f = (t * 0.3 + i / count) % 1;
  return f < 0 ? f + 1 : f;
}

/** A link is drawn only while both endpoint objects exist and it is not hidden itself. */
export function linkVisible(fromExists: boolean, toExists: boolean, visible: boolean | undefined): boolean {
  return fromExists && toExists && visible !== false;
}
