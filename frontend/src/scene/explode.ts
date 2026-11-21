// frontend/src/scene/explode.ts
import * as THREE from "three";
import type { Entry } from "./entry";

/**
 * Exploded-view offsets. Top-level objects move away from the centroid of all top-level objects;
 * children move away from their parent's origin (in the parent's local frame). Factor 0 gives zero offsets.
 */
export function explodeOffsets(entries: Iterable<Entry>, factor: number): Map<Entry, THREE.Vector3> {
  const all = [...entries];
  const top = all.filter((e) => !e.obj.parent);
  const centre = new THREE.Vector3();
  top.forEach((e) => centre.add(e.pos));
  if (top.length) centre.divideScalar(top.length);
  const out = new Map<Entry, THREE.Vector3>();
  for (const e of all) {
    const from = e.obj.parent ? new THREE.Vector3() : centre;
    out.set(e, e.pos.clone().sub(from).multiplyScalar(factor));
  }
  return out;
}
