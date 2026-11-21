// frontend/src/ui/thinkingpick.ts
import type { Net } from "../net";
import { el } from "../views/dom";
import { Dropdown } from "./voicepick";
import "./thinkingpick.css";

const LABEL: Record<string, string> = { minimal: "Minimalni", low: "Nizke", medium: "Stredni", high: "Vysoke" };

/** One thinking-level dropdown ("Premysleni") for the voice model and the agent models, fed by the `models` message. */
export class ThinkingPick {
  private level: Dropdown;

  constructor(net: Net, host: HTMLElement) {
    this.level = new Dropdown("Premysleni", (id) => net.send({ t: "set_thinking", level: id }));
    const wrap = el("div", "mp-wrap tp-wrap");
    wrap.append(this.level.root);
    host.append(wrap, el("p", "st-note tp-hint", "Plati pro hlasovy model i agenta"));
    net.on((m) => {
      if (m.t !== "models") return;
      const levels: string[] = Array.isArray(m.thinking_levels) ? m.thinking_levels : [];
      this.level.update(levels.map((id) => ({ id, label: LABEL[id] ?? id })), m.thinking ?? "");
    });
  }
}
