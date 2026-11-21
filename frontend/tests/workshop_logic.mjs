// frontend/tests/workshop_logic.mjs - pure Workshop logic: node --experimental-strip-types tests/workshop_logic.mjs
import assert from "node:assert/strict";
import {
  EMPTY_STATE, reduce, leaveCam, routeServerMessage, normParams, sameParamShape, formatValue, parseField, showHint,
  workshopKeyAction, toggleMessage, dropChatText, removeSourceText, toCam,
} from "../src/ui/workshop_logic.ts";
import { ParamThrottle } from "../src/ui/workshop_throttle.ts";
import { snapshotSize, dataUrlBytes, encodeSnapshot } from "../src/ui/workshop_snapshot.ts";

const P = { name: "width", label: "Sirka", value: 5, min: 1, max: 10, step: 0.5, unit: "cm" };
const HOME = { pos: [0, 1, 9], look: [0, 0, 0] };
const enter = { t: "workshop", op: "enter", id: "w1", title: "Zidle", origin: [0, 0, 400], camera: { pos: [0, 3, 410], look: [0, 1, 400] }, home: HOME, params: [P], sources: [{ entity_id: "e1", title: "a.png", kind: "image" }], notes: ["x"] };

// reducer
let s = reduce(EMPTY_STATE, enter);
assert.equal(s.open, true); assert.equal(s.id, "w1"); assert.equal(s.params.length, 1); assert.equal(s.sources[0].entity_id, "e1");
assert.deepEqual(s.home, HOME); assert.deepEqual(s.notes, ["x"]);
assert.deepEqual(reduce(EMPTY_STATE, { ...enter, home: undefined }, { pos: [1, 1, 1], look: [0, 0, 0] }).home, { pos: [1, 1, 1], look: [0, 0, 0] });
s = reduce(s, { t: "workshop", op: "params", id: "w1", params: [{ ...P, value: 7 }], notes: [] });
assert.equal(s.params[0].value, 7); assert.deepEqual(s.notes, []); assert.equal(s.sources.length, 1);
assert.equal(reduce(s, { t: "workshop", op: "params", id: "other", params: [] }), s);
assert.equal(reduce(EMPTY_STATE, { t: "workshop", op: "params", id: "w1", params: [P] }).open, false);
assert.equal(reduce(s, { t: "chat" }), s);
assert.deepEqual(leaveCam(s, { camera: { pos: [1, 2, 3], look: [0, 0, 0] } }), { pos: [1, 2, 3], look: [0, 0, 0] });
assert.deepEqual(leaveCam(s, {}), HOME);
const left = reduce(s, { t: "workshop", op: "leave", id: "w1" });
assert.equal(left.open, false); assert.equal(left.params.length, 0);
assert.equal(toCam({ pos: [1, 2], look: [0, 0, 0] }), null);
assert.equal(toCam({ pos: [1, 2, NaN], look: [0, 0, 0] }), null);

// params
assert.deepEqual(normParams([{ name: "a", value: 99, min: 0, max: 10 }, { name: "bad", value: "x", min: 0, max: 1 }, { value: 1, min: 0, max: 1 }, null]).map((p) => [p.name, p.value, p.step]), [["a", 10, 0.1]]);
assert.equal(normParams("nope").length, 0);
assert.ok(sameParamShape([P], [{ ...P, value: 9 }])); assert.ok(!sameParamShape([P], [{ ...P, max: 11 }])); assert.ok(!sameParamShape([P], []));
assert.equal(formatValue(5, 0.5), "5.0"); assert.equal(formatValue(5, 1), "5"); assert.equal(formatValue(0.125, 0.01), "0.13");
assert.equal(parseField("12", P), 10); assert.equal(parseField("2,5", P), 2.5); assert.equal(parseField("", P), null); assert.equal(parseField("abc", P), null);
assert.ok(showHint(EMPTY_STATE)); assert.ok(!showHint(s));

// routing
assert.equal(routeServerMessage({ t: "workshop" }), "state"); assert.equal(routeServerMessage({ t: "workshop_snapshot_request" }), "snapshot"); assert.equal(routeServerMessage({ t: "chat" }), "ignore");

// throttle: 12 per second, first immediate, last value always arrives
{
  let now = 0; const sent = []; const timers = [];
  const th = new ParamThrottle((n, v) => sent.push([n, v, now]), () => now, (fn, ms) => { timers.push({ fn, at: now + ms }); return timers.length - 1; }, (h) => { timers[h] = null; });
  const run = (to) => { for (let t = now; t <= to; t++) { now = t; for (let i = 0; i < timers.length; i++) { const x = timers[i]; if (x && x.at <= now) { timers[i] = null; x.fn(); } } } };
  for (let t = 0; t <= 1000; t += 10) { now = t; th.push("w", t); run(t); }
  run(1100);
  assert.ok(sent.length <= 13 && sent.length >= 11, `sent ${sent.length}`);
  assert.equal(sent[0][1], 0); assert.equal(sent.at(-1)[1], 1000);
  for (let i = 1; i < sent.length; i++) assert.ok(sent[i][2] - sent[i - 1][2] >= 83, "gap");
  const n = sent.length; th.push("w", 5); th.flush("w"); assert.equal(sent.length, n + 1); assert.equal(sent.at(-1)[1], 5);
  th.push("a", 1); th.push("b", 2); assert.equal(sent.filter((x) => x[0] !== "w").length, 2);
}

// snapshot sizing and encoding loop
assert.deepEqual(snapshotSize(2000, 1000, 1024), { w: 1024, h: 512 }); assert.deepEqual(snapshotSize(800, 600, 1024), { w: 800, h: 600 });
assert.deepEqual(snapshotSize(4000, 2000, 5000), { w: 1024, h: 512 }); assert.deepEqual(snapshotSize(1000, 500, 400), { w: 400, h: 200 });
assert.equal(dataUrlBytes("data:image/jpeg;base64," + "A".repeat(8)), 6); assert.equal(dataUrlBytes("data:x;base64,QQ=="), 1);
{
  const fat = "data:image/jpeg;base64," + "A".repeat(1_200_000), thin = "data:image/jpeg;base64," + "QUJD".repeat(10);
  const qs = []; const out = encodeSnapshot((w) => w, (c, q) => { qs.push([c, q]); return q <= 0.6 && c <= 512 ? thin : fat; }, 1024);
  assert.equal(out, "QUJD".repeat(10)); assert.equal(qs[0][1], 0.8); assert.ok(qs.some(([c]) => c === 768) && qs.at(-1)[0] === 512);
  assert.equal(encodeSnapshot((w) => w, () => fat, 1024), null);
  assert.equal(encodeSnapshot((w) => w, () => thin, 1024), "QUJD".repeat(10));
}

// keys
const k = (key, o = {}) => ({ key, ctrlKey: false, metaKey: false, altKey: false, defaultPrevented: false, ...o });
const free = { open: false, typing: false, blocked: false }, inside = { ...free, open: true };
assert.equal(workshopKeyAction(k("w"), free), "toggle"); assert.equal(workshopKeyAction(k("W"), inside), "toggle");
assert.equal(workshopKeyAction(k("w"), { ...free, typing: true }), null); assert.equal(workshopKeyAction(k("w", { ctrlKey: true }), free), null);
assert.equal(workshopKeyAction(k("Escape"), inside), "leave"); assert.equal(workshopKeyAction(k("Escape"), free), null);
assert.equal(workshopKeyAction(k("Escape"), { ...inside, blocked: true }), null);
assert.deepEqual(toggleMessage(s, null, null), { t: "workshop_leave" });
assert.deepEqual(toggleMessage(EMPTY_STATE, "w9", "w1"), { t: "workshop_open", id: "w9" });
assert.deepEqual(toggleMessage(EMPTY_STATE, null, "w1"), { t: "workshop_open", id: "w1" });
assert.deepEqual(toggleMessage(EMPTY_STATE, null, null), { t: "workshop_new" });
assert.equal(dropChatText("a.png", "id1"), "Pridej do dilny a.png (id1)"); assert.equal(removeSourceText("a.png"), "Odeber zdroj a.png z dilny");
console.log("workshop_logic: all ok");
