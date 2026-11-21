// frontend/tests/views.mjs - screenshot of every view kind: node tests/views.mjs [url] [out.png]
import { chromium } from "playwright-core";
const url = process.argv[2] ?? "http://127.0.0.1:8682/";
const out = process.argv[3] ?? "/tmp/friday-shots/views.png";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await b.newPage();
await p.setViewportSize({ width: 1800, height: 1000 });
const errs = [];
p.on("pageerror", (e) => errs.push(String(e)));
p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto(url, { waitUntil: "networkidle" });
await new Promise((r) => setTimeout(r, 1500));
await p.evaluate(() => __friday.send({ t: "demo", what: "views" }));
await new Promise((r) => setTimeout(r, 6000));
// tile one panel per slot so all are visible at once
await p.evaluate(() => {
  const ps = [...document.querySelectorAll(".vp")];
  ps.forEach((el, i) => {
    el.style.left = 20 + (i % 4) * 400 + "px";
    el.style.top = 60 + Math.floor(i / 4) * 310 + "px";
    el.style.width = "380px"; el.style.height = "290px";
  });
});
await new Promise((r) => setTimeout(r, 800));
console.log("panels:", await p.$$eval(".vp", (e) => e.map((x) => x.dataset.id)));
console.log("errors:", await p.$$eval(".vp-err", (e) => e.map((x) => x.textContent)));
console.log("script injected:", await p.evaluate(() => !!document.querySelector(".v-md script")));
await p.screenshot({ path: out, timeout: 180000 });
console.log("page errors:", errs);
await b.close();
