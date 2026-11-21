// frontend/src/ui/workshop.ts
import "./workshop.css";
import type { Msg, Net } from "../net";
import { isTypingTarget } from "./entitybar_logic";
import { WorkshopPanel } from "./workshop_panel";
import { encodeSnapshot, MAX_SNAPSHOT_WIDTH } from "./workshop_snapshot";
import { ParamThrottle } from "./workshop_throttle";
import {
  EMPTY_STATE, leaveCam, reduce, removeSourceText, routeServerMessage, toCam, toggleMessage, workshopKeyAction,
  type Cam, type WorkshopState,
} from "./workshop_logic";

/** Esc and W step aside while any of these is open. */
const BLOCKING_LAYERS = ".dk-panel:not([hidden]), .cf-back, #ctxmenu:not([hidden]), .mp-pop:not([hidden]), #chat.open, #settingsbtn[aria-expanded=true], .mg-full, body.zoommode";

export interface WorkshopDeps {
  /** Camera pose now (position and orbit target), as plain arrays. */
  pose(): Cam;
  glide(pos: [number, number, number], look: [number, number, number]): void;
  /** Renders one frame and returns it scaled to `width` (Stage.snapshot). */
  snapshot(width: number): HTMLCanvasElement;
  focus(entityId: string): void;
  /** Workshop id of the single selected workshop tile, if any. */
  selectedWorkshop(): string | null;
  ask(text: string): void;
}

/** The Workshop (Dilna): camera glide into and out of the table, the side panel, W / Esc keys and snapshots for the model. The rest is ordinary scene ops. */
export class Workshop {
  private state: WorkshopState = EMPTY_STATE;
  private lastId: string | null = null;
  private panel: WorkshopPanel;
  private throttle: ParamThrottle;

  constructor(private net: Net, private deps: WorkshopDeps) {
    this.throttle = new ParamThrottle(
      (name, value) => this.net.send({ t: "workshop_param", id: this.state.id, name, value }),
      () => performance.now(),
      (fn, ms) => window.setTimeout(fn, ms),
      (h) => clearTimeout(h as number),
    );
    this.panel = new WorkshopPanel({
      param: (name, value) => this.throttle.push(name, value),
      commit: (name) => this.throttle.flush(name),
      undo: () => this.net.send({ t: "workshop_undo", id: this.state.id }),
      redo: () => this.net.send({ t: "workshop_redo", id: this.state.id }),
      leave: () => this.net.send({ t: "workshop_leave" }),
      ask: (text) => deps.ask(text),
      focus: (id) => deps.focus(id),
      removeSource: (title) => deps.ask(removeSourceText(title)),
    });
    net.on((m) => this.onMessage(m));
    addEventListener("keydown", (e) => this.onKey(e), true); // capture, registered before the entity bar
  }

  isOpen(): boolean {
    return this.state.open;
  }

  private onMessage(m: Msg): void {
    const route = routeServerMessage(m);
    if (route === "snapshot") return this.answerSnapshot(m);
    if (route !== "state") return;
    const before = this.state;
    const cam = m.op === "leave" ? (before.open && m.id === before.id ? leaveCam(before, m) : null) : toCam(m.camera);
    this.state = reduce(before, m, this.deps.pose());
    if (m.op === "enter" && this.state.open) this.lastId = this.state.id;
    document.body.classList.toggle("ws-open", this.state.open);
    this.panel.update(this.state);
    if (cam && (m.op === "enter" || m.op === "leave")) this.deps.glide(cam.pos, cam.look);
  }

  private answerSnapshot(m: Msg): void {
    const reply = (extra: Record<string, unknown>): void => void this.net.send({ t: "workshop_snapshot", req: m.req, id: m.id, ...extra });
    if (document.hidden) return reply({ error: "hidden" });
    try {
      const width = typeof m.width === "number" && m.width > 0 ? Math.min(m.width, MAX_SNAPSHOT_WIDTH) : MAX_SNAPSHOT_WIDTH;
      const b64 = encodeSnapshot((w) => this.deps.snapshot(w), (c, q) => c.toDataURL("image/jpeg", q), width);
      reply(b64 ? { jpeg_b64: b64 } : { error: "too_large" });
    } catch {
      reply({ error: "failed" });
    }
  }

  private onKey(e: KeyboardEvent): void {
    const target = e.target as HTMLElement | null;
    const action = workshopKeyAction(e, { open: this.state.open, typing: isTypingTarget(target), blocked: !!document.querySelector(BLOCKING_LAYERS) });
    if (!action) return;
    e.preventDefault(); // the global Esc = stop handler and the entity bar skip a handled key
    this.net.send(action === "leave" ? { t: "workshop_leave" } : toggleMessage(this.state, this.deps.selectedWorkshop(), this.lastId));
  }
}
