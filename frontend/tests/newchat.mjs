// frontend/tests/newchat.mjs - headless check of the new-conversation button: node tests/newchat.mjs [baseUrl] [outDir]
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8772/";
const out = process.argv[3] ?? "/tmp/friday-n2";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--disable-gpu-vsync", "--disable-renderer-backgrounding"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 810 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(30000);
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
const sent = [];
await page.routeWebSocket(/\/ws$/, (ws) => {
  const server = ws.connectToServer();
  ws.onMessage((m) => { try { sent.push(JSON.parse(String(m))); } catch { /* binary */ } server.send(m); });
});
// This sandbox may have no WebGL at all: give three.js a permissive fake context so the DOM code under test still runs.
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


const cdp = await page.context().newCDPSession(page);
const shot = async (name) => {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(data, "base64"));
  console.log("shot:", name);
};
let bad = 0;
const check = (ok, msg) => { console.log(ok ? "ok:" : "FAIL:", msg); if (!ok) bad = 1; };
const count = () => page.evaluate(() => document.querySelectorAll("#log .msg:not(.system)").length);
const resets = () => sent.filter((m) => m.t === "new_conversation").length;

await page.goto(base + "?noorb&particles=500&px=1&bloom=0", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await page.evaluate(() => localStorage.removeItem("friday.chat"));
await page.click("#chatbtn");
await page.waitForTimeout(600);
const box = await page.locator(".nc-btn").boundingBox();
check(box && box.width >= 44 && box.height >= 44, `button is a 44 px target (${box?.width}x${box?.height})`);
check((await page.getAttribute(".nc-btn", "aria-label")) === "Nova konverzace", "aria-label");

// 2 messages: no confirmation
await page.evaluate(() => { window.__friday.chat("user", "ahoj"); window.__friday.chat("assistant", "Cau"); });
await page.click(".nc-btn");
await page.waitForTimeout(300);
check(resets() === 1, "2 messages: sent immediately");
check((await count()) === 0 && (await page.locator("#log .msg.system").count()) === 1, "log emptied, system line shown");

// 5 messages: confirmation
await page.evaluate(() => { for (let i = 0; i < 5; i++) window.__friday.chat(i % 2 ? "assistant" : "user", `zprava ${i}`); window.__friday.tool("t1", "show_view", "ok", 1200); });
await page.waitForTimeout(500);
check(await page.evaluate(() => localStorage.getItem("friday.chat") !== null), "history saved");
await page.click(".nc-btn");
check(await page.locator(".nc-ask").isVisible(), "confirmation shown for 5 messages");
check(resets() === 1, "not sent before confirming");
await shot("confirm");
await page.waitForTimeout(3300);
check(!(await page.locator(".nc-ask").isVisible()) && (await page.locator(".nc-btn").isVisible()), "confirmation expires after 3 s");
check((await count()) === 5 && resets() === 1, "expired: nothing cleared");
await page.click(".nc-btn");
await page.click(".nc-no");
check((await count()) === 5 && resets() === 1, "Ne keeps the chat");
await page.keyboard.press("Control+Shift+N");
check(await page.locator(".nc-ask").isVisible(), "Ctrl+Shift+N asks too");
await page.click(".nc-yes");
await page.waitForTimeout(700);
check(resets() === 2, "Ano sends new_conversation");
check((await count()) === 0 && (await page.locator("#log .chip").count()) === 0, "chat and chips empty");
const stored = await page.evaluate(() => localStorage.getItem("friday.chat"));
check(stored === null, "localStorage friday.chat cleared");
check(sent.filter((m) => m.t === "new_conversation").every((m) => m.clear_scene === undefined), "no clear_scene by default");
await shot("after");
const real = errs.filter((e) => !/reading .length.|WebGL/.test(e));
check(real.length === 0, `no page errors besides the stubbed WebGL ones ${real.join("|")}`);
await browser.close();
process.exitCode = bad;
