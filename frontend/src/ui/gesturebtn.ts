// frontend/src/ui/gesturebtn.ts - dock button, preview and wiring of the hand-gesture pipeline (the MediaPipe code loads lazily).
import "./gesturebtn.css";
import { GestureLogic } from "../gesture/logic";
import { GestureMapper, type GestureHook } from "../gesture/mapper";
import { HandTracker } from "../gesture/tracker";
import { attachDemo, DEMO_HELP } from "../gesture/demo";
import { loadPrefs, savePrefs } from "../gesture/prefs";
import { GesturePreview } from "./gesturepreview";

const HAND = "M9 11V5.5a1.5 1.5 0 0 1 3 0V10 M12 10V4.5a1.5 1.5 0 0 1 3 0V10 M15 10V5.5a1.5 1.5 0 0 1 3 0V13a7 7 0 0 1-7 7h-.5a6 6 0 0 1-4.7-2.3L3.5 13.5a1.5 1.5 0 0 1 2.3-1.9L9 14.5V11";
const HINT = "Postav se tak, aby byly videt obe ruce";

/** Hook from main.ts without the `stopEnabled` flag: that one is owned by the persisted preference here. */
export type GestureWiring = Omit<GestureHook, "stopEnabled">;

export class GestureButton {
  private prefs = loadPrefs();
  private btn = document.createElement("button");
  private logic = new GestureLogic();
  private mapper: GestureMapper;
  private tracker: HandTracker;
  private preview: GesturePreview;
  private hint = document.createElement("div");
  private running = false;

  constructor(hook: GestureWiring, settingsSection?: HTMLElement) {
    this.mapper = new GestureMapper({ ...hook, stopEnabled: () => this.prefs.stop });
    this.preview = new GesturePreview((this.tracker = new HandTracker((f) => this.onFrame(f))).video);
    this.btn.id = "gesturebtn";
    this.btn.type = "button";
    this.btn.title = "Gesta rukou";
    this.btn.setAttribute("aria-label", "Gesta rukou");
    this.btn.setAttribute("aria-pressed", "false");
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "26");
    svg.setAttribute("height", "26");
    for (const [k, v] of [["fill", "none"], ["stroke", "currentColor"], ["stroke-width", "1.8"], ["stroke-linecap", "round"], ["stroke-linejoin", "round"], ["aria-hidden", "true"]]) svg.setAttribute(k, v);
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", HAND);
    svg.append(path);
    this.btn.append(svg);
    this.btn.onclick = () => void this.set(!this.running);
    this.hint.id = "gesturehint";
    this.hint.hidden = true;
    this.hint.textContent = HINT;
    document.getElementById("zoombtn")?.after(this.btn) ?? document.getElementById("dock")?.append(this.btn);
    document.body.appendChild(this.hint);
    if (settingsSection) this.stopToggle(settingsSection);
    if (new URLSearchParams(location.search).has("gesturedemo")) this.demo();
    else if (this.prefs.enabled) void this.set(true);
  }

  /** Enables or disables tracking; the setting persists. */
  async set(on: boolean): Promise<void> {
    if (on === this.running) return;
    this.running = on;
    this.prefs.enabled = on;
    savePrefs(this.prefs);
    this.btn.classList.toggle("on", on);
    this.btn.setAttribute("aria-pressed", String(on));
    this.preview.show(on && this.prefs.preview);
    if (!on) {
      this.tracker.stop();
      this.hint.hidden = true;
      return;
    }
    this.preview.say("Nacitani modelu...");
    const err = await this.tracker.start();
    if (!this.running) return;
    this.preview.say(err ?? "");
    if (err) return void this.fail();
    if (!this.prefs.seenHint) {
      this.hint.hidden = false;
      this.prefs.seenHint = true;
      savePrefs(this.prefs);
      setTimeout(() => (this.hint.hidden = true), 5000);
    }
  }

  /** Persisted toggle: the open palm 'stop' gesture sends {t:'stop'} only when this is on (default off). */
  setStopGesture(on: boolean): void {
    this.prefs.stop = on;
    savePrefs(this.prefs);
  }

  stopGesture(): boolean {
    return this.prefs.stop;
  }

  private stopToggle(box: HTMLElement): void {
    const label = document.createElement("label");
    label.className = "st-note";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = this.prefs.stop;
    cb.onchange = () => this.setStopGesture(cb.checked);
    label.append(cb, " Otevrena dlan 0,6 s = Stop (vypnuto ve vychozim stavu)");
    box.append(label);
  }

  private fail(): void {
    this.running = false;
    this.btn.classList.remove("on");
    this.btn.setAttribute("aria-pressed", "false");
    this.tracker.stop();
  }

  private onFrame(f: Parameters<GestureLogic["feed"]>[0]): void {
    for (const e of this.logic.feed(f)) this.mapper.handle(e);
    this.preview.draw(f);
    this.preview.label(this.mapper.label);
  }

  private demo(): void {
    this.btn.classList.add("on");
    this.preview.show(true);
    this.preview.say(DEMO_HELP);
    attachDemo((e) => {
      this.mapper.handle(e);
      this.preview.label(this.mapper.label);
    });
  }
}
