// frontend/tests/gesture_logic2.mjs - crossed arms, open palm, fist, robustness. node --experimental-strip-types tests/gesture_logic2.mjs
import { GestureLogic } from "../src/gesture/logic.ts";
import { hand, pinchAt, run, seeded } from "./gesture_gen.mjs";

let bad = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); if (!ok) bad++; };
const fresh = () => ({ logic: new GestureLogic(), clock: { t: 1000 } });
const has = (ev, t) => ev.some((e) => e.type === t);
const count = (ev, t) => ev.filter((e) => e.type === t).length;

{ // crossed arms
  const mk = (xl, xr) => [hand([xl, 0.7], "other", { label: "Left" }), hand([xr, 0.7], "other", { label: "Right" })];
  let { logic, clock } = fresh();
  run(logic, clock, 6, () => mk(0.25, 0.75));
  let ev = run(logic, clock, 30, () => mk(0.55, 0.45)); // swapped and overlapping for ~1 s
  check("crossed arms >= 400 ms emits close exactly once", count(ev, "close") === 1, `n=${count(ev, "close")}`);
  ({ logic, clock } = fresh());
  run(logic, clock, 6, () => mk(0.25, 0.75));
  ev = run(logic, clock, 6, () => mk(0.55, 0.45)); // ~200 ms
  ev = ev.concat(run(logic, clock, 10, () => mk(0.25, 0.75)));
  check("brief crossing (~200 ms) does NOT close", !has(ev, "close"));
  ({ logic, clock } = fresh());
  run(logic, clock, 6, () => mk(0.75, 0.25)); // flipped label convention
  ev = run(logic, clock, 30, () => mk(0.45, 0.55));
  check("crossing works with the opposite label order", count(ev, "close") === 1);
  ({ logic, clock } = fresh());
  run(logic, clock, 6, () => mk(0.25, 0.75));
  ev = run(logic, clock, 30, () => mk(0.35, 0.65));
  check("hands merely moving closer (not swapped) do not close", !has(ev, "close"));
  ({ logic, clock } = fresh());
  const pp = (a, b) => [pinchAt([a, 0.5], { label: "Left" }), pinchAt([b, 0.5], { label: "Right" })];
  run(logic, clock, 8, () => pp(0.25, 0.75));
  ev = run(logic, clock, 30, () => pp(0.52, 0.48));
  check("crossing while dragging cancels the drag (close value 1, release before)", ev.find((e) => e.type === "close")?.value === 1);
}
{ // open palm hold
  let { logic, clock } = fresh();
  let ev = run(logic, clock, 12, () => [hand([0.5, 0.7], "open")]); // ~400 ms
  check("open palm < 600 ms: no stop", !has(ev, "stop"));
  ev = run(logic, clock, 12, () => [hand([0.5, 0.7], "open")]);
  check("open palm held ~800 ms: stop once", count(ev, "stop") === 1);
  ({ logic, clock } = fresh());
  ev = run(logic, clock, 40, (i) => [hand([0.3 + i * 0.01, 0.7], "open")]);
  check("moving open palm never stops", !has(ev, "stop"));
}
{ // fist releases
  const { logic, clock } = fresh();
  run(logic, clock, 6, () => [pinchAt([0.5, 0.5])]);
  const ev = run(logic, clock, 8, () => [hand([0.5, 0.6], "fist")]);
  check("fist after pinch releases", count(ev, "release") === 1);
}
{ // handedness swap / label flicker keeps the grab
  const { logic, clock } = fresh();
  run(logic, clock, 6, () => [pinchAt([0.3, 0.5], { label: "Left" })]);
  const ev = run(logic, clock, 10, (i) => [pinchAt([0.3, 0.5], { label: i % 2 ? "Right" : "Left" })]);
  check("handedness label flicker does not release", !has(ev, "release") && !has(ev, "grab"));
}
{ // jitter rejection
  const { logic, clock } = fresh();
  const rnd = seeded(3);
  const ev = run(logic, clock, 90, () => [hand([0.5, 0.7], "other", { jitter: 0.004, rnd })]);
  check("noisy idle hand emits nothing", ev.length === 0, `n=${ev.length}`);
  const l2 = fresh();
  const ev2 = run(l2.logic, l2.clock, 6, () => [pinchAt([0.5, 0.5], { jitter: 0.002, rnd })]).concat(run(l2.logic, l2.clock, 60, () => [pinchAt([0.5, 0.5], { jitter: 0.002, rnd })]));
  check("held pinch with jitter: one grab, no release, few moves", count(ev2, "grab") === 1 && !has(ev2, "release") && count(ev2, "move") < 3, `moves=${count(ev2, "move")}`);
  const l3 = fresh();
  const ev3 = run(l3.logic, l3.clock, 40, (i) => [pinchAt([0.5, 0.5], { gap: i % 7 === 3 ? 0.9 : 0.2 })]); // single-frame spikes
  check("single-frame pinch spikes are debounced", count(ev3, "release") === 0);
  const l4 = fresh();
  const ev4 = run(l4.logic, l4.clock, 40, (i) => [i % 9 === 4 ? pinchAt([0.5, 0.5]) : hand([0.5, 0.7], "open")]);
  check("single-frame pinch blips do not grab", !has(ev4, "grab"));
}
{ // dropout
  let { logic, clock } = fresh();
  run(logic, clock, 6, () => [pinchAt([0.5, 0.5])]);
  let ev = run(logic, clock, 3, () => []); // ~100 ms
  ev = ev.concat(run(logic, clock, 6, () => [pinchAt([0.5, 0.5])]));
  check("dropout < 150 ms keeps the grab", !has(ev, "release") && !has(ev, "grab"));
  ({ logic, clock } = fresh());
  run(logic, clock, 6, () => [pinchAt([0.5, 0.5])]);
  ev = run(logic, clock, 14, () => []); // ~460 ms
  check("dropout > 300 ms releases", count(ev, "release") === 1);
}
{ // after a two-hand session one pinch must open first
  const { logic, clock } = fresh();
  const pp = (b) => [pinchAt([0.4, 0.5], { label: "Left" }), ...(b ? [pinchAt([0.6, 0.5], { label: "Right" })] : [])];
  run(logic, clock, 8, () => pp(true));
  const ev = run(logic, clock, 14, () => pp(false)); // the lost hand is kept for 300 ms first
  check("losing one hand of a pair releases, no sudden single grab", count(ev, "release") === 1 && !has(ev, "grab"));
}
if (bad) { console.error(`${bad} gesture test(s) failed`); process.exit(1); }
console.log("gesture logic 2 ok");
