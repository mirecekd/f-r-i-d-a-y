// frontend/src/scene/kinds/lines.ts
import * as THREE from "three";
import type { Kind, Obj, Vec3 } from "../types";
import { colorOf, list, num, vec3 } from "./util";

function lineFrom(points: Vec3[], o: Obj, loop = false): THREE.Line {
  const geom = new THREE.BufferGeometry().setFromPoints(points.map((p) => new THREE.Vector3(...p)));
  const mat = new THREE.LineBasicMaterial({ color: colorOf(o), transparent: true, opacity: 0.95 });
  return loop ? new THREE.LineLoop(geom, mat) : new THREE.Line(geom, mat);
}

export const LINE: Kind = { tint: true, build: (o) => lineFrom([vec3(o.from), vec3(o.to)], o) };

export const POLYLINE: Kind = {
  tint: true,
  build: (o) => lineFrom(list(o.pts).map((p) => vec3(p)), o, o.closed === true),
};

export const ARROW: Kind = {
  tint: true,
  build: (o) => {
    const a = new THREE.Vector3(...vec3(o.from));
    const b = new THREE.Vector3(...vec3(o.to));
    const dir = b.clone().sub(a);
    const len = dir.length();
    const g = new THREE.Group();
    if (len < 1e-6) return g;
    const head = Math.min(num(o.head, 0.3), len * 0.6);
    dir.normalize();
    const base = b.clone().addScaledVector(dir, -head);
    g.add(lineFrom([[a.x, a.y, a.z], [base.x, base.y, base.z]], o));
    const mat = new THREE.MeshBasicMaterial({ color: colorOf(o) });
    const cone = new THREE.Mesh(new THREE.ConeGeometry(head * 0.35, head, 16), mat);
    cone.position.copy(base).addScaledVector(dir, head / 2);
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    g.add(cone);
    return g;
  },
};
