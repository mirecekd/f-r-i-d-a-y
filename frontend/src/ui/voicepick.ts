// frontend/src/ui/voicepick.ts
import type { Net } from "../net";
import { el } from "../views/dom";
import "./models.css";
import "./voicepick.css";

export interface Option { id: string; label: string; hint?: string; mark?: string }

/** Dropdown in the style of the model pickers (same .mp classes); options carry an optional gender mark and style hint. */
export class Dropdown {
  readonly root = el("div", "mp");
  private btn = el("button", "mp-btn");
  private pop = el("div", "mp-pop");
  private options: Option[] = [];
  private active = "";

  constructor(private title: string, private onPick: (id: string) => void) {
    this.btn.type = "button";
    this.btn.setAttribute("aria-haspopup", "listbox");
    this.btn.setAttribute("aria-expanded", "false");
    this.pop.setAttribute("role", "listbox");
    this.pop.setAttribute("aria-label", title);
    this.pop.hidden = true;
    this.root.append(this.btn, this.pop);
    this.btn.onclick = () => (this.pop.hidden ? this.open() : this.close());
    this.btn.onkeydown = (e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); this.open(); } };
    this.pop.onkeydown = (e) => this.key(e);
    document.addEventListener("pointerdown", (e) => { if (!this.root.contains(e.target as Node)) this.close(); });
    this.render();
  }

  update(options: Option[], active: string): void {
    this.options = options;
    this.active = active;
    this.render();
  }

  private render(): void {
    const cur = this.options.find((o) => o.id === this.active);
    this.btn.disabled = this.options.length === 0;
    this.btn.replaceChildren(el("span", "mp-role", this.title), el("span", "mp-cur", cur ? `${cur.mark ?? ""} ${cur.label}`.trim() : "-"));
    this.pop.replaceChildren(
      ...this.options.map((o) => {
        const b = el("button", "mp-opt vp-opt");
        if (o.mark) b.append(el("span", "vp-mark", o.mark));
        b.append(el("span", "vp-label", o.label));
        if (o.hint) b.append(el("span", "vp-hint", o.hint));
        b.type = "button";
        b.tabIndex = -1;
        b.dataset.id = o.id;
        b.setAttribute("role", "option");
        b.setAttribute("aria-selected", String(o.id === this.active));
        b.onclick = () => this.pick(o.id);
        return b;
      }),
    );
  }

  private opts(): HTMLElement[] {
    return [...this.pop.querySelectorAll<HTMLElement>(".mp-opt")];
  }

  private open(): void {
    this.pop.hidden = false;
    this.btn.setAttribute("aria-expanded", "true");
    const o = this.opts();
    (o.find((x) => x.dataset.id === this.active) ?? o[0])?.focus();
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
    this.onPick(id);
  }
}

const MARK: Record<string, string> = { female: "\u2640", male: "\u2642" };

interface VoiceInfo { id: string; label: string; gender: string; style: string }
interface LangInfo { code: string; label: string }

/** Voice ("Hlas") and language ("Jazyk") dropdowns fed by the `models` message. */
export class VoicePick {
  private voice: Dropdown;
  private lang: Dropdown;

  constructor(net: Net, host: HTMLElement) {
    this.voice = new Dropdown("Hlas", (id) => net.send({ t: "set_voice", voice: id }));
    this.lang = new Dropdown("Jazyk", (id) => net.send({ t: "set_language", language: id }));
    const wrap = el("div", "mp-wrap vp-wrap");
    wrap.append(this.voice.root, this.lang.root);
    host.append(wrap);
    net.on((m) => {
      if (m.t !== "models") return;
      const voices: VoiceInfo[] = Array.isArray(m.voices) ? m.voices : [];
      const langs: LangInfo[] = Array.isArray(m.languages) ? m.languages : [];
      this.voice.update(
        voices.map((v) => ({ id: v.id, label: v.label, hint: `${v.gender === "female" ? "zena" : "muz"}, ${v.style}`, mark: MARK[v.gender] })),
        m.voice ?? "",
      );
      this.lang.update(langs.map((l) => ({ id: l.code, label: l.label, hint: l.code })), m.language ?? "");
    });
  }
}
