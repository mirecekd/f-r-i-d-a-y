// frontend/src/views/image_card.ts
import "./image_card.css";
import { el, safeUrl } from "./dom";
import { exifChips } from "./exif";
import type { Renderer } from "./types";

const KINDS = ["photo", "floorplan", "screenshot", "drawing", "document", "other"];

/** Set by ui/imagedrop.ts: asks the server to put an uploaded image into the 3D scene. */
export const imageCardActions: { toScene: (imageId: string) => void } = { toScene: () => {} };

function section(title: string, ...nodes: HTMLElement[]): HTMLElement {
  const s = el("div", "ic-sec");
  s.append(el("div", "ic-h", title), ...nodes);
  return s;
}

function list(items: string[]): HTMLElement {
  const ul = el("ul", "ic-list");
  for (const t of items) ul.append(el("li", undefined, t));
  return ul;
}

/** data: the `image_card` shape of docs/protocol.md. Every model-provided string goes through textContent. */
export const renderImageCard: Renderer = (body, data) => {
  const root = el("div", "v-imgcard");
  const url = safeUrl(data?.url, true);
  if (url) {
    const img = el("img", "ic-thumb");
    img.src = url;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    root.append(img);
  }
  const kind = KINDS.includes(data?.kind) ? data.kind : "other";
  const badges = el("div", "ic-badges");
  badges.append(el("span", `ic-badge k-${kind}`, kind));
  if (typeof data?.people_count === "number") badges.append(el("span", "ic-badge", `lide: ${data.people_count}`));
  if (data?.scene) badges.append(el("span", "ic-badge", String(data.scene)));
  root.append(badges);
  if (data?.summary) root.append(el("p", "ic-summary", String(data.summary)));

  const objects = (Array.isArray(data?.objects) ? data.objects : []).map(
    (o: any) => `${String(o?.label ?? "?")}${Number(o?.count) > 1 ? ` x${Number(o.count)}` : ""}`);
  if (objects.length) root.append(section("Objekty", list(objects)));
  const texts = (Array.isArray(data?.text_found) ? data.text_found : []).map(String);
  if (texts.length) root.append(section("Nalezeny text", list(texts)));

  const rooms = Array.isArray(data?.rooms) ? data.rooms : [];
  if (rooms.length) {
    const table = el("table", "ic-rooms");
    for (const r of rooms) {
      const tr = el("tr");
      tr.append(el("td", undefined, String(r?.name ?? "?")), el("td", undefined, String(r?.dimensions ?? "")));
      table.append(tr);
    }
    root.append(section("Mistnosti", table));
  }
  if (data?.dimensions_hint) root.append(section("Rozmery", el("div", "ic-text", String(data.dimensions_hint))));
  if (data?.location_hint) root.append(section("Misto", el("div", "ic-text", String(data.location_hint))));
  const chips = exifChips(data?.exif);
  if (chips.length) {
    const row = el("div", "ic-chips");
    row.append(...chips);
    root.append(section("EXIF", row));
  }
  if (data?.notes) root.append(section("Poznamky", el("div", "ic-text", String(data.notes))));

  if (typeof data?.confidence === "number") {
    const pct = Math.round(Math.max(0, Math.min(1, data.confidence)) * 100);
    const fill = el("div", "ic-fill");
    fill.style.width = `${pct}%`;
    const bar = el("div", "ic-bar");
    bar.append(fill);
    root.append(section(`Jistota ${pct} %`, bar));
  }

  const id = typeof data?.url === "string" ? /([0-9a-f]{32})\.[a-z]+$/.exec(data.url)?.[1] : undefined;
  if (id) {
    const btn = el("button", "ic-scene", "Do 3D sceny");
    btn.type = "button";
    btn.onclick = () => {
      imageCardActions.toScene(id);
      btn.disabled = true;
      btn.textContent = "Odeslano do sceny";
      setTimeout(() => { btn.disabled = false; btn.textContent = "Do 3D sceny"; }, 2000);
    };
    root.append(btn);
  }
  body.append(root);
};
