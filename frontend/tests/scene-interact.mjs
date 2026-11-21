// frontend/tests/scene-interact.mjs - tween, explode and click-select checks: node tests/scene-interact.mjs [port]
import { chromium } from "playwright-core";
const port = process.argv[2] ?? "8683";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage();
await p.setViewportSize({ width: 1440, height: 810 });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await p.goto(`http://127.0.0.1:${port}/?noorb`, { waitUntil: "networkidle" });
await p.waitForSelector("#orbstate:not(:empty)");
await sleep(1500);
const r = await p.evaluate(async () => {
  const pl = __friday.player;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = {};
  pl.apply([{ op: "clear" }, { op: "camera", pos: [0, 0, 9], look: [0, 0, 0] },
    { op: "add", obj: { id: "g", kind: "group", pos: [0, 0, 0] } },
    { op: "add", obj: { id: "a", kind: "box", parent: "g", pos: [-1, 0, 0], scale: 1.5, color: "#ff0000" } },
    { op: "add", obj: { id: "b", kind: "sphere", parent: "g", pos: [1, 0, 0] } },
    { op: "add", obj: { id: "c", kind: "box", pos: [-4, 0, 0] } }]);
  await sleep(300);
  const wp = (id) => { const v = pl.entries.get(id).node.getWorldPosition(new pl.root.position.constructor()); return v.toArray().map((x) => +x.toFixed(2)); };
  out.before = { a: wp("a"), c: wp("c") };
  pl.apply([{ op: "explode", factor: 1 }]);
  await sleep(1500);
  out.exploded = { a: wp("a"), b: wp("b"), c: wp("c") };
  pl.apply([{ op: "explode", factor: 0 }]);
  await sleep(1500);
  out.restored = { a: wp("a"), c: wp("c") };
  pl.apply([{ op: "set", id: "c", props: { pos: [-4, 3, 0], color: "#00ff00" }, ms: 1000 }]);
  await sleep(500);
  out.tweenMid = wp("c");
  await sleep(900);
  out.tweenEnd = wp("c");
  const picked = [];
  pl.onSelect = (ids) => picked.push(ids);
  const v = pl.entries.get("c").node.getWorldPosition(new pl.root.position.constructor()).project(__friday.camera);
  out.px = [(v.x + 1) / 2 * innerWidth, (1 - v.y) / 2 * innerHeight];
  out.picked = picked;
  return out;
});
await p.mouse.click(r.px[0], r.px[1]);
await sleep(300);
r.pickedAfterClick = await p.evaluate(() => __friday.player.selection.ids);
await p.mouse.click(60, 400);
await sleep(300);
r.pickedAfterEmptyClick = await p.evaluate(() => __friday.player.selection.ids);
console.log(JSON.stringify(r, null, 1));
await b.close();
