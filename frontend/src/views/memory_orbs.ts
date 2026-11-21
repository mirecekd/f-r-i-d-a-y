// frontend/src/views/memory_orbs.ts
import * as THREE from "three";
import { clampOnScreen } from "./memory_label_clamp";
import { glyphCanvas, glyphFor } from "./memory_glyphs";

export type Kind = "project" | "session" | "memory" | "concept" | "file";
export const KINDS_ORDER: Kind[] = ["project", "session", "memory", "concept", "file"];

export interface MemNode {
  id: string;
  label: string;
  kind: Kind;
  weight: number;
  ts: number;
  project: string;
  x?: number;
  y?: number;
  z?: number;
}
export interface MemLink {
  source: string | MemNode;
  target: string | MemNode;
  kind: string;
  weight: number;
}

export const KIND_COLOR: Record<Kind, string> = {
  project: "#ffb347",
  session: "#4fd8ff",
  memory: "#b98cff",
  concept: "#3dffa0",
  file: "#ff7a9c",
};

/** Per-node three.js parts that hover/search highlighting changes. `core` is the glyph sprite; `hit` the invisible click target. */
export interface OrbParts {
  core: THREE.Sprite;
  glow?: THREE.Sprite;
  ring?: THREE.Sprite;
  hit: THREE.Mesh;
  label?: THREE.Sprite;
  radius: number;
}

const sphere = new THREE.SphereGeometry(1, 8, 6);
const hitMaterial = new THREE.MeshBasicMaterial({ visible: false });
const glowTextures = new Map<string, THREE.CanvasTexture>();
const glyphTextures = new Map<string, THREE.CanvasTexture>();
let ringTexture: THREE.CanvasTexture | undefined;
const noRaycast = () => {};

const canvasTexture = (c: HTMLCanvasElement): THREE.CanvasTexture => {
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
};

/** Small soft halo: tinted centre fading to nothing quickly. */
function glowTexture(color: string): THREE.CanvasTexture {
  let t = glowTextures.get(color);
  if (t) return t;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, color + "99");
  grad.addColorStop(0.5, color + "33");
  grad.addColorStop(1, color + "00");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  t = canvasTexture(c);
  glowTextures.set(color, t);
  return t;
}

function ringMap(): THREE.CanvasTexture {
  if (ringTexture) return ringTexture;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  g.strokeStyle = "#ffffff";
  g.lineWidth = 3;
  g.beginPath();
  g.arc(32, 32, 29, 0, 7);
  g.stroke();
  ringTexture = canvasTexture(c);
  return ringTexture;
}

function glyphTexture(n: MemNode, color: string): THREE.CanvasTexture {
  const name = glyphFor(n.kind, n.label);
  const key = `${name}|${color}`;
  let t = glyphTextures.get(key);
  if (!t) { t = canvasTexture(glyphCanvas(name, color)); glyphTextures.set(key, t); }
  return t;
}

/** Half-size of the glyph disc in world units (about 60% of the former blob radius, floored so glyphs stay readable). */
export function nodeRadius(n: MemNode): number {
  const w = Math.max(0, Math.min(1, Number(n.weight)) || 0);
  return Math.max(3.4, (2.2 + w * 5.5) * 0.8) * (n.kind === "project" ? 1.4 : 1);
}

/** Text label drawn to a canvas (textContent-equivalent: canvas text is never parsed as markup). */
export function labelSprite(text: string, color: string, radius: number): THREE.Sprite {
  const label = text.length > 28 ? text.slice(0, 27) + "\u2026" : text;
  const c = document.createElement("canvas");
  const g = c.getContext("2d")!;
  const font = "600 34px Rajdhani, system-ui, sans-serif";
  g.font = font;
  c.width = Math.ceil(g.measureText(label).width) + 24;
  c.height = 52;
  g.font = font;
  g.textBaseline = "middle";
  g.lineWidth = 7;
  g.strokeStyle = "rgba(2,6,12,.9)";
  g.strokeText(label, 12, 27);
  g.fillStyle = color;
  g.shadowColor = color;
  g.shadowBlur = 8;
  g.fillText(label, 12, 27);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
  const h = 4.6;
  sp.scale.set((h * c.width) / c.height, h, 1);
  sp.position.set(0, -(radius + 4), 0);
  sp.renderOrder = 5;
  sp.raycast = noRaycast;
  clampOnScreen(sp, (h * c.width) / c.height, h);
  return sp;
}

export function disposeLabel(parts: OrbParts): void {
  if (!parts.label) return;
  parts.label.parent?.remove(parts.label);
  (parts.label.material.map as THREE.Texture | null)?.dispose();
  parts.label.material.dispose();
  parts.label = undefined;
}

/** Glyph node: a crisp glyph sprite, a small additive halo (omitted when `heavy`) and an invisible, larger hit sphere. */
export function buildOrb(n: MemNode, withLabel: boolean, heavy = false): THREE.Group {
  const color = KIND_COLOR[n.kind] ?? "#ffffff";
  const radius = nodeRadius(n);
  const group = new THREE.Group();
  const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: glyphTexture(n, color), transparent: true, depthWrite: false }));
  core.scale.setScalar(radius * 2);
  core.raycast = noRaycast;
  const hit = new THREE.Mesh(sphere, hitMaterial);
  hit.scale.setScalar(radius * 1.25);
  group.add(hit, core);
  const parts: OrbParts = { core, hit, radius };
  if (!heavy) {
    parts.glow = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: glowTexture(color), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: 0.55 }),
    );
    parts.glow.scale.setScalar(radius * 3);
    parts.glow.raycast = noRaycast;
    group.add(parts.glow);
  }
  if (withLabel) {
    parts.label = labelSprite(n.label, color, radius);
    group.add(parts.label);
  }
  group.userData = parts;
  return group;
}

export function partsOf(group: THREE.Object3D | undefined): OrbParts | undefined {
  return group?.userData as OrbParts | undefined;
}

/** 1 = full, lower = receded (never below 0.3 so every node stays readable); fades glyph, halo and label together. */
export function setOrbLevel(parts: OrbParts, level: number): void {
  parts.core.material.opacity = level;
  if (parts.glow) parts.glow.material.opacity = 0.55 * level;
  if (parts.label) parts.label.material.opacity = level;
}

/** Hovered or selected node: drawn about 25% larger with a thin white ring. */
export function setOrbEmphasis(parts: OrbParts, on: boolean): void {
  parts.core.scale.setScalar(parts.radius * (on ? 2.5 : 2));
  if (on && !parts.ring) {
    parts.ring = new THREE.Sprite(new THREE.SpriteMaterial({ map: ringMap(), transparent: true, depthWrite: false, opacity: 0.9 }));
    parts.ring.raycast = noRaycast;
    parts.hit.parent?.add(parts.ring);
  }
  if (parts.ring) { parts.ring.visible = on; parts.ring.scale.setScalar(parts.radius * 2.7); }
}
