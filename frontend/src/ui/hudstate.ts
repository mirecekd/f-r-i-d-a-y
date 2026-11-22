// frontend/src/ui/hudstate.ts
import "./hudstate.css";
import type { Net } from "../net";
import { HudStateModel } from "./hudstate_logic";

/** One line under the orb that says in plain words what the agent is doing, driven by the server's `tool` events. */
export class HudState {
  private model = new HudStateModel();
  private line = document.createElement("div");
  private timer = 0;

  constructor(net: Net) {
    this.line.id = "taskstate";
    this.line.setAttribute("role", "status");
    this.line.setAttribute("aria-live", "polite");
    (document.getElementById("hud") ?? document.body).append(this.line);
    net.on((m) => {
      if (m.t !== "tool") return;
      const now = performance.now();
      if (m.status === "start") this.model.start(String(m.id), String(m.name), now);
      else this.model.end(String(m.id), now);
      this.refresh();
    });
  }

  private refresh(): void {
    window.clearTimeout(this.timer);
    const now = performance.now();
    const { label } = this.model.view(now);
    if (label !== null) this.line.textContent = label; // kept while fading out, so the text does not vanish before the opacity does
    this.line.classList.toggle("show", label !== null);
    const wait = this.model.nextChangeIn(now);
    if (wait !== null) this.timer = window.setTimeout(() => this.refresh(), wait + 5);
  }
}
