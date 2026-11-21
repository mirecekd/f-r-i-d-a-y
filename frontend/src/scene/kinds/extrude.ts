// frontend/src/scene/kinds/extrude.ts
import * as THREE from "three";
import type { Kind } from "../types";
import { colorOf, holo, list, num } from "./util";

/**
 * 2D plan -> 3D. Plan (x, y) maps to world (x, z); walls stand on y=0.
 * `walls`: [[x1,y1,x2,y2],...] with `thickness`; or `outline`: [[x,y],...] polygon extruded by `height`.
 */
export const EXTRUDE: Kind = {
  tint: true,
  build: (o) => {
    const height = num(o.height, 2.5);
    const thick = num(o.thickness, 0.2);
    const color = colorOf(o);
    const g = new THREE.Group();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    const grow = (x: number, y: number): void => {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    };
    for (const w of list(o.walls)) {
      const [x1, y1, x2, y2] = list(w).map((v) => num(v, 0));
      const len = Math.hypot(x2 - x1, y2 - y1);
      if (len < 1e-6) continue;
      grow(x1, y1); grow(x2, y2);
      const wall = holo(new THREE.BoxGeometry(len + thick, height, thick), color, 0.3);
      wall.position.set((x1 + x2) / 2, height / 2, (y1 + y2) / 2);
      wall.rotation.y = -Math.atan2(y2 - y1, x2 - x1);
      g.add(wall);
    }
    const outline = list(o.outline).map((p) => [num(list(p)[0], 0), num(list(p)[1], 0)]);
    if (outline.length >= 3) {
      const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, -y)));
      const geom = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
      geom.rotateX(-Math.PI / 2);
      g.add(holo(geom, color, 0.3));
      outline.forEach(([x, y]) => grow(x, y));
    }
    if (o.floor !== false && maxX > minX && maxY > minY) {
      const pad = thick;
      const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(maxX - minX + pad * 2, maxY - minY + pad * 2),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }),
      );
      floor.rotation.x = -Math.PI / 2;
      floor.position.set((minX + maxX) / 2, 0.01, (minY + maxY) / 2);
      g.add(floor);
    }
    return g;
  },
};
