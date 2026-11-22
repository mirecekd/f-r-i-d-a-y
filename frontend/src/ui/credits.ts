// frontend/src/ui/credits.ts
import type { Net } from "../net";
import { el } from "../views/dom";
import { parseCredits, summaryLabel } from "./credits_logic";
import "./credits.css";

/** Collapsible list "Zdroje modelu" in the settings panel: author and licence of every catalog model placed in the scene. */
export class AssetCredits {
  private toggle = el("button", "cr-toggle", "Zdroje modelu: zatim zadne");
  private list = el("ul", "cr-list");
  private count = 0;

  constructor(private net: Net, host: HTMLElement) {
    this.list.hidden = true;
    this.toggle.type = "button";
    this.toggle.setAttribute("aria-expanded", "false");
    this.toggle.onclick = () => this.flip();
    host.append(this.toggle, this.list);
    net.on((m) => { if (m.t === "assets") this.render(m.items); });
  }

  private flip(): void {
    const open = this.list.hidden;
    this.list.hidden = !open;
    this.toggle.setAttribute("aria-expanded", String(open));
    if (open) this.net.send({ t: "assets_credits" });
  }

  private render(items: unknown): void {
    const rows = parseCredits(items);
    this.count = rows.length;
    this.toggle.textContent = `Zdroje modelu: ${summaryLabel(this.count)}`;
    this.list.replaceChildren(...rows.map((c) => {
      const li = el("li", "cr-item");
      li.append(el("span", "cr-name", c.name), el("span", "cr-meta", ` - ${c.author || "autor neznamy"}, ${c.license}`));
      if (c.source_page) {
        const a = el("a", "cr-link", " zdroj");
        a.href = c.source_page;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        li.append(a);
      }
      return li;
    }));
  }
}
