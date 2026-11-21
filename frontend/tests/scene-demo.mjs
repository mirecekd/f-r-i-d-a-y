// frontend/tests/scene-demo.mjs - screenshots of the demo scene: node tests/scene-demo.mjs [port]
import { chromium } from "playwright-core";
const port = process.argv[2] ?? "8683";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage();
await p.setViewportSize({ width: 1440, height: 810 });
const errs = [];
p.on("pageerror", e => errs.push(String(e)));
p.on("console", m => { if (["error", "warning"].includes(m.type())) errs.push(m.text()); });
const sleep = ms => new Promise(r => setTimeout(r, ms));
await p.goto(`http://127.0.0.1:${port}/?noorb`, { waitUntil: "networkidle" });
await sleep(800);
await p.evaluate(() => __friday.send({ t: "demo", what: "scene" }));
await sleep(5000);
await p.screenshot({ path: "/tmp/friday-shots/demo-overview.png" });
const views = { robot: [[-14, 1, 8], [-14, 0, 0]], plan: [[-6, 9, 20], [-8, -3, 8]], graph: [[2, 4, 8], [2, 0, -4]],
  charts: [[-8, 3, 6], [-8, 0, -8]], surface: [[8, 4, 6], [8, -1, -4]], shapes: [[3, 3, 22], [4, -1, 12]] };
for (const [name, [pos, look]] of Object.entries(views)) {
  await p.evaluate(([pos, look]) => __friday.player.apply([{ op: "camera", pos, look }]), [pos, look]);
  await sleep(6000);
  await p.screenshot({ path: `/tmp/friday-shots/demo-${name}.png` });
}
console.log("errors:", errs);
await b.close();
