// frontend/tests/memhits_dom.mjs - DOM test of the hits panel without WebGL: node tests/memhits_dom.mjs
// Builds tests/memhits_page (no WebGL, no backend) with vite and drives the hits panel: node tests/memhits_dom.mjs
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { chromium } from "playwright-core";
const out = "/tmp/memhits-dist";
execFileSync("npx", ["vite", "build", "tests/memhits_page", "--outDir", out, "--emptyOutDir", "--base", "./"], { stdio: "ignore" });
const types = { html: "text/html", js: "text/javascript", css: "text/css" };
const srv = createServer((req, res) => { // module scripts do not load from file://
  const path = new URL(req.url, "http://x").pathname.replace(/^\/$/, "/index.html");
  try { res.setHeader("content-type", types[path.split(".").pop()] ?? "application/octet-stream"); res.end(readFileSync(out + path)); }
  catch { res.statusCode = 404; res.end(); }
}).listen(0, "127.0.0.1");
await new Promise((r) => srv.once("listening", r));
const url = `http://127.0.0.1:${srv.address().port}/index.html?q=` + encodeURIComponent("nginx <b>x</b>");
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox"] });
const p = await b.newPage();
await p.setViewportSize({ width: 900, height: 700 });
const errs = [];
p.on("pageerror", (e) => errs.push(String(e)));
await p.goto(url, { waitUntil: "load" });
await p.waitForFunction(() => window.panel, null, { timeout: 15000 });
assert.equal(await p.locator(".mg-hit").count(), 12);
assert.match(await p.locator(".mg-qchip").innerText(), /nginx <b>x<\/b>\s+12 vysledku/); // textContent only
assert.equal(await p.locator(".mg-hits-sum b, .mg-qchip b").count(), 0);
const small = await p.$$eval(".mg-hit, .mg-hits-toggle, .mg-cancel", (e) => e.filter((x) => x.getBoundingClientRect().height < 43.5).length);
assert.equal(small, 0, "touch targets >= 44 px");
await p.locator(".mg-hit").first().focus();
await p.keyboard.press("ArrowDown");
await p.keyboard.press("Enter");
assert.equal(await p.evaluate(() => window.picked.length), 1);
await p.locator(".mg-hit").nth(4).click();
assert.equal(await p.evaluate(() => window.picked.length), 2);
await p.locator(".mg-cancel").click();
assert.equal(await p.evaluate(() => window.cancelled), 1);
await p.locator(".mg-hits-toggle").click();
assert.equal(await p.locator(".mg-hit-list").isVisible(), false);
await p.locator(".mg-hits-toggle").click();
assert.equal(await p.locator(".mg-hit-list").isVisible(), true);
await p.screenshot({ path: "/tmp/friday-shots/memhits_dom.png" });
assert.deepEqual(errs.filter((e) => !/webgl|WebGL/i.test(e)), []);
console.log("memhits DOM ok; rows:", 12, "page errors:", errs.length);
await b.close();
srv.close();
