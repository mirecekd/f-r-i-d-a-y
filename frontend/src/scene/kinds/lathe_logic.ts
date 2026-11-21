// frontend/src/scene/kinds/lathe_logic.ts
/** Pure parameter handling for the `lathe` kind (no THREE import so node can test it). */

export const MIN_SEGMENTS = 3;
export const MAX_SEGMENTS = 96;
export const DEFAULT_SEGMENTS = 32;
export const MAX_PROFILE = 64;
export const MAX_COORD = 1e4;

export type ProfilePoint = [number, number];

export function latheSegments(v: unknown): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return DEFAULT_SEGMENTS;
  return Math.min(MAX_SEGMENTS, Math.max(MIN_SEGMENTS, Math.round(v)));
}

/** Keep finite [r, y] pairs, clamp r to >= 0 and |v| to MAX_COORD, drop consecutive duplicates, cap the length. */
export function lathePoints(v: unknown): ProfilePoint[] {
  if (!Array.isArray(v)) return [];
  const out: ProfilePoint[] = [];
  for (const p of v) {
    if (!Array.isArray(p) || p.length < 2) continue;
    const [r, y] = p;
    if (typeof r !== "number" || typeof y !== "number" || !Number.isFinite(r) || !Number.isFinite(y)) continue;
    const pt: ProfilePoint = [Math.min(MAX_COORD, Math.max(0, r)), Math.min(MAX_COORD, Math.max(-MAX_COORD, y))];
    const last = out[out.length - 1];
    if (last && last[0] === pt[0] && last[1] === pt[1]) continue;
    out.push(pt);
    if (out.length >= MAX_PROFILE) break;
  }
  return out;
}

/** Points of the closing cap: the profile ends are joined to the axis so the solid has no open rim. */
export function capProfile(points: ProfilePoint[], cap: boolean): ProfilePoint[] {
  if (!cap || points.length < 2) return points;
  const out = points.slice();
  const first = out[0];
  const last = out[out.length - 1];
  if (last[0] > 0) out.push([0, last[1]]);
  if (first[0] > 0) out.unshift([0, first[1]]);
  return out;
}
