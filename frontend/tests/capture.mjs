// frontend/tests/capture.mjs - headless test of camera sharing: node tests/capture.mjs [baseUrl] [outDir]
// Needs a served build and a backend (voice start is faked in the page, frames are counted at WebSocket.send).
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8713/";
const out = process.argv[3] ?? "/tmp/friday-w1c";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
    "--auto-select-desktop-capture-source=Entire screen"],
});
let failed = 0;
const check = (ok, what) => { console.log(ok ? "PASS" : "FAIL", what); if (!ok) failed++; };

for (const [name, w, h] of [["1440x810", 1440, 810], ["820x1180", 820, 1180]]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, permissions: ["camera"] });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.__sent = [];
    const send = WebSocket.prototype.send;
    WebSocket.prototype.send = function (d) {
      if (typeof d === "string") { try { const m = JSON.parse(d); window.__sent.push({ t: m.t, source: m.source, bytes: m.data_b64 ? Math.floor(m.data_b64.length * 3 / 4) : 0, at: performance.now() }); } catch {} }
      return send.call(this, d);
    };
  });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.goto(`${base}?particles=3000&px=1&bloom=0&noorb`);
  await page.waitForSelector("#camerabtn");
  const boxes = await page.$$eval("#dock > button:not([hidden])", (bs) => bs.map((b) => b.getBoundingClientRect().toJSON()));
  check(boxes.length >= 3 && boxes.every((b) => b.width >= 44 && b.height >= 44), `${name}: ${boxes.length} dock buttons >= 44px`);
  check(boxes.every((b) => b.left >= 0 && b.right <= w), `${name}: dock fits the viewport`);
  const screenVisible = await page.$eval("#screenbtn", (b) => !b.hidden);
  console.log(`${name}: screen button visible = ${screenVisible}`);

  await page.click("#camerabtn");
  await page.waitForSelector("#capprev:not([hidden])");
  await page.waitForTimeout(3500);
  const idleFrames = await page.evaluate(() => window.__sent.filter((m) => m.t === "frame").length);
  check(idleFrames === 0, `${name}: no frames while voice is off (${idleFrames})`);
  check(await page.$eval("#capnote", (n) => n.classList.contains("show")), `${name}: hint shown while voice is off`);
  await page.screenshot({ path: `${out}/hud-idle-${name}.png` });

  // Fake the voice state: the real mic start needs a user gesture plus the Live API.
  await page.evaluate(() => window.__friday.voiceActive(true));
  await page.waitForTimeout(6500);
  await page.screenshot({ path: `${out}/hud-live-${name}.png` });
  const frames = await page.evaluate(() => window.__sent.filter((m) => m.t === "frame"));
  const gaps = frames.slice(1).map((f, i) => f.at - frames[i].at);
  console.log(`${name}: ${frames.length} frames, max ${Math.max(...frames.map((f) => f.bytes))} B, gaps ms ${gaps.map(Math.round)}`);
  check(frames.length >= 5 && frames.length <= 8, `${name}: about 1 frame per second`);
  check(frames.every((f) => f.bytes > 1000 && f.bytes <= 400_000 && f.source === "camera"), `${name}: frame size <= 400 kB, source camera`);

  await page.evaluate(() => window.__friday.voiceActive(false));
  await page.waitForTimeout(300);
  const stops = await page.evaluate(() => window.__sent.filter((m) => m.t === "frames_stop").length);
  check(stops === 1, `${name}: frames_stop sent on voice stop`);
  const state = await page.evaluate(() => ({ hidden: document.getElementById("capprev").hidden, on: document.getElementById("camerabtn").classList.contains("on") }));
  check(state.hidden && !state.on, `${name}: preview hidden and button off after voice stop`);
  const after = await page.evaluate(() => window.__sent.filter((m) => m.t === "frame").length);
  await page.waitForTimeout(2200);
  check(after === await page.evaluate(() => window.__sent.filter((m) => m.t === "frame").length), `${name}: no frames after stop`);
  check(errs.length === 0, `${name}: no page errors ${errs.join("|")}`);
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
