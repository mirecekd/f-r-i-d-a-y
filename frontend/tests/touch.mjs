// frontend/tests/touch.mjs - tablet touch checks via CDP Input.dispatchTouchEvent: node tests/touch.mjs [port] [outDir]
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const port = process.argv[2] ?? "8702";
const out = process.argv[3] ?? "/tmp/friday-g2";
mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const fails = [];
const check = (name, ok, info = "") => { console.log(ok ? "PASS" : "FAIL", name, info); if (!ok) fails.push(name); };

for (const [w, h] of [[1180, 820], [820, 1180]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  const tag = `${w}x${h}`;
  const shot = async (n) => writeFileSync(`${out}/${tag}-${n}.png`, Buffer.from((await cdp.send("Page.captureScreenshot", { format: "png" })).data, "base64"));
  const touch = (type, pts) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: pts.map(([x, y], id) => ({ x, y, id })), timestamp: Date.now() / 1000 });
  const freeze = async () => { await p.evaluate(() => __gate.set(true)); await sleep(1500); };
  const thaw = () => p.evaluate(() => __gate.set(false));
  const tap = async (x, y, hold = 40) => { await freeze(); await touch("touchStart", [[x, y]]); await sleep(hold); await touch("touchEnd", []); await thaw(); };
  const errs = [];
  p.on("pageerror", (e) => errs.push(String(e)));
  await p.addInitScript(() => { const raf = window.requestAnimationFrame.bind(window); let pend = null; window.__gate = { paused: false };
    window.requestAnimationFrame = (cb) => { if (!window.__gate.paused) return raf(cb); pend = cb; return 0; };
    window.__gate.set = (v) => { window.__gate.paused = v; if (!v && pend) { const c = pend; pend = null; raf(c); } }; });
  await p.addInitScript(() => { window.__sent = []; const s = WebSocket.prototype.send; WebSocket.prototype.send = function (d) { window.__sent.push(String(d)); return s.call(this, d); }; });
  await p.goto(`http://127.0.0.1:${port}/?particles=3000&px=1&bloom=0&noorb`, { waitUntil: "networkidle" });
  await p.waitForSelector("#orbstate:not(:empty)");
  await p.evaluate(() => __friday.player.apply([{ op: "clear" }, { op: "camera", pos: [0, 0, 9], look: [0, 0, 0] },
    { op: "add", obj: { id: "a", kind: "box", pos: [-2, 0, 0], scale: 1.4, color: "#4fd8ff", label: "Kostka" } },
    { op: "add", obj: { id: "b", kind: "sphere", pos: [2, 0, 0], scale: 1.4, color: "#ffc866" } }]));
  await sleep(4000);
  const px = (id) => p.evaluate((id) => { const pl = __friday.player; const v = pl.entries.get(id).node.getWorldPosition(new pl.root.position.constructor()).project(__friday.camera); return [(v.x + 1) / 2 * innerWidth, (1 - v.y) / 2 * innerHeight]; }, id);
  const sel = () => p.evaluate(() => __friday.player.selection.ids);
  const cam = () => p.evaluate(() => { const c = __friday.camera; return { p: c.position.toArray(), d: c.position.length() }; });
  const [ax, ay] = await px("a");

  await tap(ax, ay);
  await sleep(300);
  check(`${tag} tap selects a`, JSON.stringify(await sel()) === '["a"]', JSON.stringify(await sel()));
  await shot("1-tap-select");
  await tap(w / 2, 120);
  await sleep(300);
  check(`${tag} tap empty clears`, (await sel()).length === 0);

  const before = await cam();
  await freeze(); await touch("touchStart", [[ax, ay]]); await touch("touchMove", [[ax + 40, ay + 20]]); await sleep(50);
  await touch("touchMove", [[ax + 80, ay + 30]]); await touch("touchEnd", []); await thaw();
  await sleep(500);
  const afterDrag = await cam();
  check(`${tag} one-finger drag orbits and does not select`, Math.abs(afterDrag.p[0] - before.p[0]) > 0.3 && (await sel()).length === 0, JSON.stringify([before.p, afterDrag.p]));

  const d0 = (await cam()).d;
  let [x1, x2] = [w / 2 - 40, w / 2 + 40];
  await freeze();
  await touch("touchStart", [[x1, h / 2], [x2, h / 2]]);
  for (let i = 1; i <= 8; i++) { await touch("touchMove", [[x1 - i * 20, h / 2], [x2 + i * 20, h / 2]]); await sleep(40); }
  await touch("touchEnd", []); await thaw();
  await sleep(600);
  const d1 = (await cam()).d;
  check(`${tag} pinch out zooms in`, d1 < d0 - 0.5, `${d0.toFixed(2)} -> ${d1.toFixed(2)}`);

  const t0 = await p.evaluate(() => __friday.camera.position.toArray());
  await freeze();
  await touch("touchStart", [[w / 2 - 40, h / 2], [w / 2 + 40, h / 2]]);
  for (let i = 1; i <= 8; i++) { await touch("touchMove", [[w / 2 - 40 + i * 20, h / 2 + i * 10], [w / 2 + 40 + i * 20, h / 2 + i * 10]]); await sleep(40); }
  await touch("touchEnd", []); await thaw();
  await sleep(600);
  const t1 = await p.evaluate(() => __friday.camera.position.toArray());
  check(`${tag} two-finger drag pans`, Math.hypot(...t1.map((v, i) => v - t0[i])) > 0.1 && Math.abs((await cam()).d - d1) < 1, JSON.stringify([t0, t1]));

  await p.evaluate(() => __friday.player.apply([{ op: "camera", pos: [0, 0, 9], look: [0, 0, 0] }]));
  await sleep(5000);
  const [cx, cy] = await px("a");
  await freeze(); await touch("touchStart", [[cx, cy]]); await touch("touchEnd", []); await touch("touchStart", [[cx, cy]]); await touch("touchEnd", []); await thaw();
  await sleep(5000);
  const framed = await cam();
  check(`${tag} double tap frames a`, framed.d < 7 && JSON.stringify(await sel()) === '["a"]', `dist ${framed.d.toFixed(2)} sel ${JSON.stringify(await sel())}`);
  await shot("2-double-tap-frame");

  await p.evaluate(() => __friday.player.apply([{ op: "camera", pos: [0, 0, 9], look: [0, 0, 0] }]));
  await sleep(5000);
  const [lx, ly] = await px("a");
  await tap(lx, ly, 700);
  await sleep(300);
  const menu = await p.evaluate(() => { const m = document.getElementById("ctxmenu"); return m && !m.hidden ? [...m.querySelectorAll("button")].map((b) => [b.textContent, Math.round(b.getBoundingClientRect().height)]) : null; });
  check(`${tag} long press opens menu with >=44px targets`, !!menu && menu.length === 4 && menu.every(([, hh]) => hh >= 44), JSON.stringify(menu));
  await shot("3-long-press-menu");
  const btn = async (label) => p.evaluate((l) => { const r = [...document.querySelectorAll("#ctxmenu button")].find((b) => b.textContent === l).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }, label);
  const [ax2, ay2] = await btn("Ask Friday"); await tap(ax2, ay2);
  await sleep(300);
  const sent = await p.evaluate(() => __sent);
  check(`${tag} Ask Friday sends chat`, sent.some((s) => s.includes('"t":"chat"') && s.includes("Rekni mi neco o objektu a")), sent.at(-1));
  await tap(lx, ly, 700); await sleep(300);
  const [hx, hy] = await btn("Hide"); await tap(hx, hy); await sleep(400);
  check(`${tag} Hide sets node invisible`, await p.evaluate(() => !__friday.player.entries.get("a").node.visible));
  await shot("4-after-hide");
  await p.evaluate(() => __friday.player.apply([{ op: "add", obj: { id: "c", kind: "box", pos: [-2, 0, 0], scale: 1.4 } }]));
  await sleep(1500);
  const [bx2, by2] = await px("c");
  await tap(bx2, by2, 700); await sleep(300);
  const [dx, dy] = await btn("Delete"); await tap(dx, dy); await sleep(400);
  check(`${tag} Delete removes c`, await p.evaluate(() => !__friday.player.entries.has("c")));
  check(`${tag} no page errors`, errs.length === 0, errs.join("|"));
  await ctx.close();
}
await b.close();
console.log(fails.length ? `FAILED: ${fails.length}` : "ALL PASS");
process.exit(fails.length ? 1 : 0);
