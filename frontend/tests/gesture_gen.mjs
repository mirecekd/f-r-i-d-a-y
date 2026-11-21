// frontend/tests/gesture_gen.mjs - synthetic landmark generators for gesture_logic.mjs (raw camera space, not mirrored).
export const P = 0.08; // palm size: wrist to middle MCP

const FINGER_X = { index: -0.3, middle: 0, ring: 0.3, pinky: 0.6 };
const BASE = { index: 5, middle: 9, ring: 13, pinky: 17 };

/** pose: 'open' | 'fist' | 'pinch' | 'other'; gap = thumb-index distance / palm size (pinch). Wrist at w, hand points up. */
export function hand(w, pose, { gap = 0.15, label = "Right", score = 0.95, jitter = 0, rnd = Math.random } = {}) {
  const lm = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
  const put = (i, ux, uy) => { lm[i] = { x: w[0] + ux * P, y: w[1] + uy * P, z: 0 }; };
  put(0, 0, 0);
  const curled = { open: [], fist: ["index", "middle", "ring", "pinky"], pinch: ["middle", "ring", "pinky"], other: ["ring", "pinky"] }[pose];
  for (const f of Object.keys(BASE)) {
    const b = BASE[f], x = FINGER_X[f];
    put(b, x, -1);
    put(b + 1, x, -1.5);
    put(b + 2, x, curled.includes(f) ? -1.0 : -1.8);
    put(b + 3, x, curled.includes(f) ? -0.6 : f === "index" && pose === "pinch" ? -1.7 : -2.1);
  }
  put(1, -0.5, -0.4); put(2, -0.8, -0.7); put(3, -0.9, -0.9);
  if (pose === "pinch") put(4, -0.3 - gap, -1.7);
  else if (pose === "fist") put(4, -0.1, -0.6);
  else put(4, -1.2, -1.2);
  if (jitter) for (const p of lm) { p.x += (rnd() - 0.5) * 2 * jitter; p.y += (rnd() - 0.5) * 2 * jitter; }
  return { handedness: label, landmarks: lm, score };
}

/** Pinch hand whose thumb/index midpoint sits at target p. */
export function pinchAt(p, opts = {}) {
  const probe = hand([0, 0], "pinch", opts);
  const mid = { x: (probe.landmarks[4].x + probe.landmarks[8].x) / 2, y: (probe.landmarks[4].y + probe.landmarks[8].y) / 2 };
  return hand([p[0] - mid.x, p[1] - mid.y], "pinch", opts);
}

export const STEP_MS = 33;

/** Feeds `n` frames produced by make(i) at ~30 fps starting at clock.t; collects all events. */
export function run(logic, clock, n, make) {
  const events = [];
  for (let i = 0; i < n; i++) {
    clock.t += STEP_MS;
    for (const e of logic.feed({ t: clock.t, hands: make(i) })) events.push(e);
  }
  return events;
}

export const types = (ev) => ev.map((e) => e.type);
export const lerp = (a, b, k) => a + (b - a) * k;
export function seeded(seed = 7) {
  let s = seed;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}
