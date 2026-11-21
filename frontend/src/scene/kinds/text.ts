// frontend/src/scene/kinds/text.ts
import * as THREE from "three";
import type { Kind, Obj } from "../types";
import { DEFAULT_COLOR, num } from "./util";

/** Labels never render smaller than this many CSS pixels tall, so far-away text stays legible. */
const MIN_PX = 14;
const wp = new THREE.Vector3();
const ws = new THREE.Vector3();
const sz = new THREE.Vector2();

export interface TextSprite extends THREE.Sprite {
  userData: { aspect: number };
}

/** Canvas-texture sprite that always faces the camera. `height` is the world height of one line block. */
export function makeTextSprite(text: string, color: string, height: number, pill = false): TextSprite {
  const lines = text.split("\n").slice(0, 8);
  const px = 64;
  const font = `600 ${px}px "Segoe UI", "DejaVu Sans", sans-serif`;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  ctx.font = font;
  const pad = pill ? 28 : 12;
  const w = Math.ceil(Math.max(...lines.map((l) => ctx.measureText(l).width), px / 2)) + pad * 2;
  const h = Math.ceil(px * 1.25 * lines.length) + pad * 2;
  canvas.width = w;
  canvas.height = h;
  ctx.font = font;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  if (pill) {
    ctx.fillStyle = "rgba(4,16,28,0.78)";
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.roundRect(3, 3, w - 6, h - 6, 24);
    ctx.fill();
    ctx.stroke();
  }
  ctx.fillStyle = pill ? "#e8fbff" : color;
  lines.forEach((l, i) => ctx.fillText(l, w / 2, pad + px * 0.625 + i * px * 1.25));
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false });
  const s = new THREE.Sprite(mat) as TextSprite;
  s.renderOrder = 20;
  s.userData.aspect = w / h;
  const base = new THREE.Vector3(height * (w / h), height, 1);
  s.scale.copy(base);
  s.onBeforeRender = (renderer, _scene, camera) => {
    s.scale.copy(base);
    s.updateWorldMatrix(true, false);
    const cam = camera as THREE.PerspectiveCamera;
    if (!cam.isPerspectiveCamera) return;
    s.matrixWorld.decompose(wp, new THREE.Quaternion(), ws);
    const dist = Math.max(0.01, wp.distanceTo(cam.position));
    const px = (ws.y * renderer.getSize(sz).y) / (2 * dist * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)));
    if (px >= MIN_PX) return;
    s.scale.multiplyScalar(MIN_PX / Math.max(px, 0.01));
    s.updateWorldMatrix(false, false);
  };
  return s;
}

function text(o: Obj, pill: boolean): THREE.Object3D {
  const lines = String(o.text ?? "").split("\n").slice(0, 8).length;
  const size = num(o.size, 0.5);
  return makeTextSprite(String(o.text ?? ""), o.color ?? DEFAULT_COLOR, size * lines, pill);
}

export const TEXT: Kind = { tint: false, build: (o) => text(o, false) };
/** Anchored to `target` by the player; drawn as a framed tag. */
export const LABEL: Kind = { tint: false, build: (o) => text(o, true) };
