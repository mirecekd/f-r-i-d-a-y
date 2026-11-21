// frontend/tests/shots.mjs - headless screenshot test: node tests/shots.mjs [baseUrl] [outDir]
// Needs a served build (vite preview or python3 -m http.server 8681 -d dist); no backend required.
// Uses ?lowfx (fewer particles, pixel ratio 1) and CDP screenshots so software GL stays responsive.
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? process.env.FRIDAY_URL ?? "http://127.0.0.1:8681/";
const out = process.argv[3] ?? "/tmp/friday-shots";
const query = process.env.FRIDAY_QUERY ?? "?lowfx&step=0.1";
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist", "--disable-gpu-vsync", "--disable-renderer-backgrounding"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 810 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(60000);
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });

const cdp = await page.context().newCDPSession(page);
const shot = async (name) => {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  const path = `${out}/${name}.png`;
  writeFileSync(path, Buffer.from(data, "base64"));
  console.log("shot:", path);
};
const frames = (n) => page.evaluate((n) => new Promise((res) => {
  let i = 0; const f = () => {
    if (++i >= n) res();
    else requestAnimationFrame(f);
  };
  requestAnimationFrame(f);
}), n);

await page.goto(base + query, { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await frames(5);
console.log("conn:", await page.evaluate(() => document.getElementById("orbstate").textContent));

await page.fill("#input", "ahoj Friday");
await page.keyboard.press("Enter");
console.log("chat msgs:", await page.$$eval(".msg", (e) => e.map((x) => `${x.className}: ${x.textContent}`)));

for (const s of ["idle", "listening", "thinking", "speaking", "drawing"]) {
  await page.evaluate((s) => { __friday.state(s); __friday.level(s === "speaking" ? 0.5 : 0); }, s);
  await frames(14); // fixed 0.1 s steps: state blend (k = 4/s) is settled after ~14 frames
  await shot(s);
}
await page.evaluate(() => {
  __friday.state("idle");
  __friday.player.apply([
    { op: "add", obj: { id: "a", kind: "box", pos: [-5.5, -1, 0], color: "#ff9a3d" } },
    { op: "add", obj: { id: "b", kind: "torus", pos: [-3, 2.6, -2], scale: 2, color: "#b36bff" } },
    { op: "add", obj: { id: "c", kind: "cone", pos: [-3.2, -1.2, 2], scale: [1.4, 2, 1.4], color: "#3dffa0" } }]);
});
await frames(14);
await shot("scene");

const fps = await page.evaluate(() => new Promise((res) => {
  let n = 0; const t0 = performance.now();
  const f = () => {
    n++;
    if (performance.now() - t0 < 2000) requestAnimationFrame(f);
    else res(n / 2);
  };
  requestAnimationFrame(f);
}));
console.log("fps (software GL, " + query + "):", fps);
console.log("errors:", errs);
await browser.close();
