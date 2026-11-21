// frontend/src/scene/kinds/primitives.ts
import * as THREE from "three";
import type { Kind } from "../types";
import { colorOf, holo, num } from "./util";

const GEOS: Record<string, () => THREE.BufferGeometry> = {
  box: () => new THREE.BoxGeometry(1, 1, 1),
  sphere: () => new THREE.SphereGeometry(0.5, 32, 24),
  cylinder: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 32),
  cone: () => new THREE.ConeGeometry(0.5, 1, 32),
  torus: () => new THREE.TorusGeometry(0.5, 0.15, 16, 48),
  plane: () => new THREE.PlaneGeometry(1, 1),
};

export const PRIMITIVES: Record<string, Kind> = Object.fromEntries(
  Object.entries(GEOS).map(([name, make]) => [
    name,
    { tint: true, build: (o) => holo(make(), colorOf(o), num(o.opacity, 0.25)) } satisfies Kind,
  ]),
);

export const GROUP: Kind = { tint: true, build: () => new THREE.Group() };
