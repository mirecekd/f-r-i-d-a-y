// frontend/src/gesture/events.ts - the event vocabulary shared by logic.ts, mapper.ts and the demo driver.

export type GestureType = "grab" | "move" | "release" | "scale" | "rotate" | "close" | "flatten" | "stop" | "idle";

/** Normalised (0..1) point in the mirrored camera view, which has the same orientation as the screen. */
export interface Anchor { x: number; y: number }

/**
 * value by type: scale = ratio to the start distance; rotate = angle in radians since the two-hand start (unwrapped);
 * flatten = 0..1 proportional to the hand spread; move = distance from the grab point; close = 1 when it cancels an
 * active grab, else 0; the others carry 0 (stop: 1). `delta` (move only) is the anchor step since the last move.
 */
export interface GestureEvent {
  type: GestureType;
  value: number;
  anchor: Anchor;
  delta?: Anchor;
}

export const ZERO: Anchor = { x: 0.5, y: 0.5 };
