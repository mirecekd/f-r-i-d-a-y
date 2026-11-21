// frontend/src/ui/settings.ts
import type { Net } from "../net";
import { el } from "../views/dom";
import "./settings.css";

/** Settings panel opened by the header gear: glass card with a registry of titled sections. */
export class Settings {
  readonly panel = el("aside", "");
  private body = el("div", "st-body");
  private version = el("span", "st-version", "-");
  private sections = new Map<string, HTMLElement>();

  constructor(net: Net, private gear: HTMLElement) {
    this.panel.id = "settings";
    this.panel.setAttribute("role", "dialog");
    this.panel.setAttribute("aria-label", "Nastaveni");
    this.panel.setAttribute("aria-hidden", "true");
    this.panel.append(el("div", "st-title", "Nastaveni"), this.body);
    document.getElementById("hud")!.after(this.panel);
    this.section("Modely"); // first in the list; Models mounts into it
    this.buildDefaults();
    gear.onclick = () => this.toggle();
    document.addEventListener("pointerdown", (e) => {
      const t = e.target as Node;
      if (this.isOpen() && !this.panel.contains(t) && !gear.contains(t)) this.close(false);
    });
    document.addEventListener("keydown", (e) => this.key(e));
    net.on((m) => { if (m.t === "hello") this.version.textContent = String(m.version ?? "-"); });
  }

  /** Registers a titled section (or returns the existing one) and returns its content container. */
  section(title: string): HTMLElement {
    const known = this.sections.get(title);
    if (known) return known;
    const box = el("section", "st-section");
    const content = el("div", "st-content");
    box.append(el("h2", "st-head", title), content);
    this.body.append(box);
    this.sections.set(title, content);
    return content;
  }

  isOpen(): boolean {
    return this.panel.classList.contains("open");
  }

  private buildDefaults(): void {
    this.section("Nastroje a MCP").append(el("p", "st-note", "bude pribyvat: zapinani a vypinani nastroju"));
    const about = this.section("O aplikaci");
    const ver = el("p", "st-note", "Verze: ");
    ver.append(this.version);
    about.append(ver);
  }

  toggle(): void {
    if (this.isOpen()) this.close(true);
    else this.open();
  }

  private open(): void {
    this.panel.classList.add("open");
    this.panel.setAttribute("aria-hidden", "false");
    this.gear.setAttribute("aria-expanded", "true");
    this.gear.classList.add("on");
    this.panel.querySelector<HTMLElement>("button:not([disabled])")?.focus({ preventScroll: true });
  }

  private close(refocus: boolean): void {
    this.panel.classList.remove("open");
    this.panel.setAttribute("aria-hidden", "true");
    this.gear.setAttribute("aria-expanded", "false");
    this.gear.classList.remove("on");
    if (refocus) this.gear.focus();
  }

  /** Esc closes (unless a dropdown popup is open and handles it); Tab wraps inside the panel. */
  private key(e: KeyboardEvent): void {
    if (!this.isOpen()) return;
    if (e.key === "Escape") {
      if (this.panel.querySelector(".mp-pop:not([hidden])")) return;
      e.preventDefault();
      this.close(true);
    } else if (e.key === "Tab") {
      const f = [...this.panel.querySelectorAll<HTMLElement>("button:not([disabled])")].filter((x) => x.offsetParent);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }
}
