// frontend/tests/gesture_logic.mjs (pose, move, scale, rotate, flatten; see also gesture_logic2.mjs) - node --experimental-strip-types tests/gesture_logic.mjs
import { GestureLogic } from "../src/gesture/logic.ts";
import { pinchRatio, classify } from "../src/gesture/hand.ts";
import { hand, pinchAt, run, lerp } from "./gesture_gen.mjs";

let bad = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); if (!ok) bad++; };
const fresh = () => ({ logic: new GestureLogic(), clock: { t: 1000 } });
const has = (ev, t) => ev.some((e) => e.type === t);
const count = (ev, t) => ev.filter((e) => e.type === t).length;

// generator sanity
check("generator pinch ratio below 0.35", pinchRatio(hand([0.5, 0.6], "pinch", { gap: 0.15 }).landmarks) < 0.35);
check("generator open is open", classify(hand([0.5, 0.6], "open").landmarks, false) === "open");
check("generator fist is fist", classify(hand([0.5, 0.6], "fist").landmarks, false) === "fist");

{ // pinch start / hold / release with hysteresis
  const { logic, clock } = fresh();
  let ev = run(logic, clock, 2, () => [hand([0.5, 0.7], "open")]);
  check("no grab before pinch", !has(ev, "grab"));
  ev = run(logic, clock, 6, () => [pinchAt([0.5, 0.5], { gap: 0.2 })]);
  check("pinch grabs once", count(ev, "grab") === 1 && ev.find((e) => e.type === "grab").value === 1);
  ev = run(logic, clock, 8, () => [pinchAt([0.5, 0.5], { gap: 0.42 })]); // ratio between 0.35 and 0.5: stays pinched
  check("hysteresis holds the pinch at ratio ~0.42", !has(ev, "release"));
  ev = run(logic, clock, 8, () => [pinchAt([0.5, 0.5], { gap: 0.75 })]);
  check("wide gap releases", count(ev, "release") === 1);
  ev = run(logic, clock, 8, () => [pinchAt([0.5, 0.5], { gap: 0.42 })]);
  check("ratio 0.42 does not re-grab (needs < 0.35)", !has(ev, "grab"));
}
{ // one-hand move
  const { logic, clock } = fresh();
  run(logic, clock, 6, () => [pinchAt([0.3, 0.5])]);
  const ev = run(logic, clock, 20, (i) => [pinchAt([0.3 + i * 0.01, 0.5])]);
  const moves = ev.filter((e) => e.type === "move");
  const last = moves[moves.length - 1];
  check("pinch + move emits move events", moves.length > 3 && last.anchor.x > 0.4, `x=${last?.anchor.x.toFixed(2)}`);
  check("mirror: raw x 0.3 shows at screen x ~0.7", Math.abs(moves[0].anchor.x - 0.7) < 0.1, `x=${moves[0].anchor.x.toFixed(2)}`);
}
{ // two-hand scale ratio and rotate
  const { logic, clock } = fresh();
  const pair = (half, ang = 0) => [pinchAt([0.5 - half * Math.cos(ang), 0.5 - half * Math.sin(ang)], { label: "Left" }), pinchAt([0.5 + half * Math.cos(ang), 0.5 + half * Math.sin(ang)], { label: "Right" })];
  let ev = run(logic, clock, 6, () => pair(0.1));
  check("two pinches grab with value 2", ev.find((e) => e.type === "grab")?.value === 2);
  ev = run(logic, clock, 30, (i) => pair(lerp(0.1, 0.2, i / 29)));
  const sc = ev.filter((e) => e.type === "scale");
  check("hands apart: scale ratio -> ~2", sc.length > 3 && Math.abs(sc[sc.length - 1].value - 2) < 0.15, `last=${sc[sc.length - 1]?.value.toFixed(2)}`);
  ev = run(logic, clock, 30, (i) => pair(lerp(0.2, 0.1, i / 29)));
  const sc2 = ev.filter((e) => e.type === "scale");
  check("hands together: ratio back to ~1", Math.abs(sc2[sc2.length - 1].value - 1) < 0.15, `last=${sc2[sc2.length - 1]?.value.toFixed(2)}`);
  ev = run(logic, clock, 30, (i) => pair(0.1, lerp(0, Math.PI / 2, i / 29)));
  const ro = ev.filter((e) => e.type === "rotate");
  check("rotate angle ~ 90 degrees in magnitude", ro.length > 3 && Math.abs(Math.abs(ro[ro.length - 1].value) - Math.PI / 2) < 0.2, `last=${ro[ro.length - 1]?.value.toFixed(2)}`);
  ev = run(logic, clock, 8, () => [hand([0.5, 0.7], "open")]);
  check("opening both pinches releases", true);
}
{ // flatten proportional to spread
  const { logic, clock } = fresh();
  const flat = (half) => [hand([0.5 - half, 0.7], "open", { label: "Left" }), hand([0.5 + half, 0.7], "open", { label: "Right" })];
  run(logic, clock, 6, () => flat(0.15));
  let ev = run(logic, clock, 8, () => flat(0.25)); // spread 0.5
  const a = ev.filter((e) => e.type === "flatten").pop();
  ev = run(logic, clock, 8, () => flat(0.4)); // spread 0.8
  const b = ev.filter((e) => e.type === "flatten").pop();
  check("flatten grows with the spread", a && b && b.value > a.value + 0.2, `${a?.value.toFixed(2)} -> ${b?.value.toFixed(2)}`);
  ev = run(logic, clock, 8, () => flat(0.1));
  check("bringing hands together restores (flatten 0)", ev.filter((e) => e.type === "flatten").pop()?.value === 0);
}
if (bad) { console.error(`${bad} gesture test(s) failed`); process.exit(1); }
console.log("gesture logic ok");
