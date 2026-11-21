// frontend/src/scene/kinds/particles.ts
import * as THREE from "three";
import type { Kind, Obj, Vec3 } from "../types";
import { DEFAULT_COLOR, list, num, rng, vec3 } from "./util";

const MAX_POINTS = 20000;

/** Generates points for gen = spiral | galaxy | grid | sphere | random. */
function generate(o: Obj): Vec3[] {
  const gen = String(o.gen ?? "random");
  const count = Math.min(Math.max(1, Math.floor(num(o.count, 1500))), MAX_POINTS);
  const radius = num(o.radius, 3);
  const rand = rng(num(o.seed, 1));
  const pts: Vec3[] = [];
  if (gen === "spiral") {
    const turns = num(o.turns, 4);
    const height = num(o.height, 3);
    for (let i = 0; i < count; i++) {
      const u = i / count;
      const a = u * turns * Math.PI * 2;
      const r = radius * (0.15 + 0.85 * u);
      pts.push([Math.cos(a) * r, (u - 0.5) * height, Math.sin(a) * r]);
    }
  } else if (gen === "galaxy") {
    const arms = Math.max(1, Math.floor(num(o.arms, 3)));
    for (let i = 0; i < count; i++) {
      const r = radius * Math.pow(rand(), 0.7);
      const a = (i % arms) * ((Math.PI * 2) / arms) + r * 1.1;
      const spread = 0.12 * radius * (0.3 + r / radius);
      pts.push([
        Math.cos(a) * r + (rand() - 0.5) * spread,
        (rand() - 0.5) * spread * 0.5 * (1 - r / radius + 0.2),
        Math.sin(a) * r + (rand() - 0.5) * spread,
      ]);
    }
  } else if (gen === "grid") {
    const n = Math.max(1, Math.round(Math.cbrt(count)));
    const sp = num(o.spacing, (radius * 2) / n);
    for (let x = 0; x < n; x++)
      for (let y = 0; y < n; y++)
        for (let z = 0; z < n; z++) pts.push([(x - (n - 1) / 2) * sp, (y - (n - 1) / 2) * sp, (z - (n - 1) / 2) * sp]);
  } else if (gen === "sphere") {
    for (let i = 0; i < count; i++) {
      const y = 1 - (2 * (i + 0.5)) / count;
      const r = Math.sqrt(1 - y * y);
      const a = i * 2.399963;
      pts.push([Math.cos(a) * r * radius, y * radius, Math.sin(a) * r * radius]);
    }
  } else {
    for (let i = 0; i < count; i++)
      pts.push([(rand() - 0.5) * radius * 2, (rand() - 0.5) * radius * 2, (rand() - 0.5) * radius * 2]);
  }
  return pts;
}

export const PARTICLES: Kind = {
  tint: false,
  build: (o) => {
    const pts = (Array.isArray(o.pts) ? list(o.pts).slice(0, MAX_POINTS).map((p) => vec3(p)) : generate(o));
    const inner = new THREE.Color(o.color ?? DEFAULT_COLOR);
    const outer = new THREE.Color(typeof o.color2 === "string" ? o.color2 : (o.color ?? DEFAULT_COLOR));
    let maxR = 1e-6;
    for (const p of pts) maxR = Math.max(maxR, Math.hypot(p[0], p[1], p[2]));
    const pos = new Float32Array(pts.length * 3);
    const col = new Float32Array(pts.length * 3);
    const c = new THREE.Color();
    pts.forEach((p, i) => {
      pos.set(p, i * 3);
      c.copy(inner).lerp(outer, Math.hypot(p[0], p[1], p[2]) / maxR);
      col.set([c.r, c.g, c.b], i * 3);
    });
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({
      size: num(o.size, 0.05),
      vertexColors: true,
      transparent: true,
      opacity: num(o.opacity, 0.9),
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    return new THREE.Points(geom, mat);
  },
};
