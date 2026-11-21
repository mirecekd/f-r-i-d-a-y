// frontend/src/ui/confirm.ts
import type { Msg, Net } from "../net";
import { el } from "../views/dom";
import "./confirm.css";

interface Request { id: string; tool: string; summary: string; args: unknown; expires_in: number }

const RING = 2 * Math.PI * 22;

function toRequest(m: Msg): Request {
  return { id: String(m.id), tool: String(m.tool ?? ""), summary: String(m.summary ?? ""), args: m.args, expires_in: Number(m.expires_in) || 60 };
}

/** Collapsed JSON tree: objects and arrays are <details>, scalars are text. */
function tree(v: unknown, key?: string, open = false): HTMLElement {
  const row = (k: string | undefined, val: HTMLElement | string) => {
    const r = el("div", "cf-row");
    if (k !== undefined) r.append(el("span", "cf-key", `${k}: `));
    r.append(typeof val === "string" ? el("span", "cf-val", val) : val);
    return r;
  };
  if (v === null || typeof v !== "object") return row(key, typeof v === "string" ? JSON.stringify(v) : String(v));
  const entries = Object.entries(v as object);
  const d = el("details", "cf-node");
  d.open = open;
  d.append(el("summary", "", `${key !== undefined ? `${key}: ` : ""}${Array.isArray(v) ? `[${entries.length}]` : `{${entries.length}}`}`));
  for (const [k, c] of entries) d.append(tree(c, k));
  return d;
}

/** Modal approval dialog for `confirm_request`; queues requests, deny is the default focus, no Enter=allow. */
export class Confirm {
  private queue: Request[] = [];
  private cur: { req: Request; root: HTMLElement; timer: number } | null = null;

  constructor(private net: Net) {
    net.on((m) => {
      if (m.t === "confirm_request") this.add(toRequest(m));
      else if (m.t === "confirm_closed") this.closed(String(m.id));
    });
  }

  private add(req: Request): void {
    this.queue.push(req);
    if (!this.cur) this.next();
  }

  /** STOP: deny the open dialog and every queued request. */
  denyAll(): void {
    for (const r of [...(this.cur ? [this.cur.req] : []), ...this.queue]) this.net.send({ t: "confirm", id: r.id, allow: false });
    this.queue = [];
    this.dismiss();
  }

  private closed(id: string): void {
    this.queue = this.queue.filter((r) => r.id !== id);
    if (this.cur?.req.id === id) this.dismiss();
  }

  private answer(allow: boolean, remember?: "once" | "session"): void {
    if (!this.cur) return;
    this.net.send({ t: "confirm", id: this.cur.req.id, allow, ...(allow && remember ? { remember } : {}) });
    this.dismiss();
  }

  private dismiss(): void {
    if (!this.cur) return;
    clearInterval(this.cur.timer);
    this.cur.root.remove();
    this.cur = null;
    this.next();
  }

  private next(): void {
    const req = this.queue.shift();
    if (!req) return;
    const root = el("div", "cf-back");
    const card = el("div", "cf-card");
    card.setAttribute("role", "alertdialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-label", `Approve ${req.tool}`);
    const secs = Math.max(1, Math.round(req.expires_in));
    const left = el("span", "cf-left", String(secs));
    const ring = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    ring.setAttribute("viewBox", "0 0 52 52");
    ring.classList.add("cf-ring");
    const arc = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    for (const [k, v] of Object.entries({ cx: 26, cy: 26, r: 22 })) arc.setAttribute(k, String(v));
    arc.setAttribute("stroke-dasharray", String(RING));
    ring.append(arc);
    const timer = el("div", "cf-timer");
    timer.append(ring, left);
    const head = el("div", "cf-head");
    const title = el("div", "cf-title");
    title.append(el("div", "cf-tool", req.tool), el("div", "cf-sum", req.summary));
    head.append(title, timer);
    const deny = el("button", "cf-btn deny", "Deny");
    const allow = el("button", "cf-btn allow", "Allow");
    const sess = el("button", "cf-btn allow", "Allow for this session");
    for (const b of [deny, allow, sess]) b.type = "button";
    deny.onclick = () => this.answer(false);
    allow.onclick = () => this.answer(true, "once");
    sess.onclick = () => this.answer(true, "session");
    const btns = el("div", "cf-btns");
    btns.append(deny, allow, sess);
    card.append(head, tree(req.args, "args"), btns);
    if (this.queue.length) card.append(el("div", "cf-more", `+${this.queue.length} more waiting`));
    root.append(card);
    root.onkeydown = (e) => {
      if (e.key === "Escape") this.answer(false);
      else if (e.key === "Tab") {
        const f = [deny, allow, sess];
        const i = f.indexOf(document.activeElement as HTMLButtonElement);
        e.preventDefault();
        f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
      }
    };
    document.body.append(root);
    deny.focus();
    const t0 = performance.now();
    const tick = window.setInterval(() => {
      const f = Math.max(0, 1 - (performance.now() - t0) / (secs * 1000));
      arc.setAttribute("stroke-dashoffset", String(RING * (1 - f)));
      left.textContent = String(Math.ceil(f * secs));
    }, 100);
    this.cur = { req, root, timer: tick };
  }
}
