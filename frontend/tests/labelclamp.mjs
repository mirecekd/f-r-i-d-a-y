// frontend/tests/labelclamp.mjs - the on-screen label height must stay inside [MIN, MAX] px at any camera distance.
// Pure maths copy of views/memory_label_clamp.ts (no WebGL needed): node tests/labelclamp.mjs
const MIN = 9, MAX = 18;
const fov = 40 * Math.PI / 180, viewH = 800, h = 4.6;
const px = (dist) => (h * viewH) / (2 * dist * Math.tan(fov / 2));
const clamped = (dist) => { const p = px(dist); const k = p > MAX ? MAX / p : p < MIN ? MIN / Math.max(p, 0.01) : 1; return p * k; };
let bad = 0;
for (const d of [5, 10, 30, 80, 200, 600, 1500, 4000]) {
  const c = clamped(d);
  const ok = c >= MIN - 1e-9 && c <= MAX + 1e-9;
  if (!ok) bad++;
  console.log(`dist ${String(d).padStart(5)}  raw ${px(d).toFixed(1).padStart(8)} px  ->  ${c.toFixed(1).padStart(5)} px  ${ok ? "ok" : "BAD"}`);
}
if (bad) { console.error("clamp failed"); process.exit(1); }
console.log("label clamp ok");
