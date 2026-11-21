// frontend/tests/entities.mjs - pure logic of entities and links (no WebGL): node --experimental-strip-types tests/entities.mjs
import assert from "node:assert/strict";
import { glyphForEntity, tileSize, shortTitle, isEntityRef } from "../src/scene/entity_logic.ts";
import { curveAt, curvePoints, trim, flowAt, linkVisible, SAMPLES } from "../src/scene/kinds/link_math.ts";

// glyph choice by shape and by file extension of a generic doc
assert.equal(glyphForEntity("book", "x"), "book");
assert.equal(glyphForEntity("tool", "read_file"), "tool");
assert.equal(glyphForEntity("weird", "x"), "note");
assert.equal(glyphForEntity("doc", "main.py"), "code");
assert.equal(glyphForEntity("doc", "data.csv"), "table");
assert.equal(glyphForEntity("doc", "song.mp3"), "audio");
assert.equal(glyphForEntity("doc", "pack.zip"), "archive");
assert.equal(glyphForEntity("doc", "notes.txt"), "doc");

// tile keeps the thumbnail aspect, longer side = 3, extreme aspects are clamped
assert.deepEqual(tileSize(2), [3, 1.5]);
assert.deepEqual(tileSize(0.5), [1.5, 3]);
assert.deepEqual(tileSize(1), [3, 3]);
assert.deepEqual(tileSize(100), [3, 0.75]);
assert.deepEqual(tileSize(NaN), [3, 3]);

// title clamp
assert.equal(shortTitle("short"), "short");
assert.equal(shortTitle("x".repeat(40)).length, 28);
assert.ok(shortTitle("x".repeat(40)).endsWith("\u2026"));
assert.ok(isEntityRef({ kind: "entity", ref: { type: "file", id: "a" } }));
assert.ok(!isEntityRef({ kind: "entity" }));
assert.ok(!isEntityRef({ kind: "box", ref: { type: "file", id: "a" } }));

// link endpoint following: the curve starts and ends exactly at the endpoints and moves with them
const a = [0, 1, 0], b = [6, 1, 0];
assert.deepEqual(curveAt(a, b, 0), a);
assert.deepEqual(curveAt(a, b, 1), b);
assert.ok(curveAt(a, b, 0.5)[1] > 1, "curve bows upward");
const pts = curvePoints(a, b);
assert.equal(pts.length, SAMPLES + 1);
const b2 = [6, 1, 8];
assert.deepEqual(curvePoints(a, b2).at(-1), b2, "follows a moved endpoint");
assert.notDeepEqual(curvePoints(a, b2)[SAMPLES >> 1], pts[SAMPLES >> 1]);

// trimming shortens both ends and never inverts a short link
const [ta, tb] = trim(a, b, 1.5);
assert.deepEqual([ta[0], tb[0]], [1.5, 4.5]);
assert.deepEqual(trim([0, 0, 0], [2, 0, 0], 1.5), [[0, 0, 0], [2, 0, 0]]);

// flowing dots stay in [0,1) and advance
for (let i = 0; i < 4; i++) for (const t of [0, 0.7, 12.3, 1e4]) {
  const f = flowAt(i, 4, t);
  assert.ok(f >= 0 && f < 1);
}
assert.notEqual(flowAt(0, 4, 0), flowAt(0, 4, 1));

// hides when an endpoint disappears
assert.equal(linkVisible(true, true, undefined), true);
assert.equal(linkVisible(true, false, undefined), false);
assert.equal(linkVisible(false, true, true), false);
assert.equal(linkVisible(true, true, false), false);
console.log("entities logic ok");
