// frontend/src/scene/kinds/util.ts
import * as THREE from "three";
import type { Obj, Vec3 } from "../types";

export const DEFAULT_COLOR = "#4fd8ff";

export function num(v: unknown, d: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : d;
}

export function vec3(v: unknown, d: Vec3 = [0, 0, 0]): Vec3 {
  return Array.isArray(v) && v.length >= 3 ? [num(v[0], 0), num(v[1], 0), num(v[2], 0)] : d;
}

export function list(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

export function colorOf(o: Obj): THREE.Color {
  return new THREE.Color(o.color ?? DEFAULT_COLOR);
}

/** Holographic solid: translucent fill plus bright edge outline. */
export function holo(geom: THREE.BufferGeometry, color: THREE.ColorRepresentation, opacity = 0.25): THREE.Group {
  const c = new THREE.Color(color);
  const g = new THREE.Group();
  g.add(
    new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: c, transparent: true, opacity, roughness: 0.3 })),
    new THREE.LineSegments(
      new THREE.EdgesGeometry(geom),
      new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.95 }),
    ),
  );
  return g;
}

/** Seeded PRNG (mulberry32) so generated clouds are reproducible. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function lineSegments(pairs: Vec3[], color: THREE.ColorRepresentation, opacity = 0.9): THREE.LineSegments {
  const geom = new THREE.BufferGeometry().setFromPoints(pairs.map((p) => new THREE.Vector3(...p)));
  return new THREE.LineSegments(geom, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
}
