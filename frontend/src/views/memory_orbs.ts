// frontend/src/views/memory_orbs.ts
import * as THREE from "three";

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

/** Per-node three.js parts that hover/search highlighting changes. */
export interface OrbParts {
  core: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  glow: THREE.Sprite;
  label?: THREE.Sprite;
  radius: number;
}

const sphere = new THREE.SphereGeometry(1, 20, 14);
const glowTextures = new Map<string, THREE.CanvasTexture>();
const noRaycast = () => {};

/** Soft radial gradient, bright white-hot centre fading to the kind colour and then to nothing. */
function glowTexture(color: string): THREE.CanvasTexture {
  let t = glowTextures.get(color);
  if (t) return t;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.16, color);
  grad.addColorStop(0.4, color + "66");
  grad.addColorStop(1, color + "00");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  glowTextures.set(color, t);
  return t;
}

export function nodeRadius(n: MemNode): number {
  const w = Math.max(0, Math.min(1, Number(n.weight) || 0));
  return (2.2 + w * 5.5) * (n.kind === "project" ? 1.5 : 1);
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
  return sp;
}

export function disposeLabel(parts: OrbParts): void {
  if (!parts.label) return;
  parts.label.parent?.remove(parts.label);
  (parts.label.material.map as THREE.Texture | null)?.dispose();
  parts.label.material.dispose();
  parts.label = undefined;
}

/** Glowing orb: tinted core sphere plus an additive halo sprite; the group carries OrbParts in userData. */
export function buildOrb(n: MemNode, withLabel: boolean): THREE.Group {
  const color = KIND_COLOR[n.kind] ?? "#ffffff";
  const radius = nodeRadius(n);
  const group = new THREE.Group();
  const core = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ color: new THREE.Color(color).lerp(new THREE.Color("#ffffff"), 0.18), transparent: true }));
  core.scale.setScalar(radius);
  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: glowTexture(color), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }),
  );
  glow.scale.setScalar(radius * 6);
  glow.raycast = noRaycast;
  group.add(glow, core);
  const parts: OrbParts = { core, glow, radius };
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

/** 0 = hidden-looking, 1 = full: fades core and halo together. */
export function setOrbLevel(parts: OrbParts, level: number): void {
  parts.core.material.opacity = 0.25 + 0.75 * level;
  parts.glow.material.opacity = level;
  if (parts.label) parts.label.material.opacity = level;
}
