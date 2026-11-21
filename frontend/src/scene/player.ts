// frontend/src/scene/player.ts
import * as THREE from "three";
import { KINDS } from "./kinds";
import { applyAnims } from "./anim";
import { baseColor, disposeTree, tintContent, toAnims, toScale, type Entry } from "./entry";
import { explodeOffsets } from "./explode";
import { followTargets } from "./follow";
import { fitGoal } from "../core/glide";
import { Selection } from "./select";
import { Tweens, type TweenKey } from "./tween";
import type { Obj, Op } from "./types";

export type { Obj, Op } from "./types";

const DEFAULT_TWEEN_MS = 0;
const EXPLODE_MS = 700;

/** Applies scene patches to a THREE.Group. Objects are holographic: wireframe shell + glow. */
export class ScenePlayer {
  readonly root = new THREE.Group();
  readonly selection: Selection;
  /** Called with the selected ids after a click in the 3D view. */
  onSelect: (ids: string[]) => void = () => {};
  /** Runtime entries by id; public for the headless interaction test. */
  entries = new Map<string, Entry>();
  private tweens = new Tweens();
  private explodeFactor = 0;

  constructor(private onCamera: (pos: THREE.Vector3, look: THREE.Vector3) => void) {
    this.selection = new Selection(
      (id) => this.entries.get(id)?.node,
      (id) => this.entries.get(id)?.obj.parent,
      () => [...this.entries.values()].filter((e) => !e.obj.parent).map((e) => e.node),
    );
    this.selection.onChange = (ids) => this.onSelect(ids);
    this.root.add(this.selection.overlay);
  }

  /** Wire pointer picking to the canvas. */
  attachPicking(canvas: HTMLElement, camera: THREE.Camera): void {
    this.selection.attach(canvas, camera);
  }

  /** Asks the camera to glide so the bounds of the given objects fill the view. */
  frame(ids: string[], camera: THREE.PerspectiveCamera, look: THREE.Vector3): void {
    const box = new THREE.Box3();
    for (const id of ids) {
      const n = this.entries.get(id)?.node;
      if (n) box.union(new THREE.Box3().setFromObject(n));
    }
    if (box.isEmpty()) return;
    const g = fitGoal(box, camera, look);
    this.onCamera(g.pos, g.look);
  }

  /** Per-frame update: tweens, animations, label anchoring, selection boxes. */
  tick(t: number): void {
    for (const [e, keys] of this.tweens.update()) {
      if (keys.includes("color")) tintContent(e);
      this.syncTransform(e);
    }
    for (const e of this.entries.values()) if (e.anims.length) applyAnims(e, t);
    followTargets(this.entries.values(), (id) => this.entries.get(id));
    this.selection.update();
  }

  apply(ops: Op[]): void {
    for (const op of ops) {
      if (op.op === "add") this.add(op.obj);
      else if (op.op === "set") this.set(op.id, op.props, op.ms ?? DEFAULT_TWEEN_MS);
      else if (op.op === "del") this.del(op.id);
      else if (op.op === "clear") [...this.entries.keys()].forEach((id) => this.del(id));
      else if (op.op === "camera") {
        this.onCamera(new THREE.Vector3(...op.pos), new THREE.Vector3(...(op.look ?? [0, 0, 0])));
      } else if (op.op === "explode") this.explode(op.factor);
    }
  }

  full(objs: Obj[]): void {
    this.apply([{ op: "clear" }, ...objs.map((obj) => ({ op: "add", obj }) as Op)]);
  }

  private add(o: Obj): void {
    this.del(o.id);
    const kind = KINDS[o.kind];
    if (!kind) {
      console.warn("unknown scene kind", o.kind);
      return;
    }
    const node = new THREE.Group();
    const inner = new THREE.Group();
    const content = kind.build(o);
    node.add(inner);
    inner.add(content);
    node.userData.id = o.id;
    const e: Entry = {
      obj: { ...o },
      node,
      inner,
      content,
      pos: new THREE.Vector3(...(o.pos ?? [0, 0, 0])),
      rot: new THREE.Vector3(...(o.rot ?? [0, 0, 0])),
      scale: toScale(o.scale),
      color: baseColor(o),
      ex: new THREE.Vector3(),
      anims: toAnims(o.anim),
      tint: kind.tint,
    };
    this.entries.set(o.id, e);
    e.node.visible = o.visible !== false;
    this.syncTransform(e);
    const parent = o.kind !== "label" || !o.target ? this.entries.get(o.parent ?? "")?.inner : undefined;
    (parent ?? this.root).add(node);
    // Children added before their parent existed are re-attached now.
    for (const c of this.entries.values()) if (c.obj.parent === o.id && c.node.parent !== inner) inner.add(c.node);
    if (this.explodeFactor) this.explode(this.explodeFactor, 0);
  }

  private set(id: string, props: Partial<Obj>, ms: number): void {
    const e = this.entries.get(id);
    if (!e) return;
    const { pos, rot, scale, color, anim, ...rest } = props;
    Object.assign(e.obj, props);
    if (anim !== undefined) e.anims = toAnims(anim);
    if (props.visible !== undefined) e.node.visible = props.visible;
    if (props.parent !== undefined) {
      const p = this.entries.get(props.parent);
      (p?.inner ?? this.root).add(e.node);
    }
    this.moveTo(e, "pos", pos ? new THREE.Vector3(...pos) : undefined, ms);
    this.moveTo(e, "rot", rot ? new THREE.Vector3(...rot) : undefined, ms);
    this.moveTo(e, "scale", scale !== undefined ? toScale(scale) : undefined, ms);
    if (color) this.moveTo(e, "color", new THREE.Color(color), ms);
    if (Object.keys(rest).some((k) => !["parent", "label", "opacity", "visible", "id", "kind"].includes(k)) || props.opacity !== undefined) {
      this.rebuild(e);
    }
    if (pos && this.explodeFactor) this.explode(this.explodeFactor, ms);
  }

  /** Content-defining props changed (text, values, nodes, ...): rebuild the content, keep transform and children. */
  private rebuild(e: Entry): void {
    const kind = KINDS[e.obj.kind];
    if (!kind) return;
    e.inner.remove(e.content);
    disposeTree(e.content);
    e.obj.color = `#${e.color.getHexString()}`;
    e.content = kind.build(e.obj);
    e.inner.add(e.content);
  }

  private moveTo(e: Entry, key: TweenKey, to: THREE.Vector3 | THREE.Color | undefined, ms: number): void {
    if (!to) return;
    if (ms > 0) {
      this.tweens.start(e, key, to, ms);
      return;
    }
    if (key === "color") {
      e.color.copy(to as THREE.Color);
      tintContent(e);
    } else (e[key] as THREE.Vector3).copy(to as THREE.Vector3);
    this.syncTransform(e);
  }

  private syncTransform(e: Entry): void {
    e.node.position.copy(e.pos).add(e.ex);
    e.node.rotation.set(e.rot.x, e.rot.y, e.rot.z);
    e.node.scale.copy(e.scale);
  }

  private del(id: string): void {
    const e = this.entries.get(id);
    if (!e) return;
    for (const c of [...this.entries.values()]) if (c.obj.parent === id) this.del(c.obj.id);
    this.tweens.drop(e);
    e.node.removeFromParent();
    disposeTree(e.content);
    this.entries.delete(id);
  }

  /** Exploded view: parts move away from their centre by `factor` (0 restores), animated over `ms`. */
  private explode(factor: number, ms = EXPLODE_MS): void {
    this.explodeFactor = factor;
    for (const [e, off] of explodeOffsets(this.entries.values(), factor)) {
      if (e.obj.kind === "label" && e.obj.target) continue;
      this.moveTo(e, "ex", off, ms);
    }
  }
}

