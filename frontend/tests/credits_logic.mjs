// frontend/tests/credits_logic.mjs
// Run: node --experimental-strip-types tests/credits_logic.mjs
import assert from "node:assert/strict";
import { parseCredits, summaryLabel } from "../src/ui/credits_logic.ts";

const ok = { name: "Chair 1", author: "Quaternius", license: "CC0-1.0", source_page: "https://quaternius.com/packs/x.html" };
assert.deepEqual(parseCredits([ok]), [ok]);
assert.deepEqual(parseCredits("nope"), []);
assert.deepEqual(parseCredits([null, 5, { author: "x" }, { name: "" }]), []);
assert.equal(parseCredits([{ ...ok, source_page: "javascript:alert(1)" }])[0].source_page, "");
assert.equal(parseCredits([{ ...ok, source_page: "http://insecure.example/x" }])[0].source_page, "");
assert.equal(parseCredits([{ ...ok, name: "x".repeat(900) }])[0].name.length, 200);
assert.equal(parseCredits(Array.from({ length: 900 }, () => ok)).length, 500);
assert.equal(summaryLabel(0), "Zatim zadne");
assert.equal(summaryLabel(1), "1 model");
assert.equal(summaryLabel(3), "3 modely");
assert.equal(summaryLabel(7), "7 modelu");
console.log("credits_logic ok");
