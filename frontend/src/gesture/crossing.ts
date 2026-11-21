// frontend/src/gesture/crossing.ts - crossed-arms detector (X): the x order of the two hands swaps and they stay together.
import type { RawHand } from "./hand.ts";

export const CROSS_HOLD_MS = 400;
const APART = 0.4; // wrists at least this far apart define the "normal" left/right order
const TOGETHER = 0.35; // swapped order counts only while the wrists are closer than this
const DROPOUT_MS = 150;

/**
 * The order of the two hands is taken from the handedness labels (stable per physical hand, whichever way the
 * camera image is mirrored); it is learned while the hands are apart, so a flipped label convention changes nothing.
 */
export class CrossDetector {
  private base = 0;
  private since = -1;
  private lastGood = -1e9;
  private fired = false;

  /** Returns true once per crossing, after the swapped, overlapping pose has been held for 400 ms. */
  update(hands: RawHand[], t: number): boolean {
    const two = hands.length === 2 && hands[0].handedness !== hands[1].handedness;
    if (!two) {
      if (hands.length === 0 && t - this.lastGood > DROPOUT_MS) this.base = 0;
      if (t - this.lastGood > DROPOUT_MS) this.restart();
      return false; // one hand may vanish for a moment while the arms overlap
    }
    this.lastGood = t;
    const [a, b] = [...hands].sort((p, q) => p.handedness.localeCompare(q.handedness));
    const dx = a.landmarks[0].x - b.landmarks[0].x;
    const gap = Math.hypot(dx, a.landmarks[0].y - b.landmarks[0].y);
    const sign = Math.sign(dx);
    if (gap >= APART) this.base = sign;
    if (this.base === 0 || sign === this.base || gap >= TOGETHER) {
      this.restart();
      return false;
    }
    if (this.since < 0) this.since = t;
    if (!this.fired && t - this.since >= CROSS_HOLD_MS) {
      this.fired = true;
      return true;
    }
    return false;
  }

  private restart(): void {
    this.since = -1;
    this.fired = false;
  }
}
