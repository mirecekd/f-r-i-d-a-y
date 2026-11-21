// frontend/tests/deck_url.mjs - node --experimental-strip-types tests/deck_url.mjs
import assert from "node:assert/strict";

// parseLinkInput is pure; the module imports DOM helpers, so the function body is checked from its source text.
import { readFileSync } from "node:fs";
const src = readFileSync(new URL("../src/ui/deck_url.ts", import.meta.url), "utf8");
const body = src.slice(src.indexOf("export function parseLinkInput"), src.indexOf("/** The small"));
const parseLinkInput = new Function(`${body.replace("export function parseLinkInput(text: string): string | null", "function parseLinkInput(text)")}; return parseLinkInput;`)();

assert.equal(parseLinkInput("https://example.com/a"), "https://example.com/a");
assert.equal(parseLinkInput("example.com"), "https://example.com/");
assert.equal(parseLinkInput("  http://example.com/x?y=1 "), "http://example.com/x?y=1");
assert.equal(parseLinkInput("javascript:alert(1)"), null);
assert.equal(parseLinkInput("file:///etc/passwd"), null);
assert.equal(parseLinkInput("two words"), null);
assert.equal(parseLinkInput(""), null);
assert.equal(parseLinkInput("a".repeat(2100)), null);
console.log("deck_url ok");
