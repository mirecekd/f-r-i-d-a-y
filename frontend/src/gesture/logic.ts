// frontend/src/gesture/logic.ts - PURE gesture state machine: landmark frames in, GestureEvents out.
import type { Anchor, GestureEvent, GestureType } from "./events.ts";
import { CrossDetector } from "./crossing.ts";
import { dist, pinchPoint, type Frame } from "./hand.ts";
import { assign, Slot } from "./tracks.ts";

export const DROPOUT_RELEASE_MS = 300;
export const STOP_HOLD_MS = 600;
const STILL_RADIUS = 0.04;
const MOVE_DEADZONE = 0.005;
const SCALE_STEP = 0.02;
const ROTATE_STEP = 0.03;
const SPREAD_ON = 0.45;
const SPREAD_OFF = 0.38;
const SPREAD_FULL = 0.9;
const FLATTEN_STEP = 0.02;

type Mode = "none" | "one" | "pair" | "flat";

export class GestureLogic {
  private slots: Slot[] = [];
  private mode: Mode = "none";
  private cross = new CrossDetector();
  private origin: Anchor = { x: 0, y: 0 };
  private last: Anchor = { x: 0, y: 0 };
  private d0 = 1;
  private a0 = 0;
  private aPrev = 0;
  private aSum = 0;
  private sentScale = 1;
  private sentRot = 0;
  private sentFlat = 0;
  private stopFired = false;
  private out: GestureEvent[] = [];

  /** Feeds one detection frame (t in ms); returns the events it caused. */
  feed(f: Frame): GestureEvent[] {
    this.out = [];
    const had = this.slots.length > 0;
    this.slots = this.slots.filter((s) => f.t - s.seen <= DROPOUT_RELEASE_MS);
    this.slots = assign(this.slots, f.hands, f.t);
    for (const s of this.slots) if (s.blocked && s.pose !== "pinch") s.blocked = false;
    if (this.cross.update(f.hands, f.t)) {
      this.emit("close", this.mode === "one" || this.mode === "pair" ? 1 : 0, this.centre());
      this.mode = "none";
      for (const s of this.slots) if (s.pose === "pinch") s.blocked = true;
      return this.out;
    }
    let next = this.wanted();
    if (this.mode === "pair" && next === "one") {
      for (const s of this.slots) if (s.pose === "pinch") s.blocked = true; // a pair never degrades into a single grab
      next = "none";
    }
    this.enter(next);
    this.run(f.t);
    if (had && !this.slots.length && this.mode === "none") this.emit("idle", 0, this.last);
    return this.out;
  }

  private wanted(): Mode {
    const pinching = this.slots.filter((s) => s.pose === "pinch" && !s.blocked);
    if (this.slots.length === 2 && pinching.length === 2) return "pair";
    if (pinching.length === 1) return "one";
    if (this.slots.length === 2 && this.slots.every((s) => s.pose === "open")) {
      const spread = this.spread();
      if (spread >= (this.mode === "flat" ? SPREAD_OFF : SPREAD_ON)) return "flat";
    }
    return "none";
  }

  private enter(next: Mode): void {
    if (next === this.mode) return;
    const prev = this.mode;
    if (prev === "one" || prev === "pair") {
      this.emit("release", 0, this.centre());
      if (prev === "pair") for (const s of this.slots) if (s.pose === "pinch") s.blocked = true;
    }
    if (prev === "flat") this.emit("flatten", 0, this.centre());
    this.mode = next;
    this.sentScale = 1;
    this.sentRot = 0;
    this.sentFlat = 0;
    this.stopFired = false;
    if (next === "one" || next === "pair") {
      this.origin = this.centre();
      this.last = this.origin;
      if (next === "pair") {
        const [a, b] = this.points();
        this.d0 = Math.max(dist(a, b), 1e-3);
        this.a0 = this.aPrev = Math.atan2(b.y - a.y, b.x - a.x);
        this.aSum = 0;
      }
      this.emit("grab", next === "pair" ? 2 : 1, this.origin);
    }
  }

  private run(t: number): void {
    const c = this.centre();
    if (this.mode === "one") this.step(c);
    else if (this.mode === "pair") {
      this.step(c);
      const [a, b] = this.points();
      const ratio = dist(a, b) / this.d0;
      if (Math.abs(ratio - this.sentScale) >= SCALE_STEP) this.emit("scale", (this.sentScale = ratio), c);
      const ang = Math.atan2(b.y - a.y, b.x - a.x);
      let d = ang - this.aPrev;
      d -= Math.round(d / (2 * Math.PI)) * 2 * Math.PI;
      this.aSum += d;
      this.aPrev = ang;
      if (Math.abs(this.aSum - this.sentRot) >= ROTATE_STEP) this.emit("rotate", (this.sentRot = this.aSum), c);
    } else if (this.mode === "flat") {
      const v = Math.min(1, Math.max(0, (this.spread() - SPREAD_ON) / (SPREAD_FULL - SPREAD_ON)));
      if (Math.abs(v - this.sentFlat) >= FLATTEN_STEP) this.emit("flatten", (this.sentFlat = v), c);
    }
    this.watchStop(t);
  }

  private step(c: Anchor): void {
    const dx = c.x - this.last.x;
    const dy = c.y - this.last.y;
    if (Math.hypot(dx, dy) < MOVE_DEADZONE) return;
    this.last = c;
    this.out.push({ type: "move", value: dist(c, this.origin), anchor: c, delta: { x: dx, y: dy } });
  }

  /** One open hand held still for 600 ms asks to stop (once per hold). */
  private watchStop(t: number): void {
    const s = this.slots[0];
    if (this.slots.length !== 1) return void (this.stopFired = false);
    const p = s.lm[9];
    if (s.pose !== "open" || dist(p, s.stillAt) > STILL_RADIUS) {
      s.stillAt = { x: p.x, y: p.y, since: t };
      this.stopFired = false;
    } else if (!this.stopFired && t - s.stillAt.since >= STOP_HOLD_MS) {
      this.stopFired = true;
      this.emit("stop", 1, { x: p.x, y: p.y });
    }
  }

  private points(): [Anchor, Anchor] {
    const [a, b] = this.slots;
    return [pinchPoint(a.lm), pinchPoint(b.lm)];
  }

  private spread(): number {
    return dist(this.slots[0].lm[0], this.slots[1].lm[0]);
  }

  private centre(): Anchor {
    const pts = this.slots.map((s) => (this.mode === "none" || this.mode === "flat" ? { x: s.lm[9].x, y: s.lm[9].y } : pinchPoint(s.lm)));
    if (!pts.length) return this.last;
    const sel = this.mode === "one" ? [this.slots.findIndex((s) => s.pose === "pinch" && !s.blocked)] : pts.map((_, i) => i);
    const use = sel.filter((i) => i >= 0).map((i) => pts[i]);
    if (!use.length) return this.last;
    return { x: use.reduce((n, p) => n + p.x, 0) / use.length, y: use.reduce((n, p) => n + p.y, 0) / use.length };
  }

  private emit(type: GestureType, value: number, anchor: Anchor): void {
    this.out.push({ type, value, anchor });
  }
}
