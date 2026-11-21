// frontend/src/ui/deck.ts
import "./deck.css";
import type * as THREE from "three";
import type { Msg, Net } from "../net";
import { el } from "../views/dom";
import { startTileDrag } from "./deck_drag";
import { filterItems, gridMove, SORT_LABELS, sortItems, typeChips, type DeckItem, type SortMode } from "./deck_logic";
import { linkInput } from "./deck_url";
import { renderTile, type TileHandlers } from "./deck_tile";
import { isTypingTarget } from "./entitybar_logic";
import { Dropdown } from "./voicepick";
import { dropChatText } from "./workshop_logic";

const SEARCH_DEBOUNCE_MS = 250;

/** The Deck window: a browsable overview of everything saved or created; tiles are opened, placed on the desk or dragged onto it. */
export class Deck {
  private panel = el("section", "dk-panel");
  private search = el("input", "dk-search");
  private sort = new Dropdown("Razeni", (id) => { this.mode = id as SortMode; this.syncSort(); this.render(); });
  private chips = el("div", "dk-chips");
  private grid = el("div", "dk-grid");
  private items: DeckItem[] = [];
  private total = 0;
  private byType: Record<string, number> = {};
  private type = "";
  private mode: SortMode = "newest";
  private timer = 0;
  private loadingMore = false;

  constructor(
    private net: Net,
    private button: HTMLElement,
    private canvas: HTMLElement,
    private camera: THREE.PerspectiveCamera,
    private ask: (text: string) => void,
    private inWorkshop: () => boolean = () => false,
  ) {
    this.panel.hidden = true;
    this.panel.setAttribute("role", "dialog");
    this.panel.setAttribute("aria-label", "Deck");
    this.search.type = "search";
    this.search.placeholder = "Hledat v Decku...";
    this.search.setAttribute("aria-label", "Hledat v Decku");
    this.search.oninput = () => { clearTimeout(this.timer); this.timer = window.setTimeout(() => this.request(false), SEARCH_DEBOUNCE_MS); };
    this.syncSort();
    const close = el("button", "dk-close", "Zavrit");
    close.type = "button";
    close.style.minHeight = "44px";
    close.onclick = () => this.setOpen(false);
    const top = el("div", "dk-top");
    const newShop = el("button", "dk-newshop", "Nova dilna");
    newShop.type = "button";
    newShop.style.minHeight = "44px";
    newShop.onclick = () => this.net.send({ t: "workshop_new" });
    top.append(el("span", "dk-name", "DECK"), this.search, linkInput(net), this.sort.root, newShop, close);
    this.grid.setAttribute("role", "list");
    this.grid.onkeydown = (e) => this.onGridKey(e);
    this.panel.append(top, this.chips, this.grid);
    document.body.append(this.panel);
    button.onclick = () => this.setOpen(!this.isOpen());
    button.setAttribute("aria-expanded", "false");
    addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) { e.preventDefault(); this.setOpen(false); }
      else if ((e.key === "d" || e.key === "D") && !e.ctrlKey && !e.metaKey && !e.altKey && !isTypingTarget(e.target as HTMLElement | null)) this.setOpen(!this.isOpen());
    }, true);
    net.on((m) => this.onMessage(m));
  }

  isOpen(): boolean {
    return this.panel.hidden === false;
  }

  setOpen(open: boolean): void {
    this.panel.hidden = !open;
    this.button.setAttribute("aria-expanded", String(open));
    this.button.classList.toggle("on", open);
    if (open) { this.request(false); this.search.focus(); }
  }

  private request(more: boolean): void {
    this.loadingMore = more;
    this.net.send({ t: "deck_list", ...(this.type ? { type: this.type } : {}), ...(this.search.value.trim() ? { q: this.search.value.trim() } : {}), offset: more ? this.items.length : 0 });
  }

  private onMessage(m: Msg): void {
    if (m.t === "deck") {
      const got = (Array.isArray(m.items) ? m.items : []) as DeckItem[];
      this.items = this.loadingMore ? [...this.items, ...got] : got;
      this.loadingMore = false;
      this.total = Number(m.total ?? this.items.length);
      this.byType = m.stats?.by_type ?? {};
      this.render();
    } else if (m.t === "deck_changed" && this.isOpen()) this.request(false);
    else if (m.t === "workshop" && m.op === "enter") this.setOpen(false);
  }

  private handlers: TileHandlers = {
    open: (it) => this.net.send(it.type === "workshop" ? { t: "workshop_open", id: it.id } : { t: "deck_open", id: it.id }),
    place: (it) => this.net.send(it.type === "workshop" ? { t: "workshop_open", id: it.id } : { t: "deck_place", id: it.id }),
    pin: (it) => this.net.send({ t: "deck_pin", id: it.id, pinned: !it.pinned }),
    tag: (it, tags) => this.net.send({ t: "deck_tag", id: it.id, tags }),
    forget: (it) => this.net.send({ t: "deck_forget", id: it.id }),
    parent: (it) => this.net.send({ t: "deck_open", id: it.parent_ids[0] }),
    dragStart: (it, e) => startTileDrag(it, e, this.panel, {
      canvas: this.canvas,
      camera: this.camera,
      onDesk: (item, pos) => (this.inWorkshop() ? this.ask(dropChatText(item.title, item.id)) : this.net.send({ t: "deck_place", id: item.id, ...(pos ? { pos } : {}) })),
      onChat: (item) => this.ask(`Pouzij ${item.title} (${item.id})`),
    }),
  };

  /** Shows the active sort mode in the dropdown (same look as the model and voice pickers). */
  private syncSort(): void {
    this.sort.update(
      (Object.keys(SORT_LABELS) as SortMode[]).map((id) => ({ id, label: SORT_LABELS[id] })),
      this.mode,
    );
  }

  private render(): void {
    this.chips.replaceChildren();
    for (const c of typeChips(this.byType, Object.values(this.byType).reduce((a, b) => a + b, 0) || this.total)) {
      const b = el("button", `dk-fchip${c.type === this.type ? " on" : ""}`, `${c.type || "vse"} ${c.count}`);
      b.type = "button";
      b.setAttribute("aria-pressed", String(c.type === this.type));
      b.onclick = () => { this.type = c.type; this.request(false); };
      this.chips.append(b);
    }
    const shown = sortItems(filterItems(this.items, this.type, this.search.value), this.mode);
    const now = Date.now() / 1000;
    this.grid.replaceChildren(...shown.map((it) => renderTile(it, this.handlers, now)));
    if (!shown.length) this.grid.append(el("div", "dk-empty", this.search.value || this.type ? "Nic nenalezeno." : "Deck je zatim prazdny. Pretahni na plochu soubor nebo pozadej Friday, aby neco vytvorila."));
    else if (this.items.length < this.total) {
      const more = el("button", "dk-more-page", "Nacist dalsi");
      more.type = "button";
      more.onclick = () => this.request(true);
      this.grid.append(more);
    }
    this.tiles()[0]?.setAttribute("tabindex", "0");
  }

  private tiles(): HTMLElement[] {
    return [...this.grid.querySelectorAll<HTMLElement>(".dk-tile")];
  }

  private columns(): number {
    const tiles = this.tiles();
    if (tiles.length < 2) return 1;
    const top = tiles[0].offsetTop;
    const n = tiles.findIndex((t) => t.offsetTop !== top);
    return n < 0 ? tiles.length : n;
  }

  private onGridKey(e: KeyboardEvent): void {
    const tiles = this.tiles();
    const at = tiles.findIndex((t) => t === document.activeElement || t.contains(document.activeElement));
    if (at < 0 || isTypingTarget(e.target as HTMLElement | null)) return;
    const next = gridMove(at, e.key, this.columns(), tiles.length);
    if (next === at && !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    tiles.forEach((t, i) => t.setAttribute("tabindex", i === next ? "0" : "-1"));
    tiles[next].focus();
  }
}
