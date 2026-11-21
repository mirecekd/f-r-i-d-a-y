// frontend/tests/voice_fake_mic.mjs - headless voice smoke test with Chrome's fake microphone:
// node tests/voice_fake_mic.mjs [url]. Clicks the mic button, sends one typed turn, logs WS frames (no audio bytes).
import { chromium } from "playwright-core";
const url = process.argv[2] ?? "http://127.0.0.1:8684/";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true,
  args: ["--no-sandbox", "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await b.newContext({ permissions: ["microphone"] });
const p = await ctx.newPage();
const t0 = Date.now();
const log = (s) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${s}`);
let up = 0, down = 0;
p.on("pageerror", (e) => log("PAGEERROR " + e));
p.on("websocket", (ws) => {
  ws.on("framesent", (f) => { if (typeof f.payload === "string") log(">> " + f.payload); else up++; });
  ws.on("framereceived", (f) => {
    if (typeof f.payload === "string") { const m = JSON.parse(f.payload); if (!(m.t === "transcript" && !m.final)) log("<< " + f.payload.slice(0, 160)); }
    else down++;
  });
});
await p.goto(url, { waitUntil: "networkidle" });
await p.click("#mic");
await new Promise((r) => setTimeout(r, 2500));
log("mic button class: " + (await p.$eval("#mic", (e) => e.className)));
await p.fill("#input", "Ahoj Friday, rekni jednu vetu o pocasi.");
await p.keyboard.press("Enter");
await new Promise((r) => setTimeout(r, 10000));
await p.click("#mic");
await new Promise((r) => setTimeout(r, 800));
log(`binary mic frames sent: ${up}; binary audio frames received: ${down}`);
log("chat msgs: " + JSON.stringify(await p.$$eval(".msg", (e) => e.map((x) => x.className + ": " + x.textContent))));
await b.close();
