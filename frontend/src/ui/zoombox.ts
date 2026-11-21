// frontend/src/ui/zoombox.ts
import * as THREE from "three";
import type { Stage } from "../core/stage";
import type { ScenePlayer } from "../scene/player";
import { isTinyStroke, rectHits, regionGoal, screenRect, strokeRect, type Pt, type Rect } from "../core/zoommath";
import { ZoomDraw } from "./zoomdraw";
import { BACK_PATHS, GLASS_PATHS, icon } from "./zoomicon";
import "./zoombox.css";

const MAX_HISTORY = 20;
const DOUBLE_TAP_MS = 350;
const MIN_DISTANCE = 0.5;
const SAMPLE_PX = 2;
interface View { pos: THREE.Vector3; look: THREE.Vector3 }

const typing = (e: Event): boolean => /^(INPUT|TEXTAREA|SELECT)$/.test((e.target as HTMLElement)?.tagName ?? "") || !!(e.target as HTMLElement)?.isContentEditable;

/**
 * Zoom by drawing: a freehand outline on the screen zooms the 3D view to what it encloses.
 * Active with the dock magnifier (or Z), or momentarily with Shift+drag. Alt/Ctrl on release selects instead.
 * Keeps a view history (button ZPET or Backspace) and a home view (double tap on empty space, Home key).
 */
export class ZoomBox {
  private draw = new ZoomDraw();
  private on = false;
  private pts: Pt[] = [];
  private pointer = -1;
  private lastTinyAt = 0;
  private history: View[] = [];
  private home: View;
  private btn = document.createElement("button");
  private back = document.createElement("button");
  private hint = document.createElement("div");

  constructor(private stage: Stage, private player: ScenePlayer, private glideTo: (pos: THREE.Vector3, look: THREE.Vector3) => void) {
    this.home = this.current();
    const canvas = stage.renderer.domElement;
    this.btn.id = "zoombtn";
    this.btn.type = "button";
    this.btn.title = "Zoom kresbou (Z)";
    this.btn.setAttribute("aria-label", "Zoom kresbou");
    this.btn.setAttribute("aria-pressed", "false");
    this.btn.append(icon(26, GLASS_PATHS, [10.5, 10.5, 6.5]));
    this.btn.onclick = () => this.setOn(!this.on);
    this.back.id = "zoomback";
    this.back.type = "button";
    this.back.title = "Zpet (Backspace)";
    this.back.setAttribute("aria-label", "Zpet");
    const label = document.createElement("span");
    label.textContent = "ZPET";
    this.back.append(icon(22, BACK_PATHS), label);
    this.back.hidden = true;
    this.back.onclick = () => this.pop();
    this.hint.id = "zoombox-hint";
    this.hint.hidden = true;
    this.hint.textContent = "ZOOM: OBKRESLI OBLAST";
    document.getElementById("dock")?.append(this.btn, this.back);
    document.body.appendChild(this.hint);

    const onFrame = player.selection.onFrame;
    player.selection.onFrame = (id) => (id ? onFrame(id) : this.reset());
    const mine = (e: PointerEvent): boolean => e.target === canvas || e.target === this.draw.canvas;
    addEventListener("pointerdown", (e) => this.down(e, mine(e)), true);
    addEventListener("pointermove", (e) => e.pointerId === this.pointer && this.move(e), true);
    addEventListener("pointerup", (e) => e.pointerId === this.pointer && this.up(e), true);
    addEventListener("pointercancel", (e) => e.pointerId === this.pointer && this.cancel(), true);
    addEventListener("keydown", (e) => this.key(e));
    (window as any).__zoombox = this;
  }

  /** STOP: leave zoom-by-drawing mode and drop a stroke in progress. */
  exit(): void {
    this.setOn(false);
  }

  private current(): View {
    return { pos: this.stage.camera.position.clone(), look: this.stage.controls.target.clone() };
  }

  private setOn(on: boolean): void {
    this.on = on;
    if (!on) this.cancel();
    this.btn.classList.toggle("on", on);
    this.btn.setAttribute("aria-pressed", String(on));
    this.hint.hidden = !on;
    this.draw.canvas.style.pointerEvents = on ? "auto" : "none";
    this.draw.canvas.style.touchAction = "none";
    document.body.classList.toggle("zoommode", on);
  }

  private key(e: KeyboardEvent): void {
    if (typing(e) || e.ctrlKey || e.metaKey) return;
    if (e.key === "Escape") return this.pointer >= 0 ? this.cancel() : this.setOn(false);
    if (e.key === "z" || e.key === "Z") this.setOn(!this.on);
    else if (e.key === "Backspace") this.pop();
    else if (e.key === "Home") this.reset();
  }

  private down(e: PointerEvent, onView: boolean): void {
    if (this.pointer >= 0) return this.cancel(); // second finger: leave pinch/pan to the orbit controls
    if (!onView || !(this.on || (e.shiftKey && e.pointerType === "mouse")) || (e.pointerType === "mouse" && e.button !== 0)) return;
    e.stopPropagation();
    e.preventDefault();
    this.pointer = e.pointerId;
    this.pts = [{ x: e.clientX, y: e.clientY }];
    this.draw.begin(this.pts[0]);
  }

  private move(e: PointerEvent): void {
    e.stopPropagation();
    const last = this.pts[this.pts.length - 1];
    if (Math.hypot(e.clientX - last.x, e.clientY - last.y) < SAMPLE_PX) return;
    this.pts.push({ x: e.clientX, y: e.clientY });
    this.draw.add(this.pts[this.pts.length - 1]);
  }

  private up(e: PointerEvent): void {
    e.stopPropagation();
    const pts = this.pts;
    this.pointer = -1;
    this.pts = [];
    const rect = strokeRect(pts);
    if (isTinyStroke(rect)) {
      this.draw.clear();
      if (e.timeStamp - this.lastTinyAt < DOUBLE_TAP_MS) this.reset();
      this.lastTinyAt = e.timeStamp;
      return;
    }
    this.draw.end();
    if (e.altKey || e.ctrlKey) this.select(rect);
    else this.zoom(rect);
  }

  private cancel(): void {
    this.pointer = -1;
    this.pts = [];
    this.draw.clear();
  }

  /** Ids of top-level scene objects whose projected bounds fall into the outline rectangle. */
  private hits(rect: Rect): string[] {
    const cam = this.stage.camera;
    cam.updateMatrixWorld();
    const ids: string[] = [];
    for (const [id, e] of this.player.entries) {
      if (e.obj.parent || !e.node.visible) continue;
      const box = new THREE.Box3().setFromObject(e.node);
      const sr = box.isEmpty() ? null : screenRect(box, cam, innerWidth, innerHeight);
      if (sr && rectHits(sr, rect)) ids.push(id);
    }
    return ids;
  }

  private select(rect: Rect): void {
    const ids = this.hits(rect);
    this.player.selection.set(ids);
    this.player.onSelect(ids);
  }

  private zoom(rect: Rect): void {
    const { camera, controls } = this.stage;
    const before = this.current();
    const ids = this.hits(rect);
    if (ids.length) this.player.frame(ids, camera, controls.target);
    else this.glideTo(...goal(regionGoal(rect, camera, controls.target, innerWidth, innerHeight, Math.max(controls.minDistance, MIN_DISTANCE), controls.maxDistance)));
    this.push(before);
  }

  private push(v: View): void {
    this.history.push(v);
    if (this.history.length > MAX_HISTORY) this.history.shift();
    this.back.hidden = false;
  }

  private pop(): void {
    const v = this.history.pop();
    if (!v) return;
    this.back.hidden = this.history.length === 0;
    this.glideTo(v.pos, v.look);
  }

  private reset(): void {
    this.push(this.current());
    this.glideTo(this.home.pos.clone(), this.home.look.clone());
  }
}

const goal = (g: { pos: THREE.Vector3; look: THREE.Vector3 }): [THREE.Vector3, THREE.Vector3] => [g.pos, g.look];
