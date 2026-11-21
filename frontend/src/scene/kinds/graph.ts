// frontend/src/scene/kinds/graph.ts
import * as THREE from "three";
import type { Kind, Obj, Vec3 } from "../types";
import { DEFAULT_COLOR, list, num, vec3 } from "./util";
import { makeTextSprite } from "./text";

interface GNode {
  id: string;
  pos: Vec3;
  color: string;
  size: number;
  label: string;
}

function readNodes(o: Obj): GNode[] {
  const raw = list(o.nodes) as Record<string, unknown>[];
  const base = o.color ?? DEFAULT_COLOR;
  return raw.map((n, i) => {
    const ring = (i / Math.max(raw.length, 1)) * Math.PI * 2;
    const r = Math.max(2, raw.length * 0.4);
    return {
      id: String(n.id ?? i),
      pos: Array.isArray(n.pos) ? vec3(n.pos) : [Math.cos(ring) * r, 0, Math.sin(ring) * r],
      color: String(n.color ?? base),
      size: num(n.size, num(o.node_size, 0.5)),
      label: String(n.label ?? n.id ?? ""),
    };
  });
}

/** Nodes are glowing spheres at the given positions; edges are [from, to] id pairs or {from, to, color}. */
export const GRAPH: Kind = {
  tint: false,
  build: (o) => {
    const g = new THREE.Group();
    const nodes = readNodes(o);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    for (const n of nodes) {
      const core = new THREE.Mesh(
        new THREE.SphereGeometry(n.size / 2, 24, 16),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(n.color).multiplyScalar(1.4) }),
      );
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(n.size * 0.8, 24, 16),
        new THREE.MeshBasicMaterial({ color: n.color, transparent: true, opacity: 0.16, depthWrite: false }),
      );
      core.position.set(...n.pos);
      halo.position.set(...n.pos);
      g.add(core, halo);
      if (n.label) {
        const t = makeTextSprite(n.label, "#dff9ff", 0.34, true);
        t.position.set(n.pos[0], n.pos[1] + n.size * 0.9 + 0.3, n.pos[2]);
        g.add(t);
      }
    }
    const verts: number[] = [];
    const colors: number[] = [];
    const tmp = new THREE.Color();
    for (const e of list(o.edges)) {
      const [fa, ta] = Array.isArray(e) ? [e[0], e[1]] : [(e as Obj).from, (e as Obj).to];
      const a = byId.get(String(fa));
      const b = byId.get(String(ta));
      if (!a || !b) continue;
      tmp.set(a.color);
      verts.push(...a.pos, ...b.pos);
      colors.push(tmp.r, tmp.g, tmp.b);
      tmp.set(b.color);
      colors.push(tmp.r, tmp.g, tmp.b);
      if (o.directed === true) {
        const dir = new THREE.Vector3(...b.pos).sub(new THREE.Vector3(...a.pos));
        const len = dir.length();
        if (len > b.size + 0.4) {
          dir.normalize();
          const tip = new THREE.Vector3(...b.pos).addScaledVector(dir, -(b.size / 2 + 0.05));
          const cone = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.3, 12), new THREE.MeshBasicMaterial({ color: b.color }));
          cone.position.copy(tip).addScaledVector(dir, -0.15);
          cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
          g.add(cone);
        }
      }
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    geom.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    g.add(new THREE.LineSegments(geom, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.8 })));
    return g;
  },
};
