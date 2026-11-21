// frontend/tests/echogate.mjs
// Unit test of the half-duplex echo gate. Run: node tests/echogate.mjs (Node >= 22.18 strips the TypeScript types).
import assert from "node:assert/strict";
import { EchoGate, GATE, pcmRms, speakerMode } from "../src/audio/echogate.ts";

const F = 20; // frame length in ms

/** Feeds `ms` of constant-RMS frames; returns {t, passed: [bool]}. */
function run(g, t, ms, rms, playing) {
  const passed = [];
  for (let i = 0; i < ms / F; i++) passed.push(g.push(rms, playing, (t += F), F));
  return { t, passed };
}

// 1. Not speaking: everything passes, also quiet frames.
let g = new EchoGate();
let r = run(g, 0, 1000, 0.01, false);
assert.ok(r.passed.every(Boolean), "idle passes");

// 2. Simulated echo at 0.05 RMS during playback stays gated, and the floor is learned.
r = run(g, r.t, 3000, 0.05, true);
assert.ok(r.passed.every((p) => !p), "echo gated");
assert.ok(Math.abs(g.floor - 0.05) < 0.005, `floor learned ${g.floor}`);
assert.ok(Math.abs(g.threshold - 3 * g.floor) < 1e-9 && g.threshold >= GATE.minThreshold, "threshold = 3x floor (0.15)");
assert.equal(new EchoGate().threshold, GATE.minThreshold, "fresh gate uses the 0.12 minimum");

// 3. Speech at 0.3 RMS opens the gate within 200 ms.
r = run(g, r.t, 400, 0.3, true);
const firstOpen = r.passed.indexOf(true);
assert.ok(firstOpen >= 0 && (firstOpen + 1) * F <= GATE.bargeMs, `opened after ${(firstOpen + 1) * F} ms`);
assert.ok(r.passed.slice(firstOpen).every(Boolean), "stays open while speaking");

// 4. A short loud burst (< 200 ms) does not open it.
g = new EchoGate();
r = run(g, 0, 1000, 0.05, true);
let b = run(g, r.t, 160, 0.4, true);
assert.ok(b.passed.every((p) => !p), "160 ms click stays gated");
b = run(g, b.t, 200, 0.05, true);
assert.ok(b.passed.every((p) => !p), "and the burst counter reset");

// 5. Hold after speech: gate stays open ~600 ms of silence-level echo, then closes while she still speaks.
g = new EchoGate();
r = run(g, 0, 500, 0.05, true);
r = run(g, r.t, 400, 0.3, true);
const after = run(g, r.t, 1000, 0.05, true);
const closeAt = after.passed.indexOf(false) * F;
assert.ok(closeAt >= GATE.holdMs - F && closeAt <= GATE.holdMs + F, `closed after ${closeAt} ms hold`);

// 6. Tail: playback ends, the gate stays closed for 350 ms, then passes.
g = new EchoGate();
r = run(g, 0, 1000, 0.05, true);
const tail = run(g, r.t, 600, 0.05, false);
const reopen = tail.passed.indexOf(true) * F;
assert.ok(tail.passed.slice(0, 15).every((p) => !p), "closed in the first 300 ms");
assert.ok(reopen >= GATE.tailMs - F && reopen <= GATE.tailMs + F, `reopened after ${reopen} ms`);

// 7. Adaptation: a loud echo (0.2 RMS) raises the threshold to 3x; 0.3 speech then no longer opens, 0.8 does.
g = new EchoGate();
r = run(g, 0, 1500, 0.2, true);
assert.ok(g.floor > 0.18 && Math.abs(g.threshold - 3 * g.floor) < 1e-9, `threshold ${g.threshold}`);
b = run(g, r.t, 600, 0.3, true);
assert.ok(b.passed.every((p) => !p), "0.3 is not clearly louder than a 0.2 echo");
b = run(g, b.t, 400, 0.8, true);
assert.ok(b.passed.some(Boolean), "0.8 opens");
// ... and the learned floor decays between her turns, so the next turn starts with a lower threshold.
g = new EchoGate();
r = run(g, 0, 1500, 0.2, true);
r = run(g, r.t, 8000, 0.01, false);
assert.ok(g.floor < 0.2 && g.floor > 0.03, `floor relaxes in the tail, then decays slowly: ${g.floor}`);

// 7b. The learning window: a loud echo at the very start of a turn never opens the gate.
g = new EchoGate();
assert.ok(run(g, 0, 280, 0.2, true).passed.every((p) => !p), "first 300 ms of a turn only learn");

// 8. Disabled gate (headphones): always passes.
g = new EchoGate();
g.enabled = false;
assert.ok(run(g, 0, 500, 0.05, true).passed.every(Boolean), "disabled passes during playback");

// 9. Helpers.
const pcm = new Int16Array(100).fill(16384);
assert.ok(Math.abs(pcmRms(pcm.buffer) - 0.5) < 1e-6);
assert.equal(pcmRms(new ArrayBuffer(0)), 0);
assert.equal(speakerMode("1", true), false);
assert.equal(speakerMode("0", false), true);
assert.equal(speakerMode(null, true), true);
assert.equal(speakerMode(null, false), false);

console.log("echogate: all checks passed");
