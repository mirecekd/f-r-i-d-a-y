// frontend/src/gesture/mapper.ts - applies GestureEvents to the 3D scene, the camera and the open view panels.
import type * as THREE from "three";
import type { GestureEvent } from "./events";
import { dolly, orbit, pan, restore, screenToWorld, snapshot, type CamRig, type CamSnapshot } from "./cammove";
import type { Op } from "../scene/types";

export interface GestureHook extends CamRig {
  player: {
    entries: Map<string, { pos: THREE.Vector3; rot: THREE.Vector3; scale: THREE.Vector3; node: THREE.Object3D }>;
    apply(ops: Op[]): void;
    pickAt(nx: number, ny: number): string | undefined;
  };
  views: { close(id: string): void };
  net: { send(m: { t: string }): void };
  /** Gesture 'stop' is sent only while this returns true (setting, default off). */
  stopEnabled: () => boolean;
}

const TWEEN_MS = 90;
const CANCEL_MS = 180;
const FLATTEN_GAIN = 2;
const FLATTEN_EVERY_MS = 120;
const v3 = (v: THREE.Vector3): [number, number, number] => [v.x, v.y, v.z];

interface Held { id: string; pos: THREE.Vector3; rot: THREE.Vector3; scale: THREE.Vector3 }

/** Topmost open view panel (highest z-index) read from the DOM, so the view host stays untouched. */
export function topmostPanelId(): string | undefined {
  let best: HTMLElement | undefined;
  for (const el of document.querySelectorAll<HTMLElement>(".vp[data-id]")) {
    if (!best || Number(el.style.zIndex || 0) >= Number(best.style.zIndex || 0)) best = el;
  }
  return best?.dataset.id;
}

export class GestureMapper {
  private held: Held | null = null;
  private cam: CamSnapshot | null = null;
  private pos = new Map<string, THREE.Vector3>();
  private lastFlatten = 0;
  /** Last event type, shown by the preview label. */
  label = "";

  constructor(private hook: GestureHook, private now: () => number = () => performance.now()) {}

  handle(e: GestureEvent): void {
    this.label = e.type;
    switch (e.type) {
      case "grab": return this.grab(e);
      case "move": return this.move(e);
      case "scale": return this.scale(e.value);
      case "rotate": return this.rotate(e.value);
      case "release": return this.drop();
      case "close": return this.close(e);
      case "flatten": return this.flatten(e.value);
      case "stop": return void (this.hook.stopEnabled() && this.hook.net.send({ t: "stop" }));
    }
  }

  private grab(e: GestureEvent): void {
    const id = this.hook.player.pickAt(e.anchor.x, e.anchor.y);
    const en = id ? this.hook.player.entries.get(id) : undefined;
    this.held = id && en ? { id, pos: en.pos.clone(), rot: en.rot.clone(), scale: en.scale.clone() } : null;
    this.cam = snapshot(this.hook);
    this.pos.clear();
  }

  private move(e: GestureEvent): void {
    const d = e.delta;
    if (!d) return;
    const h = this.held;
    const en = h && this.hook.player.entries.get(h.id);
    if (!h || !en) return pan(this.hook, d.x, d.y);
    const dist = this.hook.camera.position.distanceTo(en.node.getWorldPosition(en.pos.clone()));
    const next = (this.pos.get(h.id) ?? en.pos).clone().add(screenToWorld(this.hook.camera, d.x, d.y, dist));
    this.pos.set(h.id, next);
    this.hook.player.apply([{ op: "set", id: h.id, props: { pos: v3(next) }, ms: TWEEN_MS }]);
  }

  private scale(ratio: number): void {
    const h = this.held;
    if (h) this.hook.player.apply([{ op: "set", id: h.id, props: { scale: v3(h.scale.clone().multiplyScalar(ratio)) }, ms: TWEEN_MS }]);
    else if (this.cam) dolly(this.hook, this.cam, ratio);
  }

  private rotate(angle: number): void {
    const h = this.held;
    if (h) this.hook.player.apply([{ op: "set", id: h.id, props: { rot: [h.rot.x, h.rot.y, h.rot.z - angle] }, ms: TWEEN_MS }]);
    else if (this.cam) orbit(this.hook, this.cam, angle);
  }

  private drop(): void {
    this.held = null;
    this.cam = null;
    this.pos.clear();
  }

  /** Close cancels an active drag (restoring the start state); otherwise it closes the topmost open panel. */
  private close(e: GestureEvent): void {
    const h = this.held;
    if (e.value === 1 || h || this.cam) {
      if (h) this.hook.player.apply([{ op: "set", id: h.id, props: { pos: v3(h.pos), rot: v3(h.rot), scale: v3(h.scale) }, ms: CANCEL_MS }]);
      else if (this.cam) restore(this.hook, this.cam);
      return this.drop();
    }
    const id = topmostPanelId();
    if (id) this.hook.views.close(id);
  }

  private flatten(value: number): void {
    const t = this.now();
    if (value > 0 && t - this.lastFlatten < FLATTEN_EVERY_MS) return;
    this.lastFlatten = t;
    this.hook.player.apply([{ op: "explode", factor: value * FLATTEN_GAIN }]);
  }
}
