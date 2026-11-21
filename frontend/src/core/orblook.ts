// frontend/src/core/orblook.ts

/** Pure orb look table: one target look per assistant state, blended by stepLook. */
export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "drawing" | "error" | "offline";

/**
 * State palette: ONE table with the orb colour, the label word and the label text colour per state.
 * Edit only this table to change how a state looks. `offline` = websocket down (client-side state).
 */
export const PALETTE: Record<OrbState, { label: string; color: [number, number, number]; text: string }> = {
  idle: { label: "ONLINE", color: [0.15, 0.45, 1.0], text: "#5f9bff" },
  listening: { label: "LISTENING", color: [0.2, 1.0, 0.45], text: "#4dff8a" },
  thinking: { label: "THINKING", color: [1.0, 0.72, 0.1], text: "#ffc233" },
  speaking: { label: "SPEAKING", color: [0.7, 1.0, 1.0], text: "#d8ffff" },
  drawing: { label: "DRAWING", color: [0.85, 0.25, 1.0], text: "#e070ff" },
  error: { label: "ERROR", color: [1.0, 0.2, 0.2], text: "#ff5a5a" },
  offline: { label: "OFFLINE", color: [0.5, 0.06, 0.06], text: "#ff4040" },
};

export interface Look {
  radius: number;
  noise: number;
  spin: number;
  ring: number;
  color: [number, number, number];
}

export const LOOKS: Record<OrbState, Look> = {
  idle: { radius: 1.8, noise: 0.08, spin: 0.08, ring: 0, color: PALETTE.idle.color },
  listening: { radius: 1.55, noise: 0.14, spin: 0.15, ring: 0, color: PALETTE.listening.color },
  thinking: { radius: 1.8, noise: 0.1, spin: 0.9, ring: 1, color: PALETTE.thinking.color },
  speaking: { radius: 1.9, noise: 0.22, spin: 0.2, ring: 0, color: PALETTE.speaking.color },
  drawing: { radius: 2.2, noise: 0.3, spin: 0.5, ring: 0.4, color: PALETTE.drawing.color },
  error: { radius: 1.7, noise: 0.35, spin: 0.05, ring: 0, color: PALETTE.error.color },
  offline: { radius: 1.6, noise: 0.05, spin: 0.03, ring: 0, color: PALETTE.offline.color },
};

export function cloneLook(l: Look): Look {
  return { ...l, color: [...l.color] };
}

/** Moves `cur` towards `to` with exponential smoothing factor k (0..1). */
export function stepLook(cur: Look, to: Look, k: number): void {
  cur.radius += (to.radius - cur.radius) * k;
  cur.noise += (to.noise - cur.noise) * k;
  cur.spin += (to.spin - cur.spin) * k;
  cur.ring += (to.ring - cur.ring) * k;
  for (let i = 0; i < 3; i++) cur.color[i] += (to.color[i] - cur.color[i]) * k;
}
