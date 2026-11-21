// frontend/src/scene/kinds/csg.ts
import * as THREE from "three";
import { ADDITION, Brush, Evaluator, INTERSECTION, SUBTRACTION } from "three-bvh-csg";
import type { Kind, Obj } from "../types";
import { colorOf, list } from "./util";

const MAX_TRIS = 50000;
const SETTLE_MS = 150;
const OPS: Record<string, number> = { subtract: SUBTRACTION, union: ADDITION, intersect: INTERSECTION };

const triCount = (m: THREE.Mesh): number => (m.geometry.index ? m.geometry.index.count : m.geometry.getAttribute("position").count) / 3;

/** The mesh of each operand plus its sibling edge outlines (holo groups), each once. */
const inputsOf = (ms: THREE.Mesh[]): THREE.Object3D[] => [...new Set(ms.flatMap((m) => m.parent?.children ?? [m]))];

/**
 * Boolean of other scene objects, evaluated lazily once the referenced objects exist:
 * `{op: subtract|union|intersect, a: id, b: [ids], hide_inputs}`. Place it at the origin of the same parent as its
 * operands. Over MAX_TRIS or on any failure the cutters are drawn as dark translucent boxes and a warning is logged.
 */
class CsgGroup extends THREE.Group {
  private sig = "";
  private pending = "";
  private since = 0;
  private warned = false;
  private shown: THREE.Object3D[] = [];
  private hidden: THREE.Object3D[] = [];
  constructor(private o: Obj) { super(); }

  private top(): THREE.Object3D {
    let t: THREE.Object3D = this;
    while (t.parent) t = t.parent;
    return t;
  }

  /** Meshes (with their own object ids' node) of the scene object `id`, or [] when it does not exist. */
  private meshesOf(id: string): THREE.Mesh[] {
    let node: THREE.Object3D | undefined;
    this.top().traverse((n) => { if (!node && n.userData.id === id) node = n; });
    const out: THREE.Mesh[] = [];
    node?.traverse((n) => { if ((n as THREE.Mesh).isMesh && !this.shown.includes(n)) out.push(n as THREE.Mesh); });
    return out;
  }

  /** Geometry (position + normal only) of `m` in this group's frame. */
  private baked(m: THREE.Mesh, inv: THREE.Matrix4): THREE.BufferGeometry {
    m.updateWorldMatrix(true, false);
    const src = m.geometry;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", src.getAttribute("position").clone());
    g.setAttribute("normal", src.getAttribute("normal").clone());
    if (src.index) g.setIndex(src.index.clone());
    return g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld));
  }

  override updateMatrixWorld(force?: boolean): void {
    super.updateMatrixWorld(force);
    const a = typeof this.o.a === "string" ? this.o.a : "";
    const bs = list(this.o.b).filter((v): v is string => typeof v === "string");
    const inv = new THREE.Matrix4().copy(this.matrixWorld).invert();
    const bm = bs.map((id) => this.meshesOf(id));
    const cutters = new Set(bm.flat());
    const am = this.meshesOf(a).filter((m) => !cutters.has(m)); // `a` may be a group that also parents the cutters
    let sig = `${a}:${am.length}`;
    for (const m of [...am, ...bm.flat()]) {
      m.updateWorldMatrix(true, false);
      sig += `|${m.geometry.uuid}${new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld).elements.map((v) => v.toFixed(3)).join(",")}`;
    }
    if (sig === this.sig) { this.pending = ""; return; }
    const now = performance.now();
    if (sig !== this.pending) { this.pending = sig; this.since = now; }
    if (this.sig !== "" && now - this.since < SETTLE_MS) return; // inputs still moving (explode tween)
    this.sig = sig;
    this.rebuild(am, bm.flat(), inv);
  }

  private clearResult(): void {
    this.hidden.forEach((n) => { n.visible = true; });
    this.hidden = [];
    for (const n of this.shown) { this.remove(n); n.traverse((c) => { (c as THREE.Mesh).geometry?.dispose(); }); }
    this.shown = [];
  }

  private rebuild(am: THREE.Mesh[], bm: THREE.Mesh[], inv: THREE.Matrix4): void {
    this.clearResult();
    if (am.length === 0) return;
    const color = colorOf(this.o);
    const tris = [...am, ...bm].reduce((s, m) => s + triCount(m), 0);
    const hideInputs = this.o.hide_inputs !== false;
    const op = OPS[String(this.o.op)] ?? SUBTRACTION;
    try {
      if (tris > MAX_TRIS) throw new Error(`${tris} triangles exceed ${MAX_TRIS}`);
      const ev = new Evaluator();
      ev.attributes = ["position", "normal"];
      const brush = (m: THREE.Mesh): Brush => new Brush(this.baked(m, inv), new THREE.MeshStandardMaterial());
      let acc = am.map(brush).reduce((x, y) => ev.evaluate(x, y, ADDITION));
      for (const m of bm) acc = ev.evaluate(acc, brush(m), op);
      const geom = acc.geometry.clone();
      const mat = new THREE.MeshStandardMaterial({ color, transparent: true, opacity: 0.45, roughness: 0.3, side: THREE.DoubleSide });
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geom, 25), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 }));
      this.shown.push(new THREE.Mesh(geom, mat), edges);
      if (hideInputs) this.hidden = inputsOf([...am, ...bm]);
    } catch (e) {
      if (!this.warned) console.warn("csg: falling back to cutter boxes:", e);
      this.warned = true;
      const dark = new THREE.MeshBasicMaterial({ color: 0x05070a, transparent: true, opacity: 0.7, depthWrite: false });
      for (const m of bm) {
        const box = new THREE.Mesh(this.baked(m, inv), dark);
        box.scale.setScalar(0.97);
        this.shown.push(box);
        this.hidden.push(...inputsOf([m]));
      }
    }
    this.hidden.forEach((n) => { n.visible = false; });
    this.shown.forEach((n) => this.add(n));
  }
}

export const CSG: Kind = { tint: false, build: (o) => new CsgGroup(o) };
