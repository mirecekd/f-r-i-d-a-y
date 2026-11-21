// frontend/tests/lathe_logic.mjs - pure lathe parameter handling: node --experimental-strip-types tests/lathe_logic.mjs
import assert from "node:assert/strict";
import { latheSegments, lathePoints, capProfile, MAX_PROFILE } from "../src/scene/kinds/lathe_logic.ts";

assert.equal(latheSegments(undefined), 32);
assert.equal(latheSegments("8"), 32);
assert.equal(latheSegments(NaN), 32);
assert.equal(latheSegments(1), 3);
assert.equal(latheSegments(500), 96);
assert.equal(latheSegments(7.6), 8);

assert.deepEqual(lathePoints("x"), []);
assert.deepEqual(lathePoints([[1, 2], [1, 2], [3, 4]]), [[1, 2], [3, 4]]);
assert.deepEqual(lathePoints([[-5, 1], [2, 1e9], [Infinity, 0], [NaN, 1], ["a", 1], [1], null]), [[0, 1], [2, 1e4]]);
assert.equal(lathePoints(Array.from({ length: 200 }, (_, i) => [1, i])).length, MAX_PROFILE);

assert.deepEqual(capProfile([[1, 0], [2, 3]], false), [[1, 0], [2, 3]]);
assert.deepEqual(capProfile([[1, 0], [2, 3]], true), [[0, 0], [1, 0], [2, 3], [0, 3]]);
assert.deepEqual(capProfile([[0, 0], [2, 3], [0, 4]], true), [[0, 0], [2, 3], [0, 4]]);
assert.deepEqual(capProfile([[1, 0]], true), [[1, 0]]);
console.log("lathe_logic ok");
