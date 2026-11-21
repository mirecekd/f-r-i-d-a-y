// frontend/tests/workshop.mjs - DOM checks of the real Workshop and Deck modules in a small harness page (no Stage, no WebGL, fake socket):
// npx vite build -c tests/workshop_page/vite.config.ts && (cd /tmp/friday-ws-page && python3 -m http.server 8782 --bind 127.0.0.1) &
// node tests/workshop.mjs [baseUrl] [outDir]
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8781/";
const out = process.argv[3] ?? "/tmp/friday-workshop";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--use-gl=disabled"],
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
const cdp = await page.context().newCDPSession(page);
const shot = async (name) => {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(data, "base64"));
  console.log("shot:", name);
};
let bad = 0;
const check = (ok, msg) => { console.log(ok ? "ok:" : "FAIL:", msg); if (!ok) bad = 1; };
const sent = (t) => page.evaluate((t) => window.__sent.filter((m) => m.t === t), t);
const emit = (m) => page.evaluate((m) => window.__ws.emit(m), m);

await page.goto(base, { waitUntil: "load" });
await page.waitForFunction(() => window.__ws !== undefined);
// requestAnimationFrame never fires in this headless Chrome, so Playwright's "stable" wait would hang: act with force.
const click = (sel) => page.click(sel, { force: true });
const fill = (sel, v) => page.fill(sel, v, { force: true });
const clear = () => page.evaluate(() => { window.__sent.length = 0; });
const P1 = { name: "width", label: "Sirka", unit: "cm", value: 5, min: 1, max: 10, step: 0.5 };
const P2 = { name: "legs", label: "Nohy", unit: "", value: 4, min: 3, max: 6, step: 1 };
const ENTER = { t: "workshop", op: "enter", id: "w1", title: "Zidle", origin: [0, 0, 400], camera: { pos: [0, 3, 410], look: [0, 1, 400] }, home: { pos: [0, 1.2, 9], look: [0, 0, 0] }, params: [P1, P2], sources: [{ entity_id: "e1", title: "zidle.png", kind: "image" }], notes: ["Pocet nohou omezen"] };

check((await page.locator(".ws-panel:not([hidden])").count()) === 0, "panel hidden before entering");
// W with nothing selected and no workshop known: create a new one
await page.keyboard.press("w");
check((await sent("workshop_new")).length === 1, "W sends workshop_new");
// deck: Nova dilna button and workshop tile
await page.keyboard.press("d");
await page.waitForSelector(".dk-panel:not([hidden])");
await clear();
await click(".dk-newshop");
check((await sent("workshop_new")).length === 1, "Nova dilna button sends workshop_new");
await emit({ t: "deck", items: [{ id: "w1", type: "workshop", title: "Zidle", created_at: 1, updated_at: 1, pinned: false, tags: [], parent_ids: [] }], total: 1, stats: { by_type: { workshop: 1 } } });
check((await page.locator(".dk-place").textContent()) === "Otevrit dilnu", "workshop tile shows Otevrit dilnu");
await clear();
await click(".dk-place");
check((await sent("workshop_open")).some((m) => m.id === "w1"), "Otevrit dilnu sends workshop_open");
check((await sent("deck_place")).length === 0, "no deck_place for a workshop tile");

// enter
await clear();
await emit(ENTER);
await page.waitForSelector(".ws-panel:not([hidden])");
check(!(await page.locator(".dk-panel:not([hidden])").count()), "Deck closes when a workshop opens");
check((await page.locator(".ws-slider").count()) === 2, "one slider per parameter");
check((await page.locator(".ws-field").first().inputValue()) === "5.0", "numeric field shows the value with step decimals");
check((await page.locator(".ws-title").textContent()) === "Zidle", "title shown");
check((await page.locator(".ws-note").textContent()).includes("omezen"), "server notes shown");
check((await page.locator(".ws-source").count()) === 1, "one source row");
check(await page.locator(".ws-hint").isHidden(), "hint hidden while there is content");
const glides = () => page.evaluate(() => window.__ws.calls.glide);
check(JSON.stringify((await glides()).at(-1)) === JSON.stringify({ pos: [0, 3, 410], look: [0, 1, 400] }), "enter asks the camera to glide to the workshop pose");
await shot("workshop");

// sliders throttle to ~12/s and the last value arrives
await clear();
await page.evaluate(() => {
  const s = document.querySelector('.ws-param[data-name="width"] .ws-slider');
  for (let i = 0; i < 40; i++) { s.value = String(1 + (i % 9)); s.dispatchEvent(new Event("input", { bubbles: true })); }
  s.value = "8"; s.dispatchEvent(new Event("input", { bubbles: true })); s.dispatchEvent(new Event("change", { bubbles: true }));
});
const ps = await sent("workshop_param");
check(ps.length >= 1 && ps.length <= 3, `burst of 41 slider events sends only ${ps.length}`);
check(ps.at(-1).value === 8 && ps.at(-1).name === "width" && ps.at(-1).id === "w1", "the final value is sent on release");
await clear();
await fill('.ws-param[data-name="legs"] .ws-field', "99");
await page.press('.ws-param[data-name="legs"] .ws-field', "Tab");
check((await sent("workshop_param")).some((m) => m.name === "legs" && m.value === 6), "typed value is clamped and sent");
// a params update changes values in place without rebuilding the sliders
await emit({ t: "workshop", op: "params", id: "w1", params: [{ ...P1, value: 2 }, P2], notes: [] });
check((await page.locator(".ws-param[data-name=width] .ws-field").inputValue()) === "2.0", "params op updates the field");
check((await page.locator(".ws-note").count()) === 0, "notes cleared");

// undo / redo / ask / source removal
await clear();
await click(".ws-undo"); await click(".ws-redo");
check((await sent("workshop_undo")).some((m) => m.id === "w1") && (await sent("workshop_redo")).some((m) => m.id === "w1"), "undo and redo messages");
await fill(".ws-ask-input", "Udelej ji vyssi");
await page.press(".ws-ask-input", "Enter");
check((await sent("chat")).some((m) => m.text === "Udelej ji vyssi"), "Zeptat se sends chat");
await click(".ws-src-x");
check((await sent("chat")).some((m) => m.text === "Odeber zdroj zidle.png z dilny"), "x on a source asks the model to remove it");
check(await page.evaluate(() => document.body.classList.contains("ws-open")), "body marked ws-open (hides the desk-only Zavrit of the entity bar)");
await click(".ws-src-pick");
check(await page.evaluate(() => window.__ws.calls.focused[0] === "e1"), "clicking a source focuses its entity");

// W typed in the ask field does not toggle; W elsewhere leaves
await clear();
await page.focus(".ws-ask-input"); await page.keyboard.type("w");
check((await sent("workshop_leave")).length === 0, "typing w in a field does not leave");
await page.evaluate(() => document.activeElement.blur());
await page.keyboard.press("w");
check((await sent("workshop_leave")).length === 1, "W inside the workshop sends workshop_leave");
await clear();
await page.keyboard.press("Escape");
check((await sent("workshop_leave")).length === 1, "Esc inside the workshop sends workshop_leave");
await clear();
await page.keyboard.press("d");
await page.keyboard.press("Escape");
check((await sent("workshop_leave")).length === 0, "Esc with the Deck open only closes the Deck");

// drop a deck tile on the canvas while inside the workshop
await page.evaluate(() => document.activeElement.blur());
await page.keyboard.press("d");
await page.fill(".dk-search", ""); // the D key leaves a literal "d" in the freshly focused search field
await emit({ t: "deck", items: [{ id: "it9", type: "image", title: "mapa.png", created_at: 1, updated_at: 1, pinned: false, tags: [], parent_ids: [] }], total: 1, stats: { by_type: { image: 1 } } });
await clear();
const box = await page.locator(".dk-thumb").boundingBox();
await page.mouse.move(box.x + 10, box.y + 10); await page.mouse.down(); await page.mouse.move(box.x + 30, box.y + 30);
await page.mouse.move(5, 790); await page.mouse.up();
check((await sent("chat")).some((m) => m.text === "Pridej do dilny mapa.png (it9)"), "tile dropped on the canvas asks the model to add it");
check((await sent("deck_place")).length === 0, "no deck_place while a workshop is open");
await page.keyboard.press("Escape");

// snapshot request: the harness renders a 2D canvas, so the encode loop and the reply are exercised for real
await clear();
await emit({ t: "workshop_snapshot_request", req: "r1", id: "w1", width: 640 });
await page.waitForFunction(() => window.__sent.some((m) => m.t === "workshop_snapshot"));
const snap = (await sent("workshop_snapshot"))[0];
check(snap.req === "r1" && snap.id === "w1" && typeof snap.jpeg_b64 === "string" && snap.jpeg_b64.length > 100 && snap.jpeg_b64.length * 0.75 <= 800000, `snapshot answered with a jpeg (${Math.round(snap.jpeg_b64?.length * 0.75 / 1000)} kB)`);
await emit({ t: "workshop_snapshot_request", req: "r2", id: "w1" });
await page.waitForFunction(() => window.__sent.some((m) => m.t === "workshop_snapshot" && m.req === "r2"));
check(true, "snapshot without width answered");

// leave: panel closes, hint returns on an empty workshop
await emit({ t: "workshop", op: "leave", id: "w1", camera: { pos: [0, 1.2, 9], look: [0, 0, 0] } });
check((await page.locator(".ws-panel:not([hidden])").count()) === 0, "leave closes the panel");
check(JSON.stringify((await glides()).at(-1)) === JSON.stringify({ pos: [0, 1.2, 9], look: [0, 0, 0] }), "leave asks the camera to glide back");
await emit({ t: "workshop", op: "enter", id: "w2", title: "Prazdna", camera: { pos: [0, 3, 810], look: [0, 1, 800] }, params: [], sources: [], notes: [] });
check((await page.locator(".ws-hint").textContent()) === "Hod sem obrazek nebo soubor z Decku a rekni, co mam postavit.", "hint on an empty workshop");
await clear();
await page.keyboard.press("w"); // leave
await emit({ t: "workshop", op: "leave", id: "w2" });
await page.keyboard.press("w");
check((await sent("workshop_open")).some((m) => m.id === "w2"), "W after leaving reopens the last workshop");

const real = errs;
check(real.length === 0, `no page errors ${real.join("|")}`);
await browser.close();
process.exitCode = bad;
