// frontend/src/core/zoommath.ts
import * as THREE from "three";
import type { CamGoal } from "./glide";

export interface Rect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Pt {
  x: number;
  y: number;
}

/** Strokes whose larger side is below this are taps, not zoom gestures. */
export const MIN_STROKE_PX = 12;
const MIN_ZOOM_SCALE = 0.04;
const OVERLAP_TO_HIT = 0.5;

export function strokeRect(pts: Pt[]): Rect {
  const r = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  for (const p of pts) {
    r.x0 = Math.min(r.x0, p.x);
    r.y0 = Math.min(r.y0, p.y);
    r.x1 = Math.max(r.x1, p.x);
    r.y1 = Math.max(r.y1, p.y);
  }
  return r;
}

export const isTinyStroke = (r: Rect): boolean => Math.max(r.x1 - r.x0, r.y1 - r.y0) < MIN_STROKE_PX;

/** Screen-space (px) bounds of a world box, or null when any corner is behind the camera. */
export function screenRect(box: THREE.Box3, camera: THREE.PerspectiveCamera, w: number, h: number): Rect | null {
  const r = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  const v = new THREE.Vector3();
  for (let i = 0; i < 8; i++) {
    v.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z);
    if (v.clone().applyMatrix4(camera.matrixWorldInverse).z > -camera.near) return null;
    v.project(camera);
    const x = ((v.x + 1) / 2) * w;
    const y = ((1 - v.y) / 2) * h;
    r.x0 = Math.min(r.x0, x);
    r.y0 = Math.min(r.y0, y);
    r.x1 = Math.max(r.x1, x);
    r.y1 = Math.max(r.y1, y);
  }
  return r;
}

/** True when at least half of the object's screen bounds lie inside the stroke rectangle. */
export function rectHits(obj: Rect, stroke: Rect): boolean {
  const ow = Math.min(obj.x1, stroke.x1) - Math.max(obj.x0, stroke.x0);
  const oh = Math.min(obj.y1, stroke.y1) - Math.max(obj.y0, stroke.y0);
  if (ow <= 0 || oh <= 0) return false;
  const area = Math.max((obj.x1 - obj.x0) * (obj.y1 - obj.y0), 1e-6);
  return (ow * oh) / area >= OVERLAP_TO_HIT;
}

/**
 * Camera pose that makes the screen rectangle `r` fill the viewport: the new target is the rectangle centre
 * projected onto the camera-facing plane through `target`; the distance shrinks by the rectangle/viewport ratio.
 */
export function regionGoal(r: Rect, camera: THREE.PerspectiveCamera, target: THREE.Vector3, w: number, h: number, minD: number, maxD: number): CamGoal {
  const view = target.clone().sub(camera.position);
  const dist = view.length();
  const fwd = view.clone().normalize();
  const ndc = new THREE.Vector3((((r.x0 + r.x1) / 2) / w) * 2 - 1, -(((r.y0 + r.y1) / 2) / h) * 2 + 1, 0.5);
  const ray = ndc.unproject(camera).sub(camera.position).normalize();
  const look = camera.position.clone().add(ray.multiplyScalar(dist / ray.dot(fwd)));
  const scale = Math.min(1, Math.max(MIN_ZOOM_SCALE, Math.max((r.x1 - r.x0) / w, (r.y1 - r.y0) / h) * 1.05));
  const newDist = THREE.MathUtils.clamp(dist * scale, minD, maxD);
  return { pos: look.clone().sub(fwd.multiplyScalar(newDist)), look };
}
