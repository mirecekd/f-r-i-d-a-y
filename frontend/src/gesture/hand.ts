// frontend/src/gesture/hand.ts - pure single-hand features (no DOM, three or mediapipe imports).

export interface Pt { x: number; y: number; z: number }
export interface RawHand { handedness: string; landmarks: Pt[]; score: number }
export interface Frame { t: number; hands: RawHand[] }
export type Pose = "pinch" | "open" | "fist" | "other";

export const PINCH_ON = 0.35;
export const PINCH_OFF = 0.5;
const OPEN_MIN_RATIO = 0.6;
const TIPS = [8, 12, 16, 20];
const PIPS = [6, 10, 14, 18];

export const dist = (a: { x: number; y: number }, b: { x: number; y: number }): number => Math.hypot(a.x - b.x, a.y - b.y);

/** Wrist (0) to middle-finger MCP (9): the scale all other distances are divided by. */
export const palmSize = (lm: Pt[]): number => Math.max(dist(lm[0], lm[9]), 1e-6);

/** Thumb tip to index tip over palm size. */
export const pinchRatio = (lm: Pt[]): number => dist(lm[4], lm[8]) / palmSize(lm);

/** Fingers (not the thumb) whose tip is closer to the wrist than their PIP joint. */
export function curledCount(lm: Pt[]): number {
  let n = 0;
  for (let i = 0; i < TIPS.length; i++) if (dist(lm[TIPS[i]], lm[0]) < dist(lm[PIPS[i]], lm[0])) n++;
  return n;
}

/** Pinch uses hysteresis (on below 0.35, off above 0.5). A hand with all four fingers curled is a fist even if the thumb touches the index. */
export function classify(lm: Pt[], wasPinch: boolean): Pose {
  const curled = curledCount(lm);
  if (curled === TIPS.length) return "fist";
  const r = pinchRatio(lm);
  if (r < (wasPinch ? PINCH_OFF : PINCH_ON)) return "pinch";
  if (curled === 0 && r >= OPEN_MIN_RATIO) return "open";
  return "other";
}

/** Midpoint of the thumb and index tips: where a pinching hand "points". */
export const pinchPoint = (lm: Pt[]): { x: number; y: number } => ({ x: (lm[4].x + lm[8].x) / 2, y: (lm[4].y + lm[8].y) / 2 });

/** The preview is mirrored, so the logic works in mirrored screen space. */
export const mirror = (lm: Pt[]): Pt[] => lm.map((p) => ({ x: 1 - p.x, y: p.y, z: p.z }));

/** Exponential smoothing; alpha 1 keeps the new frame. */
export function smoothLandmarks(prev: Pt[] | null, next: Pt[], alpha: number): Pt[] {
  if (!prev) return next.map((p) => ({ ...p }));
  return next.map((p, i) => ({
    x: prev[i].x + (p.x - prev[i].x) * alpha,
    y: prev[i].y + (p.y - prev[i].y) * alpha,
    z: prev[i].z + (p.z - prev[i].z) * alpha,
  }));
}
