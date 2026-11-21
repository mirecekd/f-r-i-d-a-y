// frontend/tests/models.mjs - role-filtered model dropdowns: node tests/models.mjs [baseUrl] [outDir]
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8701/";
const out = process.argv[3] ?? "/tmp/friday-m1";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 810 } });
page.setDefaultTimeout(30000);
const fail = (m) => { console.log("FAIL:", m); process.exitCode = 1; };

const live = (id, label) => ({ id, provider: "gemini", label, group: "google live", roles: ["chat"] });
const catalog = [
  live("gemini-3.8-live", "Gemini 3.8 Live"),
  live("gemini-3.8-live-extended-thinking", "Gemini 3.8 Live Extended Thinking (async only, no scheduling)"),
  live("gemini-3.1-flash-live-preview", "Gemini 3.1 Flash Live Preview (legacy: no async tools)"),
  { id: "gemini-3.5-flash", provider: "gemini", label: "Gemini 3.5 Flash", group: "google", roles: ["agent"], caps: { tools: true, vision: true, reasoning: true } },
  { id: "eu.anthropic.claude-opus-5", provider: "litellm", label: "claude-opus-5 (eu)", group: "anthropic", roles: ["agent"], caps: { tools: true, vision: true, reasoning: true } },
  { id: "eu.mistral.pixtral", provider: "litellm", label: "pixtral (eu)", group: "mistral", roles: ["agent"], caps: { tools: true } },
];

await page.goto(base + "?particles=2000&px=1&bloom=0", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await page.evaluate((cat) => window.__friday.emit({
  t: "models", catalog: cat, pinned: { agent_model: "gemini-3.5-flash", chat_model: "gemini-3.8-live" },
}), catalog);

const ids = async (idx) => {
  const wrap = page.locator(".mp").nth(idx);
  await wrap.locator(".mp-btn").click();
  const list = await wrap.locator(".mp-opt").evaluateAll((os) => os.map((o) => o.dataset.id));
  const caps = await wrap.locator(".mp-cap").count();
  return { wrap, list, caps };
};
const agent = await ids(0);
await page.screenshot({ path: `${out}/agent.png` });
await page.keyboard.press("Escape");
const chat = await ids(1);
await page.screenshot({ path: `${out}/chat.png` });
console.log("agent:", agent.list.join(", "), "badges", agent.caps);
console.log("chat:", chat.list.join(", "));
if (chat.list.length !== 3 || chat.list.some((i) => !i.includes("live"))) fail("chat dropdown must hold only live models");
if (agent.list.length !== 3 || agent.list.some((i) => i.includes("live"))) fail("agent dropdown must hold no live models");
if (agent.caps < 4) fail("capability badges missing");
const tip = await agent.wrap.locator(".mp-opt").first().getAttribute("title");
if (!tip?.includes("function calling")) fail("tooltip missing capabilities");
await browser.close();
console.log(process.exitCode ? "FAILED" : "OK");
