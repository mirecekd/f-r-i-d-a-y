// frontend/src/ui/stopbutton.ts
import "./stopbutton.css";
import type { Net } from "../net";
import type { Voice } from "../audio/voice";
import type { Capture } from "./capture";
import type { ZoomBox } from "./zoombox";
import type { Confirm } from "./confirm";

interface Parts { voice: Voice; capture: Capture; zoom: ZoomBox; confirm: Confirm }

const RUNNING_STATES = new Set(["thinking", "drawing", "speaking"]);
/** Esc must keep closing these first. */
const OPEN_LAYERS = ".cf-back, #chat.open, #settingsbtn[aria-expanded=true], .mp-pop:not([hidden]), .mg-full, body.zoommode";

/** Round STOP button: stops playback, mic, capture, zoom mode and dialogs here and sends `{t:'stop'}`; amber ring while busy. */
export class StopButton {
  private serverBusy = false;
  private state = "idle";

  constructor(private net: Net, private button: HTMLElement, private parts: Parts) {
    button.onclick = () => this.stop();
    addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || document.querySelector(OPEN_LAYERS)) return;
      this.stop();
    });
    net.on((m) => {
      if (m.t === "busy") this.serverBusy = m.busy === true;
      else if (m.t === "state") this.state = String(m.state);
      else if (m.t === "stopped") this.flash();
      this.render();
    });
  }

  private stop(): void {
    const { voice, capture, zoom, confirm } = this.parts;
    voice.halt();
    capture.stop();
    zoom.exit();
    confirm.denyAll();
    this.net.send({ t: "stop" });
    this.net.emit({ t: "state", state: "idle" });
    this.serverBusy = false;
    this.flash();
    this.render();
  }

  private flash(): void {
    this.button.classList.remove("flash");
    void this.button.offsetWidth; // restart the animation
    this.button.classList.add("flash");
  }

  private render(): void {
    const busy = this.serverBusy || this.parts.voice.active || RUNNING_STATES.has(this.state);
    this.button.classList.toggle("busy", busy);
  }
}
