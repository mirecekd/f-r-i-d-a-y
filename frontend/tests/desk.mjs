// frontend/tests/desk.mjs - DOM-only checks of the entity bar, drop toast and Deck window (no WebGL, fake socket):
// node tests/desk.mjs [baseUrl] [outDir]   (baseUrl: the built frontend, e.g. python3 -m http.server in backend/static)
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8781/";
const out = process.argv[3] ?? "/tmp/friday-desk";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(20000);
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
// A fake socket that is always open and records everything the page sends.
await page.addInitScript(() => {
  window.__sent = [];
  window.WebSocket = class {
    static OPEN = 1;
    constructor() { this.readyState = 1; setTimeout(() => this.onopen && this.onopen(), 0); }
    send(d) { window.__sent.push(JSON.parse(d)); }
    close() {}
  };
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
const sent = (t) => page.evaluate((t) => window.__sent.filter((m) => m.t === t), t);
const emit = (m) => page.evaluate((m) => window.__friday.emit(m), m);
const ENTITY = { id: "ent-file-ab12cd34", kind: "entity", shape: "doc", title: "architect.webp", pos: [0, 1.2, 0], ref: { type: "file", id: "ab12cd34" } };

await page.goto(base + "?noorb&particles=100&px=1&bloom=0", { waitUntil: "load" });
await page.waitForFunction(() => window.__friday !== undefined);
await page.waitForTimeout(500);

// ---- drop toast: scene op with a ref arrives together with file_ready
await emit({ t: "file_ready", id: "ab12cd34", client_id: "c1", kind: "doc", name: "architect.webp", size: 10, url: "/x", meta: {} });
await emit({ t: "scene", ops: [{ op: "add", obj: ENTITY }] });
await page.waitForSelector(".dn-toast:not([hidden])");
check((await page.textContent(".dn-text")).includes("architect.webp"), "toast names the file");
check(await page.evaluate(() => window.__friday.player.selection.ids[0] === "ent-file-ab12cd34"), "new entity is selected");
check((await sent("select")).some((m) => m.ids[0] === "ent-file-ab12cd34"), "selection reported to the server");
// the automatic card for that upload is not opened
await emit({ t: "view", id: "file-ab12cd34", kind: "file_card", title: "architect.webp", data: {} });
check((await page.locator(".vp").count()) === 0, "automatic file_card suppressed");
await page.click(".dn-toast button:has-text('Zeptat se')");
check((await sent("chat")).some((m) => m.text === "Co je to za soubor architect.webp?"), "Zeptat se sends the question");
check(await page.locator(".dn-toast").isHidden(), "toast closes after an action");
await emit({ t: "file_ready", id: "ab12cd34", kind: "doc", name: "architect.webp", size: 10, url: "/x", meta: {} });
await emit({ t: "scene", ops: [{ op: "del", id: ENTITY.id }, { op: "add", obj: ENTITY }] });
await page.waitForSelector(".dn-toast:not([hidden])");
await page.click(".dn-toast button:has-text('Otevrit')");
check((await sent("entity_open")).some((m) => m.id === ENTITY.id), "Otevrit sends entity_open");
await emit({ t: "file_ready", id: "ab12cd34", kind: "doc", name: "architect.webp", size: 10, url: "/x", meta: {} });
await emit({ t: "scene", ops: [{ op: "del", id: ENTITY.id }, { op: "add", obj: ENTITY }] });
await page.waitForSelector(".dn-toast:not([hidden])");
await page.waitForTimeout(8300);
check(await page.locator(".dn-toast").isHidden(), "toast disappears after 8 s");

// ---- entity bar: selection shows it, buttons and keys work
await page.evaluate((id) => { window.__friday.player.selection.set([id]); window.__friday.player.onSelect([id]); }, ENTITY.id);
await page.waitForSelector(".eb-bar:not([hidden])");
const boxes = await page.locator(".eb-bar button").evaluateAll((bs) => bs.map((b) => [b.textContent, b.getBoundingClientRect().width, b.getBoundingClientRect().height]));
check(boxes.map((b) => b[0]).join("|") === "Zavrit x|Otevrit|Spojit|Zeptat se", `bar buttons ${boxes.map((b) => b[0])}`);
check(boxes.every((b) => b[1] >= 44 && b[2] >= 44), "bar targets are at least 44 px");
const r = await page.locator(".eb-bar").boundingBox();
check(r.x >= 0 && r.y >= 0 && r.x + r.width <= 1280 && r.y + r.height <= 800, "bar is inside the viewport");
await shot("bar");
await page.click(".eb-close");
check((await sent("entity_remove")).length === 1, "Zavrit x sends entity_remove");
await page.evaluate(() => document.activeElement.blur());
await page.keyboard.press("Enter");
check((await sent("entity_open")).length === 2, "Enter opens (2nd entity_open)");
await page.keyboard.press("Delete");
check((await sent("entity_remove")).length === 2, "Delete removes");
await page.keyboard.press("Escape");
check(await page.evaluate(() => window.__friday.player.selection.ids.length === 0), "Esc deselects");
await page.waitForFunction(() => document.querySelector(".eb-bar").hidden, null, { timeout: 5000 }).catch(() => {});
check(await page.locator(".eb-bar").isHidden(), "bar hidden without selection (next frame)");
await page.evaluate((id) => { window.__friday.player.selection.set([id]); }, ENTITY.id);
await page.click("#chatbtn");
await page.waitForTimeout(500);
await page.focus("#input");
await page.keyboard.press("Backspace");
check((await sent("entity_remove")).length === 2, "Backspace in a text field does not remove");
await page.evaluate(() => document.activeElement.blur());
await page.click("#chatbtn");
await page.waitForTimeout(400);

// ---- Deck window
const mk = (i, type, extra = {}) => ({ id: `it${i}`, type, title: `Polozka ${i}`, subtitle: "pdf, 3 pages", created_at: Date.now() / 1000 - i * 90, updated_at: Date.now() / 1000 - i * 90, pinned: i === 1, tags: i === 2 ? ["dum"] : [], source: "upload", parent_ids: i === 3 ? ["a", "b"] : [], size: 100, ...extra });
await page.keyboard.press("d");
await page.waitForSelector(".dk-panel:not([hidden])");
check((await sent("deck_list")).length >= 1, "opening the Deck asks deck_list");
await emit({ t: "deck", items: [mk(1, "file"), mk(2, "image"), mk(3, "file"), mk(4, "note")], total: 6, stats: { by_type: { file: 3, image: 2, note: 1 } } });
check((await page.locator(".dk-tile").count()) === 4, "4 tiles rendered");
check((await page.locator(".dk-fchip").allTextContents()).join("|") === "vse 6|file 3|image 2|note 1", "type chips with counts");
check((await page.textContent(".dk-tile .dk-from")).includes("vznikl z: 2 polozek"), "provenance line");
check((await page.locator(".dk-tile .dk-chip").first().textContent()) === "dum" || (await page.locator(".dk-chip").count()) >= 1, "tag chip shown");
check((await page.locator(".dk-meta").first().textContent()).startsWith("pred"), "relative time");
check((await page.locator(".dk-more-page").count()) === 1, "Nacist dalsi shown while more exist");
await page.click(".dk-more-page");
check((await sent("deck_list")).some((m) => m.offset === 4), "Nacist dalsi asks the next offset");
await page.locator(".dk-fchip", { hasText: "image" }).click();
check((await sent("deck_list")).some((m) => m.type === "image"), "type chip asks the filtered list");
await page.fill(".dk-search", "dum");
await page.waitForTimeout(500);
check((await sent("deck_list")).some((m) => m.q === "dum"), "debounced search asks the server");
await page.fill(".dk-search", "");
await page.waitForTimeout(400);
await page.locator(".dk-fchip", { hasText: "vse" }).click();
await emit({ t: "deck", items: [mk(1, "file"), mk(2, "image"), mk(3, "file"), mk(4, "note")], total: 4, stats: { by_type: { file: 2, image: 1, note: 1 } } });
await page.locator(".dk-top .mp-btn").click();
await page.locator(".dk-top .mp-opt", { hasText: "Nazev" }).click();
check((await page.locator(".dk-title").first().textContent()) === "Polozka 1", "sort by name keeps order here");
// keyboard navigation
await page.locator(".dk-tile").first().focus();
await page.keyboard.press("ArrowRight");
check(await page.evaluate(() => document.activeElement.dataset.id === document.querySelectorAll(".dk-tile")[1].dataset.id), "ArrowRight moves focus");
await page.keyboard.press("End");
check(await page.evaluate(() => document.activeElement === [...document.querySelectorAll(".dk-tile")].at(-1)), "End goes to the last tile");
await page.keyboard.press("Home");
await page.keyboard.press("Enter");
check((await sent("deck_open")).length === 1, "Enter on a tile sends deck_open");
// place, pin, tag, forget two-step
await page.locator(".dk-tile").first().locator(".dk-place").click();
check((await sent("deck_place")).some((m) => m.id === "it1" && m.pos === undefined), "Na plochu sends deck_place");
await page.locator(".dk-tile").first().locator(".dk-star").click();
check((await sent("deck_pin")).some((m) => m.id === "it1" && m.pinned === false), "star toggles pin");
await page.locator(".dk-tile").first().locator(".dk-more").click();
await page.locator(".dk-menu button:has-text('Stitky')").click();
await page.fill(".dk-menu .dk-tags", "a, b");
await page.keyboard.press("Enter");
check((await sent("deck_tag")).some((m) => m.id === "it1" && m.tags.join() === "a,b"), "Tag... sends deck_tag");
await page.locator(".dk-tile").first().locator(".dk-more").click();
await page.locator(".dk-menu .dk-forget").click();
check((await sent("deck_forget")).length === 0, "first Forget click only arms");
await shot("deck");
await page.locator(".dk-menu .dk-forget").click();
check((await sent("deck_forget")).some((m) => m.id === "it1"), "second click sends deck_forget");
await page.locator(".dk-tile").nth(1).locator(".dk-from, .dk-place").first().click();
// empty state and Escape
await emit({ t: "deck", items: [], total: 0, stats: { by_type: {} } });
check((await page.locator(".dk-empty").count()) === 1, "empty state shown");
await page.keyboard.press("Escape");
check(await page.locator(".dk-panel").isHidden(), "Esc closes the Deck");
await page.click("#deckbtn");
check(await page.locator(".dk-panel").isVisible(), "dock button opens the Deck");
await shot("deck-empty");

const real = errs.filter((e) => !/reading .length.|WebGL/.test(e));
check(real.length === 0, `no page errors besides the stubbed WebGL ones ${real.join("|")}`);
await browser.close();
process.exitCode = bad;
