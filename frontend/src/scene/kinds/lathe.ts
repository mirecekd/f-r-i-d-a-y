// frontend/src/scene/kinds/lathe.ts
import * as THREE from "three";
import type { Kind } from "../types";
import { colorOf, holo } from "./util";
import { capProfile, lathePoints, latheSegments } from "./lathe_logic";

/**
 * Surface of revolution: `profile` [[r, y], ...] turned around the y axis (vases, bottles, bowls, wheels).
 * `segments` (3..96, 32) sets the facets, `cap` (true) closes both ends against the axis.
 */
export const LATHE: Kind = {
  tint: true,
  build: (o) => {
    const pts = capProfile(lathePoints(o.profile), o.cap !== false);
    const g = new THREE.Group();
    if (pts.length < 2) return g;
    const geom = new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), latheSegments(o.segments));
    const solid = holo(geom, colorOf(o), 0.3);
    solid.traverse((node: THREE.Object3D) => {
      const mesh = node as THREE.Mesh;
      if (mesh.isMesh) (mesh.material as THREE.Material).side = THREE.DoubleSide;
    });
    g.add(solid);
    return g;
  },
};
