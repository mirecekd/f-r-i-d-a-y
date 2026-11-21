// frontend/src/scene/anim.ts
import * as THREE from "three";
import type { Entry } from "./entry";
import type { Anim } from "./types";

const AXES = { x: 0, y: 1, z: 2 } as const;

function offsetOnCircle(axis: Anim["axis"], a: number, r: number): [number, number, number] {
  const c = Math.cos(a) * r;
  const s = Math.sin(a) * r;
  if (axis === "x") return [0, c, s];
  if (axis === "z") return [c, s, 0];
  return [c, 0, s];
}

/** Applies spin / bob / pulse / orbit to the animation layer (inner) of an entry at time t (seconds). */
export function applyAnims(e: Entry, t: number): void {
  const inner = e.inner;
  inner.position.set(0, 0, 0);
  inner.rotation.set(0, 0, 0);
  inner.scale.set(1, 1, 1);
  for (const a of e.anims) {
    const speed = a.speed ?? 1;
    const axis = a.axis ?? "y";
    if (a.type === "spin") {
      inner.rotation[axis] += t * speed;
    } else if (a.type === "bob") {
      inner.position.setComponent(AXES[axis], inner.position.getComponent(AXES[axis]) + Math.sin(t * speed * 2) * (a.amp ?? 0.25));
    } else if (a.type === "pulse") {
      inner.scale.multiplyScalar(1 + Math.sin(t * speed * 2) * (a.amp ?? 0.12));
    } else if (a.type === "orbit") {
      const [x, y, z] = offsetOnCircle(axis, t * speed, a.amp ?? 1);
      inner.position.add(new THREE.Vector3(x, y, z));
    }
  }
}
