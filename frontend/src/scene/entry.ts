// frontend/src/scene/entry.ts
import * as THREE from "three";
import type { Anim, Obj } from "./types";
import { DEFAULT_COLOR, vec3 } from "./kinds/util";

/**
 * Runtime state of one scene object. Hierarchy: node (base transform) > inner (animation layer) > content + children.
 * pos/rot/scale/color hold the logical (possibly tweened) values; node transforms are derived from them.
 */
export interface Entry {
  obj: Obj;
  node: THREE.Group;
  inner: THREE.Group;
  content: THREE.Object3D;
  pos: THREE.Vector3;
  /** explode offset, added to pos */
  ex: THREE.Vector3;
  rot: THREE.Vector3;
  scale: THREE.Vector3;
  color: THREE.Color;
  anims: Anim[];
  tint: boolean;
}

export function toScale(s: Obj["scale"]): THREE.Vector3 {
  if (typeof s === "number") return new THREE.Vector3(s, s, s);
  return new THREE.Vector3(...vec3(s, [1, 1, 1]));
}

export function toAnims(a: Obj["anim"]): Anim[] {
  if (!a) return [];
  return (Array.isArray(a) ? a : [a]).filter((x) => x && typeof x.type === "string");
}

export function baseColor(o: Obj): THREE.Color {
  return new THREE.Color(o.color ?? DEFAULT_COLOR);
}

/** Recolors the line/mesh materials of an entry's content (not its children, not text sprites). */
export function tintContent(e: Entry): void {
  if (!e.tint) return;
  e.content.traverse((m) => {
    if ((m as THREE.Sprite).isSprite) return;
    const mat = (m as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (mat && "color" in mat && !(mat as THREE.Material & { vertexColors?: boolean }).vertexColors) mat.color.copy(e.color);
  });
}

export function disposeTree(root: THREE.Object3D): void {
  root.traverse((m) => {
    const mesh = m as THREE.Mesh;
    mesh.geometry?.dispose();
    const mats = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
    for (const mat of mats) {
      (mat as THREE.SpriteMaterial).map?.dispose();
      mat.dispose();
    }
  });
}
