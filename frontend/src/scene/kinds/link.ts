// frontend/src/scene/kinds/link.ts
import * as THREE from "three";
import type { Kind } from "../types";
import { DOTS, SAMPLES, curveAt, curvePoints, flowAt, trim, type V3 } from "./link_math";
import { DEFAULT_COLOR } from "./util";

const TILE_RADIUS = 1.5; // line starts this far from an endpoint centre, at the tile edge

/** Glowing curve between two objects (`from`, `to` are object ids). The player repositions it every frame (see follow.ts). */
export const LINK: Kind = {
  tint: false,
  build: (o) => {
    const color = new THREE.Color(String(o.color ?? DEFAULT_COLOR));
    const g = new THREE.Group();
    const dashed = o.style === "dashed";
    const mat = dashed
      ? new THREE.LineDashedMaterial({ color, dashSize: 0.25, gapSize: 0.15, transparent: true, opacity: 0.9 })
      : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 });
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(new Array(SAMPLES + 1).fill(new THREE.Vector3())), mat);
    line.frustumCulled = false;
    const dots = new THREE.Points(
      new THREE.BufferGeometry().setFromPoints(new Array(DOTS).fill(new THREE.Vector3())),
      new THREE.PointsMaterial({ color, size: 0.16, transparent: true, depthWrite: false }),
    );
    dots.frustumCulled = false;
    const head = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.28, 12), new THREE.MeshBasicMaterial({ color }));
    g.add(line, dots, head);
    g.userData.link = { line, dots, head, dashed };
    return g;
  },
};

interface Parts { line: THREE.Line; dots: THREE.Points; head: THREE.Mesh; dashed: boolean }

/** Re-shapes a built link for the current endpoint world positions and time `t` (seconds). */
export function updateLink(content: THREE.Object3D, from: V3, to: V3, t: number): void {
  const p = content.userData.link as Parts | undefined;
  if (!p) return;
  const [a, b] = trim(from, to, TILE_RADIUS);
  const pts = curvePoints(a, b);
  p.line.geometry.setFromPoints(pts.map((v) => new THREE.Vector3(...v)));
  if (p.dashed) p.line.computeLineDistances();
  const pos = p.dots.geometry.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < DOTS; i++) {
    const v = curveAt(a, b, flowAt(i, DOTS, t));
    pos.setXYZ(i, ...v);
  }
  pos.needsUpdate = true;
  const tip = curveAt(a, b, 1);
  const back = curveAt(a, b, 0.96);
  p.head.position.set(...tip);
  p.head.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    new THREE.Vector3(tip[0] - back[0], tip[1] - back[1], tip[2] - back[2]).normalize(),
  );
}
