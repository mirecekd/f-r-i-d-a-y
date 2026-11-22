// frontend/tests/hudstate_logic.mjs - pure task-state logic: node --experimental-strip-types tests/hudstate_logic.mjs
import assert from "node:assert/strict";
import { categoryOf, labelOf, HudStateModel, MIN_SHOW_MS, FADE_AFTER_MS } from "../src/ui/hudstate_logic.ts";

const cases = {
  web_search: "search", web_add: "search", web_read: "search",
  recall: "memory", remember: "memory", today_digest: "memory", show_memory_graph: "memory",
  deck_place: "files", entity_link: "files", read_file: "files", list_files: "files", file_to_scene: "files", summarize_file: "files",
  analyze_image: "images", image_edit: "images", list_images: "images", house_from_sources: "images",
  model_add_part: "building", workshop_build: "building", scene_apply: "building", pack_generate: "building", draw: "building",
  ask_hermes: "tool", mcp_x: "tool", server__do_thing: "tool",
  undo: "work", something_else: "work", "": "work",
};
for (const [name, cat] of Object.entries(cases)) assert.equal(categoryOf(name), cat, name);
assert.equal(labelOf("web_search"), "Hledam");
assert.equal(labelOf("recall"), "Vzpominam");
assert.equal(labelOf("entity_link"), "Pracuji se soubory");
assert.equal(labelOf("analyze_image"), "Divam se na obrazky");
assert.equal(labelOf("scene_apply"), "Stavim");
assert.equal(labelOf("a__b"), "Volam nastroj");
assert.equal(labelOf("undo"), "Pracuji");

// a single tool: shown at start, fades 1.5 s after the end
let m = new HudStateModel();
assert.equal(m.view(0).label, null);
m.start("1", "web_search", 0);
assert.equal(m.view(10).label, "Hledam");
m.end("1", 100);
assert.equal(m.view(100 + FADE_AFTER_MS - 1).label, "Hledam");
assert.equal(m.view(100 + FADE_AFTER_MS).label, null);

// a very fast tool is still shown for at least 600 ms
m = new HudStateModel();
m.start("1", "recall", 1000);
m.end("1", 1005);
assert.equal(m.view(1005 + 100).label, "Vzpominam");
assert.ok(m.nextChangeIn(1105) >= FADE_AFTER_MS - 100 - 1);

// a burst of different tools does not flicker: the label changes at most every 600 ms
m = new HudStateModel();
m.start("1", "web_search", 0);
m.end("1", 50);
m.start("2", "recall", 100);
assert.equal(m.view(200).label, "Hledam");
assert.equal(m.nextChangeIn(200), MIN_SHOW_MS - 200);
assert.equal(m.view(MIN_SHOW_MS).label, "Vzpominam");
m.end("2", 700);
m.start("3", "scene_apply", 720);
m.end("3", 730);
assert.equal(m.view(740).label, "Vzpominam");
assert.equal(m.view(1300).label, "Stavim");
assert.equal(m.view(730 + FADE_AFTER_MS - 1).label, "Stavim");
assert.equal(m.view(730 + FADE_AFTER_MS).label, null);

// a new tool during the fade keeps the line up; unknown ends are ignored
m = new HudStateModel();
m.start("1", "web_search", 0);
m.end("1", 10);
m.end("nope", 20);
m.start("2", "web_search", 1000);
assert.equal(m.view(1700).label, "Hledam");
m.end("2", 1800);
assert.equal(m.view(1800 + FADE_AFTER_MS - 1).label, "Hledam");
assert.equal(m.view(1800 + FADE_AFTER_MS).label, null);

// while a long tool keeps running the line stays
m = new HudStateModel();
m.start("1", "draw", 0);
assert.equal(m.view(60000).label, "Stavim");
assert.equal(m.nextChangeIn(60000), null);
console.log("hudstate_logic ok");
