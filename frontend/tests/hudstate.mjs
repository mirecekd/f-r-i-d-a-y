// frontend/tests/hudstate.mjs - DOM check of the task-state line (no WebGL: a stub context is injected):
//   node tests/hudstate.mjs [outDir]   (serves ../backend/static itself, run `npm run build` first)
import { createServer } from "node:http";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { extname, join } from "node:path";
import { chromium } from "playwright-core";

const out = process.argv[2] ?? "/tmp/friday-hud";
mkdirSync(out, { recursive: true });
const root = new URL("../../backend/static/", import.meta.url).pathname;
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".woff": "font/woff" };
const server = createServer((req, res) => {
  const path = new URL(req.url, "http://x").pathname;
  try {
    const file = path === "/" ? "/index.html" : path;
    const body = readFileSync(join(root, file));
    res.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" }).end(body);
  } catch { res.writeHead(404).end(); }
}).listen(0, "127.0.0.1");
await new Promise((r) => server.once("listening", r));
const base = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.setDefaultTimeout(20000);
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
await page.addInitScript(() => {
  const real = HTMLCanvasElement.prototype.getContext;
  const fake = () => new Proxy(function () {}, {
    get: (_t, k) => {
      if (k === "canvas") return document.createElement("canvas");
      if (k === "getContextAttributes") return () => ({ alpha: true, antialias: false });
      if (k === "getShaderPrecisionFormat") return () => ({ rangeMin: 127, rangeMax: 127, precision: 23 });
      if (k === "getParameter") return (p) => ([7936, 7937, 7938, 35724].includes(p) ? "WebGL 2.0 stub" : 16);
      if (k === "getExtension") return () => null;
      if (k === "getSupportedExtensions") return () => [];
      if (k === "getProgramParameter" || k === "getShaderParameter") return () => true;
      if (k === "getProgramInfoLog" || k === "getShaderInfoLog") return () => "";
      if (typeof k === "symbol") return undefined;
      const text = { VERSION: 7938, SHADING_LANGUAGE_VERSION: 35724, VENDOR: 7936, RENDERER: 7937 };
      if (k in text) return text[k];
      return /^[A-Z_0-9]+$/.test(k) ? 1 : () => ({});
    },
  });
  HTMLCanvasElement.prototype.getContext = function (type, ...a) {
    const ctx = real.call(this, type, ...a);
    return ctx || (/webgl/.test(String(type)) ? fake() : ctx);
  };
});

let bad = 0;
const check = (ok, msg) => { console.log(ok ? "ok:" : "FAIL:", msg); if (!ok) bad = 1; };
const state = () => page.evaluate(() => { const e = document.getElementById("taskstate"); return { text: e.textContent, show: e.classList.contains("show") }; });
const tool = (id, name, status) => page.evaluate((m) => window.__friday.emit({ t: "tool", ...m }), { id, name, status });

await page.goto(base + "?noorb&offline&particles=500&px=1&bloom=0", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
check((await state()).show === false, "hidden at rest");
await tool("1", "web_search", "start");
check(JSON.stringify(await state()) === JSON.stringify({ text: "Hledam", show: true }), "web_search shows Hledam");
await tool("1", "web_search", "ok");
await page.waitForTimeout(700);
check((await state()).show === true, "still shown 700 ms after the end (fade starts after 1.5 s)");
await page.waitForTimeout(1200);
check((await state()).show === false, "hidden about 1.9 s after the end");
await tool("2", "scene_apply", "start");
await tool("2", "scene_apply", "ok");
await tool("3", "recall", "start");
await tool("3", "recall", "ok");
check((await state()).text === "Stavim", "burst: first label is held, no flicker");
await page.waitForTimeout(800);
check((await state()).text === "Vzpominam", "burst: the newest label follows after the minimum display time");
await page.setViewportSize({ width: 320, height: 640 });
await tool("4", "a__b", "start");
await page.waitForTimeout(150);
const r = await page.evaluate(() => {
  const box = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
  return { line: box("#taskstate"), dock: box("#dock"), w: innerWidth };
});
const overlap = r.line.l < r.dock.r && r.line.r > r.dock.l && r.line.t < r.dock.b && r.line.b > r.dock.t;
check(r.line.r <= r.w && r.line.l >= 0, `fits 320 px (${Math.round(r.line.l)}..${Math.round(r.line.r)})`);
check(!overlap, "does not overlap the dock at 320 px");
const { data } = await (await page.context().newCDPSession(page)).send("Page.captureScreenshot", { format: "png" });
writeFileSync(`${out}/hud-320.png`, Buffer.from(data, "base64"));
// The WebGL stub makes three.js throw once while it builds the scene; that error is known and not ours.
const ours = errs.filter((e) => !/Cannot read properties of undefined \(reading 'length'\)/.test(e));
check(ours.length === 0, "no page errors besides the known WebGL-stub one" + (ours.length ? `: ${ours[0]}` : ""));
await browser.close();
server.close();
process.exit(bad);
