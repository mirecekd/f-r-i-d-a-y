// frontend/src/scene/types.ts
import type * as THREE from "three";

export type Vec3 = [number, number, number];

export interface Anim {
  type: "spin" | "bob" | "pulse" | "orbit";
  speed?: number;
  axis?: "x" | "y" | "z";
  amp?: number;
}

export interface Obj {
  id: string;
  kind: string;
  pos?: Vec3;
  rot?: Vec3;
  scale?: number | Vec3;
  color?: string;
  label?: string;
  parent?: string;
  opacity?: number;
  visible?: boolean;
  anim?: Anim | Anim[] | null;
  [k: string]: unknown;
}

export type Op =
  | { op: "add"; obj: Obj }
  | { op: "set"; id: string; props: Partial<Obj>; ms?: number }
  | { op: "del"; id: string }
  | { op: "clear" }
  | { op: "camera"; pos: Vec3; look?: Vec3 }
  | { op: "explode"; factor: number };

/** A scene kind: builds the visible content of one object. `tint` kinds recolor live via material.color. */
export interface Kind {
  build: (o: Obj) => THREE.Object3D;
  tint: boolean;
}
