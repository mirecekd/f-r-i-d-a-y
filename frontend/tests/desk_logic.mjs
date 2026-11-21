// frontend/tests/desk_logic.mjs - pure logic of the entity bar, the Deck and the drop projection: node --experimental-strip-types tests/desk_logic.mjs
import assert from "node:assert/strict";
import { projectPoint, ndcToPixels, rayHitsPlaneY, dropPositionOnDesk, placeBar, keyAction, isTypingTarget, DESK_Y } from "../src/ui/entitybar_logic.ts";
import { relativeTime, provenance, filterItems, sortItems, typeChips, parseTags, gridMove, toSeconds } from "../src/ui/deck_logic.ts";

// Camera at (0, 5, 10) looking at the origin, fov 50, aspect 1.6 (column-major matrices built by hand).
const near = 0.1, far = 200, fov = (50 * Math.PI) / 180, aspect = 1.6;
const f = 1 / Math.tan(fov / 2);
const proj = [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, (2 * far * near) / (near - far), 0];
const projInv = [aspect / f, 0, 0, 0, 0, 1 / f, 0, 0, 0, 0, 0, (near - far) / (2 * far * near), 0, 0, -1, (far + near) / (2 * far * near)];
const eye = [0, 5, 10], len = Math.hypot(...eye);
const z = eye.map((v) => v / len); // camera looks along -z
const x = [1, 0, 0];
const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
const world = [...x, 0, ...y, 0, ...z, 0, ...eye, 1];
const view = [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -(x[0] * eye[0] + x[1] * eye[1] + x[2] * eye[2]), -(y[0] * eye[0] + y[1] * eye[1] + y[2] * eye[2]), -(z[0] * eye[0] + z[1] * eye[1] + z[2] * eye[2]), 1];

// the origin projects to the screen centre; points behind the camera give null
const o = projectPoint(view, proj, [0, 0, 0]);
assert.ok(Math.abs(o.nx) < 1e-9 && Math.abs(o.ny) < 1e-9);
assert.equal(projectPoint(view, proj, [0, 5, 30]), null);
assert.deepEqual(ndcToPixels(0, 0, 1000, 500), { x: 500, y: 250 });
assert.deepEqual(ndcToPixels(-1, 1, 1000, 500), { x: 0, y: 0 });

// round trip: project a desk point, then the drop projection recovers it
const rect = { left: 0, top: 0, width: 1600, height: 1000 };
for (const p of [[0, DESK_Y, 0], [3, DESK_Y, -4], [-5, DESK_Y, 2]]) {
  const s = projectPoint(view, proj, p);
  const px = ndcToPixels(s.nx, s.ny, rect.width, rect.height);
  const back = dropPositionOnDesk(rect, px.x, px.y, world, projInv);
  assert.ok(back && Math.abs(back[0] - p[0]) < 0.02 && Math.abs(back[2] - p[2]) < 0.02, `round trip ${p}`);
  assert.equal(back[1], DESK_Y);
}
// a canvas offset in the window is honoured; outside the canvas and sky above the horizon are misses
const shifted = { left: 100, top: 50, width: 1600, height: 1000 };
assert.ok(dropPositionOnDesk(shifted, 900, 550, world, projInv));
assert.equal(dropPositionOnDesk(shifted, 50, 550, world, projInv), null);
assert.equal(dropPositionOnDesk(rect, 800, 2, world, projInv), null);
assert.equal(dropPositionOnDesk({ left: 0, top: 0, width: 0, height: 0 }, 1, 1, world, projInv), null);
// this camera still looks slightly below the horizon at the top edge: the hit exists but is far (rejected by DESK_LIMIT above)
assert.ok(rayHitsPlaneY(world, projInv, 0, 0.99, DESK_Y)[2] < -100);
// a camera looking up never meets the desk plane
const up = [1, 0, 0, 0, 0, 0.9, 0.43589, 0, 0, -0.43589, 0.9, 0, 0, 5, 10, 1];
assert.equal(rayHitsPlaneY(up, projInv, 0, 0, DESK_Y), null);

// bar placement: above the anchor, flipped below at the top edge, clamped left and right
const view1 = { w: 1000, h: 600 }, bar = { w: 300, h: 56 };
assert.deepEqual(placeBar({ x: 500, y: 300 }, bar, view1), { left: 350, top: 234 });
assert.equal(placeBar({ x: 500, y: 20 }, bar, view1).top, 30);
assert.equal(placeBar({ x: 5, y: 300 }, bar, view1).left, 8);
assert.equal(placeBar({ x: 995, y: 300 }, bar, view1).left, 692);
assert.equal(placeBar({ x: 500, y: 595 }, bar, view1).top, 529);
assert.equal(placeBar({ x: 500, y: 30 }, { w: 300, h: 590 }, view1).top, 8);
assert.equal(placeBar({ x: 500, y: 300 }, { w: 2000, h: 56 }, view1).left, 8);

// keys
assert.equal(keyAction("Delete"), "remove");
assert.equal(keyAction("Backspace"), "remove");
assert.equal(keyAction("Escape"), "deselect");
assert.equal(keyAction("Enter"), "open");
assert.equal(keyAction("a"), null);
assert.ok(isTypingTarget({ tagName: "INPUT" }) && isTypingTarget({ tagName: "div", isContentEditable: true }));
assert.ok(!isTypingTarget({ tagName: "CANVAS" }) && !isTypingTarget(null));

// relative time (seconds and ISO input)
const now = 1_800_000_000;
assert.equal(relativeTime(now - 5, now), "pred chvili");
assert.equal(relativeTime(now - 300, now), "pred 5 min");
assert.equal(relativeTime(now - 3 * 3600, now), "pred 3 hod");
assert.equal(relativeTime(now - 2 * 86400, now), "pred 2 dny");
assert.equal(relativeTime(now - 40 * 86400, now), new Date((now - 40 * 86400) * 1000).toISOString().slice(0, 10));
assert.equal(relativeTime(undefined, now), "");
assert.equal(toSeconds("2026-01-01T00:00:00Z"), 1767225600);
assert.equal(toSeconds(1767225600000), 1767225600);

// provenance
assert.equal(provenance({ parent_ids: [] }), "");
assert.equal(provenance({ parent_ids: ["a", "b"] }), "vznikl z: 2 polozek");

// filter, sort, chips, tags
const item = (id, type, title, upd, pinned = false, tags = [], subtitle = "") => ({ id, type, title, subtitle, created_at: upd, updated_at: upd, pinned, tags, parent_ids: [] });
const items = [item("1", "image", "Zebra", 100, false, ["dum"]), item("2", "file", "alpha.pdf", 300, true), item("3", "image", "beta", 200, true, ["rodina", "dum"], "Praha"), item("4", "file", "Cesta", 50)];
assert.deepEqual(filterItems(items, "image", "").map((i) => i.id), ["1", "3"]);
assert.deepEqual(filterItems(items, "", "dum rodina").map((i) => i.id), ["3"]);
assert.deepEqual(filterItems(items, "", "PRAHA").map((i) => i.id), ["3"]);
assert.deepEqual(filterItems(items, "file", "nothing"), []);
assert.deepEqual(sortItems(items, "newest").map((i) => i.id), ["2", "3", "1", "4"]);
assert.deepEqual(sortItems(items, "pinned").map((i) => i.id), ["2", "3", "1", "4"]);
assert.deepEqual(sortItems(items, "name").map((i) => i.id), ["2", "3", "4", "1"]);
assert.equal(items[0].id, "1"); // inputs are not mutated
assert.deepEqual(typeChips({ file: 2, image: 5, note: 2 }, 9), [{ type: "", count: 9 }, { type: "image", count: 5 }, { type: "file", count: 2 }, { type: "note", count: 2 }]);
assert.deepEqual(parseTags("a, b  a,,c"), ["a", "b", "c"]);
assert.equal(parseTags(Array.from({ length: 20 }, (_, i) => `t${i}`).join(",")).length, 12);

// grid keys over 4 columns and 10 tiles
assert.equal(gridMove(5, "ArrowRight", 4, 10), 6);
assert.equal(gridMove(5, "ArrowLeft", 4, 10), 4);
assert.equal(gridMove(5, "ArrowDown", 4, 10), 9);
assert.equal(gridMove(6, "ArrowDown", 4, 10), 6);
assert.equal(gridMove(1, "ArrowUp", 4, 10), 1);
assert.equal(gridMove(0, "ArrowLeft", 4, 10), 0);
assert.equal(gridMove(3, "End", 4, 10), 9);
assert.equal(gridMove(3, "Home", 4, 10), 0);
assert.equal(gridMove(0, "ArrowDown", 4, 0), -1);

console.log("desk_logic: all assertions passed");
