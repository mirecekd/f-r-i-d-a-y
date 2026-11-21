// frontend/src/scene/follow.ts
import * as THREE from "three";
import type { Entry } from "./entry";

const box = new THREE.Box3();
const top = new THREE.Vector3();

/** Places `label` objects with a `target` above the world-space bounding box of that target (plus `offset`). */
export function followTargets(entries: Iterable<Entry>, find: (id: string) => Entry | undefined): void {
  for (const e of entries) {
    const targetId = e.obj.kind === "label" ? e.obj.target : undefined;
    if (typeof targetId !== "string") continue;
    const t = find(targetId);
    if (!t) continue;
    box.setFromObject(t.node);
    if (box.isEmpty()) continue;
    box.getCenter(top);
    top.y = box.max.y + 0.4;
    const off = Array.isArray(e.obj.offset) ? e.obj.offset : [0, 0, 0];
    e.node.position.set(top.x + Number(off[0] ?? 0), top.y + Number(off[1] ?? 0), top.z + Number(off[2] ?? 0));
  }
}
