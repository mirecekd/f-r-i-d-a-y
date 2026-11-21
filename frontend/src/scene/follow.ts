// frontend/src/scene/follow.ts
import * as THREE from "three";
import type { Entry } from "./entry";
import { updateLink } from "./kinds/link";
import { linkVisible } from "./kinds/link_math";

const box = new THREE.Box3();
const top = new THREE.Vector3();

/** Places `label` objects with a `target` above the world-space bounding box of that target (plus `offset`). */
export function followTargets(entries: Iterable<Entry>, find: (id: string) => Entry | undefined, time = 0): void {
  for (const e of entries) {
    if (e.obj.kind === "link") {
      followLink(e, find, time);
      continue;
    }
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

const pa = new THREE.Vector3();
const pb = new THREE.Vector3();

/** A `link` object follows the world positions of its `from` and `to` objects every frame; hidden while one is missing. */
function followLink(e: Entry, find: (id: string) => Entry | undefined, t: number): void {
  const a = find(String(e.obj.from));
  const b = find(String(e.obj.to));
  const show = linkVisible(!!a, !!b, e.obj.visible);
  e.node.visible = show;
  if (!a || !b || !show) return;
  a.node.getWorldPosition(pa);
  b.node.getWorldPosition(pb);
  updateLink(e.content, [pa.x, pa.y, pa.z], [pb.x, pb.y, pb.z], t);
}
