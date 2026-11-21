// frontend/src/scene/kinds/surface.ts
import * as THREE from "three";
import type { Kind, Obj } from "../types";
import { colorOf, list, num } from "./util";

const MATH_FUNCS: Record<string, (...a: number[]) => number> = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, abs: Math.abs, sqrt: Math.sqrt, pow: Math.pow, exp: Math.exp,
  log: Math.log, min: Math.min, max: Math.max, atan2: Math.atan2, floor: Math.floor, ceil: Math.ceil,
  sign: Math.sign, hypot: Math.hypot, atan: Math.atan,
};
const FUNCS = Object.keys(MATH_FUNCS);
const CONSTS: Record<string, number> = { PI: Math.PI, E: Math.E };

/** Compiles a restricted math expression in x and z (e.g. "sin(x)*cos(z)"). Returns null if it is not safe. */
export function compileExpr(src: string): ((x: number, z: number) => number) | null {
  if (src.length > 300 || !/^[0-9A-Za-z_+\-*/%^().,\s]*$/.test(src)) return null;
  const ids = src.match(/[A-Za-z_][A-Za-z_0-9]*/g) ?? [];
  if (ids.some((i) => i !== "x" && i !== "z" && !FUNCS.includes(i) && !(i in CONSTS))) return null;
  try {
    const f = new Function("x", "z", ...FUNCS, ...Object.keys(CONSTS), `"use strict"; return (${src.replace(/\^/g, "**")});`);
    const fns = FUNCS.map((n) => MATH_FUNCS[n]);
    return (x, z) => Number(f(x, z, ...fns, ...Object.values(CONSTS)));
  } catch {
    return null;
  }
}

function heights(o: Obj): { rows: number; cols: number; h: number[] } {
  const data = list(o.data).map((r) => list(r).map((v) => num(v, 0)));
  if (data.length > 1 && data[0].length > 1) {
    const cols = data[0].length;
    return { rows: data.length, cols, h: data.flatMap((r) => Array.from({ length: cols }, (_, i) => r[i] ?? 0)) };
  }
  const res = Math.min(Math.max(Math.floor(num(o.res, 40)), 2), 128);
  const [x0, x1] = list(o.range).length >= 2 ? [num(list(o.range)[0], -3), num(list(o.range)[1], 3)] : [-3, 3];
  const fn = compileExpr(String(o.fn ?? "sin(x)*cos(z)")) ?? (() => 0);
  const h: number[] = [];
  for (let r = 0; r < res; r++)
    for (let c = 0; c < res; c++) {
      const v = fn(x0 + ((x1 - x0) * c) / (res - 1), x0 + ((x1 - x0) * r) / (res - 1));
      h.push(Number.isFinite(v) ? v : 0);
    }
  return { rows: res, cols: res, h };
}

/** Heightmap from a 2D `data` array or an expression `fn` of x,z. Footprint `size` [w,d], max height `height`. */
export const SURFACE: Kind = {
  tint: false,
  build: (o) => {
    const { rows, cols, h } = heights(o);
    const size = list(o.size).length >= 2 ? [num(list(o.size)[0], 6), num(list(o.size)[1], 6)] : [6, 6];
    const lo = Math.min(...h);
    const span = Math.max(Math.max(...h) - lo, 1e-9);
    const amp = num(o.height, 2);
    const geom = new THREE.PlaneGeometry(size[0], size[1], cols - 1, rows - 1);
    geom.rotateX(-Math.PI / 2);
    const pos = geom.getAttribute("position");
    const lowC = colorOf(o);
    const highC = new THREE.Color(typeof o.color2 === "string" ? o.color2 : "#ff7ad9");
    const colors = new Float32Array(pos.count * 3);
    const c = new THREE.Color();
    for (let i = 0; i < pos.count; i++) {
      const u = (h[i] - lo) / span;
      pos.setY(i, u * amp);
      c.copy(lowC).lerp(highC, u);
      colors.set([c.r, c.g, c.b], i * 3);
    }
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geom.computeVertexNormals();
    const g = new THREE.Group();
    g.add(
      new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ vertexColors: true, transparent: true, opacity: 0.4, side: THREE.DoubleSide, roughness: 0.4 })),
      new THREE.LineSegments(new THREE.WireframeGeometry(geom), new THREE.LineBasicMaterial({ color: lowC.clone().lerp(highC, 0.4), transparent: true, opacity: 0.55 })),
    );
    return g;
  },
};
