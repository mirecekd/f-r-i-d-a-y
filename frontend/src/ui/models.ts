// frontend/src/ui/models.ts
import type { Net } from "../net";
import { el } from "../views/dom";
import "./models.css";

interface Caps { tools?: boolean; vision?: boolean; reasoning?: boolean }
interface CatalogEntry { id: string; provider: string; label: string; group: string; roles: Role[]; caps?: Caps }
type Role = "agent" | "chat";

const BADGES: [keyof Caps, string, string][] = [
  ["tools", "T", "function calling"],
  ["vision", "V", "vision"],
  ["reasoning", "R", "reasoning"],
];

/** One dropdown (listbox popup) for a role; keyboard: Enter/Space/ArrowDown open, arrows move, Esc closes. */
class Picker {
  readonly root = el("div", "mp");
  private btn = el("button", "mp-btn");
  private pop = el("div", "mp-pop");
  private entries: CatalogEntry[] = [];
  private active = "";

  constructor(private role: Role, private title: string, private net: Net) {
    this.btn.type = "button";
    this.btn.setAttribute("aria-haspopup", "listbox");
    this.btn.setAttribute("aria-expanded", "false");
    this.pop.setAttribute("role", "listbox");
    this.pop.setAttribute("aria-label", title);
    this.pop.hidden = true;
    this.root.append(this.btn, this.pop);
    this.btn.onclick = () => (this.pop.hidden ? this.open() : this.close());
    this.btn.onkeydown = (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); this.open(); }
    };
    this.pop.onkeydown = (e) => this.key(e);
    document.addEventListener("pointerdown", (e) => { if (!this.root.contains(e.target as Node)) this.close(); });
    this.render();
  }

  update(entries: CatalogEntry[], active: string): void {
    this.entries = entries.filter((e) => e.roles?.includes(this.role));
    this.active = active;
    this.render();
  }

  private render(): void {
    const cur = this.entries.find((e) => e.id === this.active);
    const na = this.entries.length === 0;
    this.btn.disabled = na;
    this.btn.replaceChildren(el("span", "mp-role", this.title), el("span", "mp-cur", na ? "models n/a" : (cur?.label ?? this.active) || "-"));
    this.pop.replaceChildren();
    const groups = new Map<string, CatalogEntry[]>();
    for (const e of this.entries) {
      const g = `${e.provider} / ${e.group}`;
      groups.set(g, [...(groups.get(g) ?? []), e]);
    }
    for (const [g, list] of groups) {
      this.pop.append(el("div", "mp-group", g));
      for (const e of list) {
        const o = el("button", "mp-opt", e.label);
        const caps = BADGES.filter(([k]) => e.caps?.[k]);
        for (const [, letter] of caps) o.append(el("span", "mp-cap", letter));
        if (caps.length) o.title = `${e.id}: ${caps.map(([, , name]) => name).join(", ")}`;
        else o.title = e.id;
        o.type = "button";
        o.tabIndex = -1;
        o.dataset.id = e.id;
        o.setAttribute("role", "option");
        o.setAttribute("aria-selected", String(e.id === this.active));
        o.onclick = () => this.pick(e.id);
        this.pop.append(o);
      }
    }
  }

  private opts(): HTMLElement[] {
    return [...this.pop.querySelectorAll<HTMLElement>(".mp-opt")];
  }

  private open(): void {
    this.pop.hidden = false;
    this.btn.setAttribute("aria-expanded", "true");
    const o = this.opts();
    (o.find((x) => x.dataset.id === this.active) ?? o[0])?.focus();
    this.pop.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }

  private close(): void {
    this.pop.hidden = true;
    this.btn.setAttribute("aria-expanded", "false");
  }

  private key(e: KeyboardEvent): void {
    const o = this.opts();
    const i = o.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); o[(n + o.length) % o.length]?.focus(); };
    if (e.key === "ArrowDown") to(i + 1);
    else if (e.key === "ArrowUp") to(i - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(o.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); this.close(); this.btn.focus(); }
    else if (e.key === "Tab") this.close();
  }

  private pick(id: string): void {
    this.close();
    this.btn.focus();
    if (id === this.active) return;
    this.active = id;
    this.render();
    this.net.send({ t: "set_model", role: this.role, model: id });
  }
}

/** Header pickers for the agent and chat models, fed by the server `models` message. */
export class Models {
  private pickers: Record<Role, Picker>;

  constructor(net: Net, header: HTMLElement) {
    this.pickers = { agent: new Picker("agent", "Agent model", net), chat: new Picker("chat", "Chat model", net) };
    const wrap = el("div", "mp-wrap");
    wrap.append(this.pickers.agent.root, this.pickers.chat.root);
    header.append(wrap);
    net.on((m) => {
      if (m.t !== "models") return;
      const cat: CatalogEntry[] = Array.isArray(m.catalog) ? m.catalog : [];
      this.pickers.agent.update(cat, m.pinned?.agent_model ?? "");
      this.pickers.chat.update(cat, m.pinned?.chat_model ?? "");
    });
  }
}
