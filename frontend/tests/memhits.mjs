// frontend/tests/memhits.mjs - pure logic of the memory search view: node --experimental-strip-types tests/memhits.mjs
import assert from "node:assert/strict";
import { cleanHits, countText, highlightIds, orbLevel, parseSearch, relTime, scoreRatio, truncate, HL_DIM } from "../src/views/memory_hits_logic.ts";

const T = (...a) => new Date(...a).getTime();
const now = T(2026, 10, 21, 15, 0, 0); // 21. 11. 2026 15:00 local
let n = 0;
const ok = (name, fn) => { fn(); n++; console.log("ok -", name); };

ok("relTime", () => {
  assert.equal(relTime(0, now), "");
  assert.equal(relTime(now - 20e3, now), "prave ted");
  assert.equal(relTime(now - 5 * 60e3, now), "pred 5 min");
  assert.equal(relTime(now - 2 * 3600e3 - 60e3, now), "pred 2 h");
  assert.equal(relTime(T(2026, 10, 20, 9, 0), now), "vcera");
  assert.equal(relTime(T(2026, 10, 18, 9, 0), now), "pred 3 dny");
  assert.equal(relTime(T(2026, 10, 12, 9, 0), now), "12. 11.");
  assert.equal(relTime(T(2025, 2, 3, 9, 0), now), "3. 3. 2025");
});
ok("truncate", () => {
  assert.equal(truncate("abc"), "abc");
  const t = truncate("x".repeat(80));
  assert.equal(Array.from(t).length, 60);
  assert.ok(t.endsWith("\u2026"));
  assert.equal(truncate("y".repeat(60)), "y".repeat(60));
});
ok("scoreRatio", () => {
  assert.equal(scoreRatio(0.5, 1), 0.5);
  assert.equal(scoreRatio(0, 1), 0.04);
  assert.equal(scoreRatio(3, 2), 1);
  assert.equal(scoreRatio(1, 0), 0.04);
});
ok("cleanHits order, cap, kinds", () => {
  const raw = Array.from({ length: 20 }, (_, i) => ({ id: `m${i}`, label: `L${i}`, kind: i === 3 ? "weird" : "memory", score: i % 5 }));
  raw.push({ id: "", score: 9 }, null, { score: 9 });
  const hits = cleanHits(raw);
  assert.equal(hits.length, 12);
  assert.deepEqual(hits.slice(0, 4).map((h) => h.id), ["m4", "m9", "m14", "m19"]); // score 4, stable
  assert.ok(hits.every((h, i) => i === 0 || hits[i - 1].score >= h.score));
  assert.equal(cleanHits([{ id: "a", kind: "weird" }])[0].kind, "concept");
  assert.deepEqual(cleanHits("nope"), []);
});
ok("parseSearch", () => {
  assert.equal(parseSearch({ nodes: [], links: [] }), null);
  assert.equal(parseSearch(null), null);
  const s = parseSearch({ query: "  nginx  ", highlight: ["a", 5, "b"], hits: [{ id: "a", score: 1 }], summary: "s".repeat(500) });
  assert.equal(s.query, "nginx");
  assert.deepEqual(s.highlight, ["a", "b"]);
  assert.equal(s.summary.length, 400);
  assert.ok(parseSearch({ query: "nic", highlight: [] })); // "nothing found" is still a search state
});
ok("highlightIds ignores unknown and duplicate ids, keeps relevance order", () => {
  const known = new Set(["a", "b", "c"]);
  assert.deepEqual(highlightIds(["c", "zzz", "a", "c", "b"], (id) => known.has(id)), ["c", "a", "b"]);
  assert.deepEqual(highlightIds([], () => true), []);
});
ok("orbLevel dim levels", () => {
  assert.equal(HL_DIM, 0.35);
  assert.equal(orbLevel(1, false, false, false), 1); // no search: untouched
  assert.equal(orbLevel(1, true, true, false), 1); // result node
  assert.equal(orbLevel(1, true, false, false), 0.35); // receded
  assert.equal(orbLevel(0.3, true, false, false), 0.3); // never raised
  assert.equal(orbLevel(1, true, false, true), 1); // reached by hover/selection focus
});
ok("countText", () => {
  assert.deepEqual([0, 1, 2, 4, 5, 12].map(countText), ["nic nenalezeno", "1 vysledek", "2 vysledky", "4 vysledky", "5 vysledku", "12 vysledku"]);
});
console.log(`memhits ok (${n} groups)`);
