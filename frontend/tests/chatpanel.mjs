// frontend/tests/chatpanel.mjs - headless check of mini orb and chat panel: node tests/chatpanel.mjs [baseUrl] [outDir]
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8701/";
const out = process.argv[3] ?? "/tmp/friday-g1";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist", "--disable-gpu-vsync"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 810 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(60000);
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
const cdp = await page.context().newCDPSession(page);
const shot = async (name) => {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(data, "base64"));
  console.log("shot:", name);
};
const fail = (m) => { console.log("FAIL:", m); process.exitCode = 1; };
const wait = (ms) => page.waitForTimeout(ms);

await page.goto(base + "?particles=3000&px=1&bloom=0", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await page.evaluate(() => localStorage.removeItem("friday.chat"));
await wait(1500);
for (const s of ["idle", "listening", "speaking"]) {
  await page.evaluate((s) => { window.__friday.state(s); window.__friday.level(s === "speaking" ? 0.5 : 0); }, s);
  await wait(1800);
  await shot(`closed-${s}`);
}
const open = () => page.evaluate(() => document.getElementById("chat").classList.contains("open"));
if (await open()) fail("chat open by default");
const btn = await page.locator("#chatbtn").boundingBox();
if (btn.width < 44 || btn.height < 44) fail("button too small");

// A message arriving while closed: badge + caption (served by the backend echo is not needed; inject through the app).
await page.evaluate(() => window.__friday.chat("assistant", "Ahoj. Jsem Friday a mam pro tebe odpoved."));
await page.evaluate(() => window.__friday.chat("assistant", "Druha zprava prisla taky."));
await wait(500);
await shot("closed-badge-caption");
if ((await page.textContent("#chatbadge")) !== "2") fail("badge not 2");
await page.click("#chatbtn");
await wait(600);
if (!(await open())) fail("chat did not open");
if (!(await page.evaluate(() => document.activeElement?.id === "input"))) fail("input not focused");
if (!(await page.locator("#chatbadge").isHidden())) fail("badge not cleared");
await page.evaluate(() => window.__friday.tool("t1", "show_chart", "ok", 1200));
await shot("open");
await page.keyboard.press("Escape");
await wait(600);
if (await open()) fail("Esc did not close");
await wait(200);
await page.evaluate(() => window.__friday.chat("assistant", "Posledni veta zmizi."));
await wait(300);
const capShown = await page.evaluate(() => document.getElementById("caption").classList.contains("show"));
if (!capShown) fail("caption not shown");
await wait(7500);
if (await page.evaluate(() => document.getElementById("caption").classList.contains("show"))) fail("caption not faded");
await wait(500);
await page.reload({ waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("friday.chat") ?? "[]").length);
const restored = await page.evaluate(() => document.querySelectorAll("#log .msg, #log .chip").length);
console.log("stored", stored, "restored", restored);
if (stored < 4 || restored !== stored) fail("history not restored");
if (errs.length) fail(errs.join("; "));
await browser.close();
console.log(process.exitCode ? "FAILED" : "OK");
