// frontend/tests/voicepick.mjs - voice and language dropdowns: node tests/voicepick.mjs [baseUrl] [outDir]
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8703/";
const out = process.argv[3] ?? "/tmp/friday-v1";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.setDefaultTimeout(20000);
let failed = false;
const check = (name, ok, info = "") => { console.log(ok ? "PASS" : "FAIL", name, info); if (!ok) failed = true; };

const voices = [
  ["Kore", "female", "firm"], ["Leda", "female", "youthful"], ["Aoede", "female", "breezy"], ["Zephyr", "female", "bright"],
  ["Puck", "male", "upbeat"], ["Charon", "male", "informative"], ["Orus", "male", "firm"],
].map(([id, gender, style]) => ({ id, label: id, gender, style }));
const languages = [["cs-CZ", "Cestina"], ["en-US", "English"], ["sk-SK", "Slovencina"], ["de-DE", "Deutsch"], ["pl-PL", "Polski"]]
  .map(([code, label]) => ({ code, label }));

await page.goto(base + "?offline&noorb&lowfx", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await page.evaluate(([v, l]) => {
  window.__sent = [];
  const net = window.__friday;
  net.emit({ t: "models", catalog: [], pinned: { agent_model: "", chat_model: "gemini-3.8-live" }, voice: "Kore", voices: v, language: "cs-CZ", languages: l });
}, [voices, languages]);
await page.click("#settingsbtn");
await page.waitForSelector("#settings.open");
const sec = page.locator("#settings section", { hasText: "Hlas a jazyk" });
check("section exists", (await sec.count()) === 1);
const btns = sec.locator(".mp-btn");
check("two dropdowns", (await btns.count()) === 2);
check("voice shows current", (await btns.nth(0).innerText()).includes("Kore"), (await btns.nth(0).innerText()).replace(/\n/g, " "));
check("language shows current", (await btns.nth(1).innerText()).includes("Cestina"));
check("touch height >= 44", (await btns.nth(0).boundingBox()).height >= 44);
await btns.nth(0).click();
check("voice options", (await sec.locator(".mp").nth(0).locator(".mp-opt").count()) === voices.length);
await page.screenshot({ path: `${out}/voicepick-voice.png` });
await btns.nth(0).click();
await btns.nth(1).click();
await page.screenshot({ path: `${out}/voicepick-lang.png` });
await browser.close();
process.exit(failed ? 1 : 0);
