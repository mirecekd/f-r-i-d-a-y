// frontend/src/ui/deck_tile.ts
import { glyphForEntity } from "../scene/entity_logic";
import { glyphCanvas } from "../core/glyphs";
import { el, safeUrl } from "../views/dom";
import { parseTags, provenance, relativeTime, shapeOfType, type DeckItem } from "./deck_logic";

export interface TileHandlers {
  open(item: DeckItem): void;
  place(item: DeckItem): void;
  pin(item: DeckItem): void;
  tag(item: DeckItem, tags: string[]): void;
  forget(item: DeckItem): void;
  parent(item: DeckItem): void;
  dragStart(item: DeckItem, e: PointerEvent): void;
}

const CONFIRM_MS = 4000;

function button(text: string, cls: string, title: string, run: () => void): HTMLButtonElement {
  const b = el("button", cls, text);
  b.type = "button";
  b.title = title;
  b.onclick = (e) => { e.stopPropagation(); run(); };
  return b;
}

/** Thumbnail when the item has one, otherwise the glyph of its type; this area is also the drag handle. */
function thumb(item: DeckItem, h: TileHandlers): HTMLElement {
  const box = el("div", "dk-thumb");
  const url = safeUrl(item.thumb_url);
  if (url) {
    const img = el("img");
    img.src = url;
    img.alt = "";
    img.draggable = false;
    box.append(img);
  } else {
    box.append(glyphCanvas(glyphForEntity(shapeOfType(item.type), item.title), "#4fd8ff", 64));
  }
  box.title = "Pretahni na plochu";
  box.addEventListener("pointerdown", (e) => e.button === 0 && h.dragStart(item, e));
  return box;
}

/** The menu behind the context button: Pin, Tag..., Forget (needs a second click within a few seconds). */
function menu(item: DeckItem, h: TileHandlers, close: () => void): HTMLElement {
  const m = el("div", "dk-menu");
  m.append(button(item.pinned ? "Odepnout" : "Pripnout", "", "Pripnout nebo odepnout", () => { close(); h.pin(item); }));
  const tags = button("Stitky...", "", "Upravit stitky", () => {
    const input = el("input", "dk-tags");
    input.value = item.tags.join(", ");
    input.setAttribute("aria-label", "Stitky oddelene carkou");
    input.onkeydown = (e) => {
      e.stopPropagation();
      if (e.key === "Enter") { h.tag(item, parseTags(input.value)); close(); }
      else if (e.key === "Escape") close();
    };
    m.replaceChildren(input);
    input.focus();
  });
  let armed: number | undefined;
  const forget = button("Zapomenout", "dk-forget", "Smazat z Decku (dvoukrokove)", () => {
    if (armed === undefined) {
      forget.textContent = "Opravdu zapomenout?";
      forget.classList.add("armed");
      armed = window.setTimeout(() => { armed = undefined; forget.textContent = "Zapomenout"; forget.classList.remove("armed"); }, CONFIRM_MS);
      return;
    }
    clearTimeout(armed);
    close();
    h.forget(item);
  });
  m.append(tags, forget);
  return m;
}

/** One Deck tile; the root is focusable (roving tabindex is set by the grid) and Enter on it opens the item. */
export function renderTile(item: DeckItem, h: TileHandlers, nowSeconds: number): HTMLElement {
  const tile = el("div", "dk-tile");
  tile.dataset.id = item.id;
  tile.setAttribute("role", "listitem");
  tile.tabIndex = -1;
  const head = el("div", "dk-head");
  const star = button(item.pinned ? "\u2605" : "\u2606", "dk-star", item.pinned ? "Odepnout" : "Pripnout", () => h.pin(item));
  star.setAttribute("aria-pressed", String(item.pinned));
  head.append(el("span", "dk-type", item.type.toUpperCase()), star);
  const body = el("div", "dk-body");
  body.append(el("div", "dk-title", item.title), el("div", "dk-sub", item.subtitle ?? ""));
  const meta = el("div", "dk-meta", relativeTime(item.updated_at, nowSeconds));
  const tagRow = el("div", "dk-tagrow");
  for (const t of item.tags) tagRow.append(el("span", "dk-chip", t));
  body.append(meta, tagRow);
  const from = provenance(item);
  if (from) body.append(button(from, "dk-from", "Otevrit puvodni polozku", () => h.parent(item)));
  const acts = el("div", "dk-acts");
  const more = button("...", "dk-more", "Dalsi akce", () => {
    const old = tile.querySelector(".dk-menu");
    if (old) return old.remove();
    tile.append(menu(item, h, () => tile.querySelector(".dk-menu")?.remove()));
  });
  const shop = item.type === "workshop";
  acts.append(button(shop ? "Otevrit dilnu" : "Na plochu", "dk-place", shop ? "Vstoupit do dilny" : "Polozit na plochu", () => h.place(item)), more);
  tile.append(head, thumb(item, h), body, acts);
  tile.addEventListener("keydown", (e) => {
    if (e.target === tile && e.key === "Enter") h.open(item);
  });
  tile.addEventListener("dblclick", () => h.open(item));
  body.onclick = () => h.open(item);
  return tile;
}
