// frontend/src/ui/newchat.ts
import "./newchat.css";
import type { Net } from "../net";
import type { Chat } from "./chat";
import { views } from "../views/host";

const CONFIRM_MS = 3000;
const CONFIRM_ABOVE = 3;
const NOTE = "Nova konverzace";
const SVG_NS = "http://www.w3.org/2000/svg";

/** Speech bubble with a plus, built as DOM nodes (no HTML string). */
function icon(): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  const attrs = { viewBox: "0 0 24 24", width: "22", height: "22", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" };
  for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, v);
  for (const d of ["M4 5h16v11H10l-4 3.5V16H4z", "M12 8v5M9.5 10.5h5"]) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

function make<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, text = ""): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  el.className = cls;
  el.textContent = text;
  return el;
}

/** "Nova konverzace" in the chat panel header: asks the server to forget the context, then empties the log. */
export class NewChat {
  private button = make("button", "nc-btn");
  private ask = make("span", "nc-ask");
  private timer = 0;

  constructor(private net: Net, private chat: Chat) {
    const head = make("div", "nc-head");
    this.button.type = "button";
    this.button.title = NOTE;
    this.button.setAttribute("aria-label", NOTE);
    this.button.append(icon());
    this.button.onclick = () => this.request();
    const yes = make("button", "nc-yes", "Ano");
    const no = make("button", "nc-no", "Ne");
    for (const b of [yes, no]) b.type = "button";
    yes.onclick = () => this.confirmed();
    no.onclick = () => this.cancel();
    this.ask.hidden = true;
    this.ask.append(make("span", "nc-q", "Opravdu?"), yes, no);
    head.append(make("span", "nc-title", "Chat"), this.ask, this.button);
    document.getElementById("chat")!.prepend(head);
    addEventListener("keydown", (e) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "n" && this.chat.isOpen()) {
        e.preventDefault();
        this.request();
      }
    });
    net.on((m) => {
      if (m.t !== "conversation_reset") return;
      this.cancel();
      this.chat.reset(NOTE);
      if (m.clear_scene) views.ids().forEach((id) => views.close(id));
    });
  }

  private request(): void {
    if (this.chat.messageCount() > CONFIRM_ABOVE) return this.showAsk();
    this.confirmed();
  }

  private showAsk(): void {
    this.button.hidden = true;
    this.ask.hidden = false;
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.cancel(), CONFIRM_MS);
  }

  private cancel(): void {
    clearTimeout(this.timer);
    this.ask.hidden = true;
    this.button.hidden = false;
  }

  private confirmed(): void {
    this.cancel();
    const stop = document.getElementById("stopbtn");
    if (stop?.classList.contains("busy")) stop.click(); // halts mic, playback and capture here, like STOP
    this.net.send({ t: "new_conversation" });
  }
}
