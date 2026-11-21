// frontend/src/gesture/tracks.ts - frame-to-frame identity, smoothing and pose debouncing of up to two hands.
import { classify, dist, mirror, smoothLandmarks, type Pose, type Pt, type RawHand } from "./hand.ts";

export const MIN_POSE_FRAMES = 3;
const SMOOTH_TAU_MS = 50;
const MAX_MATCH = 0.35;

/** One tracked hand. Identity comes from position, not from the handedness label (which flips with mirroring). */
export class Slot {
  lm: Pt[];
  seen: number;
  pose: Pose = "other";
  /** After a two-hand session ends the remaining pinch must be released before it can grab again. */
  blocked = false;
  stillAt = { x: 0, y: 0, since: 0 };
  private cand: Pose = "other";
  private count = 0;

  constructor(raw: Pt[], t: number) {
    this.lm = mirror(raw);
    this.seen = t;
    this.stillAt = { x: this.lm[9].x, y: this.lm[9].y, since: t };
    this.debounce(classify(this.lm, false));
  }

  update(raw: Pt[], t: number): void {
    const dt = Math.min(Math.max(t - this.seen, 8), 100);
    this.lm = smoothLandmarks(this.lm, mirror(raw), 1 - Math.exp(-dt / SMOOTH_TAU_MS));
    this.seen = t;
    this.debounce(classify(this.lm, this.pose === "pinch"));
  }

  private debounce(raw: Pose): void {
    if (raw === this.pose) {
      this.cand = raw;
      this.count = 0;
      return;
    }
    this.count = raw === this.cand ? this.count + 1 : 1;
    this.cand = raw;
    if (this.count >= MIN_POSE_FRAMES) {
      this.pose = raw;
      this.count = 0;
    }
  }
}

/** Matches detections to slots by nearest wrist (greedy), creates slots for new hands (max 2) and returns the unmatched slots untouched. */
export function assign(slots: Slot[], hands: RawHand[], t: number): Slot[] {
  const dets = [...hands].sort((a, b) => b.score - a.score).slice(0, 2).map((h) => h.landmarks);
  const pairs: { s: Slot; d: number; dist: number }[] = [];
  dets.forEach((lm, d) => slots.forEach((s) => pairs.push({ s, d, dist: dist(s.lm[0], { x: 1 - lm[0].x, y: lm[0].y }) })));
  pairs.sort((a, b) => a.dist - b.dist);
  const usedSlots = new Set<Slot>();
  const usedDets = new Set<number>();
  for (const p of pairs) {
    if (p.dist > MAX_MATCH || usedSlots.has(p.s) || usedDets.has(p.d)) continue;
    usedSlots.add(p.s);
    usedDets.add(p.d);
    p.s.update(dets[p.d], t);
  }
  const out = [...slots];
  dets.forEach((lm, d) => {
    if (!usedDets.has(d) && out.length < 2) out.push(new Slot(lm, t));
  });
  return out;
}
