// frontend/src/scene/select.ts
import * as THREE from "three";
import { attachGestures } from "./gestures";

const HIGHLIGHT = 0xffd24a;

/** Click-to-select with a bounding-box highlight. Click empty space clears; shift-click toggles; clicking the selected object again selects its parent. */
export class Selection {
  ids: string[] = [];
  onChange: (ids: string[]) => void = () => {};
  readonly overlay = new THREE.Group();
  private boxes = new Map<string, THREE.Box3Helper>();
  private ray = new THREE.Raycaster();

  constructor(
    private nodeOf: (id: string) => THREE.Object3D | undefined,
    private parentOf: (id: string) => string | undefined,
    private pickables: () => THREE.Object3D[],
  ) {
    this.ray.params.Line = { threshold: 0.12 };
    this.ray.params.Points = { threshold: 0.15 };
  }

  /** Called with the hit id (or undefined for empty space) after a double tap / long press. */
  onFrame: (id: string | undefined) => void = () => {};
  onMenu: (id: string, x: number, y: number) => void = () => {};

  private camera: THREE.Camera | null = null;

  /** Object under a normalised screen point (0..1, y down), or undefined. Used by hand gestures. */
  pickAt(nx: number, ny: number): string | undefined {
    if (!this.camera) return undefined;
    this.ray.setFromCamera(new THREE.Vector2(nx * 2 - 1, -(ny * 2 - 1)), this.camera);
    return this.hitId();
  }

  attach(canvas: HTMLElement, camera: THREE.Camera): void {
    this.camera = camera;
    const pick = (x: number, y: number): string | undefined => {
      const r = canvas.getBoundingClientRect();
      this.ray.setFromCamera(new THREE.Vector2(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1), camera);
      return this.hitId();
    };
    attachGestures(canvas, {
      tap: (x, y, shift) => this.click(pick(x, y), shift),
      doubleTap: (x, y) => {
        const id = pick(x, y);
        if (id) this.choose([id]);
        this.onFrame(id);
      },
      longPress: (x, y) => {
        const id = pick(x, y);
        if (!id) return;
        this.choose([id]);
        this.onMenu(id, x, y);
      },
    });
  }

  set(ids: string[]): void {
    this.ids = ids;
    for (const [id, b] of this.boxes) {
      if (!ids.includes(id)) {
        b.removeFromParent();
        b.geometry.dispose();
        this.boxes.delete(id);
      }
    }
    for (const id of ids) {
      if (this.boxes.has(id)) continue;
      const b = new THREE.Box3Helper(new THREE.Box3(), HIGHLIGHT);
      b.renderOrder = 30;
      (b.material as THREE.Material).depthTest = false;
      this.boxes.set(id, b);
      this.overlay.add(b);
    }
  }

  /** Re-fits the highlight boxes to the (animated) objects; drops ids whose object is gone. */
  update(): void {
    const gone = this.ids.filter((id) => !this.nodeOf(id));
    if (gone.length) this.set(this.ids.filter((id) => !gone.includes(id)));
    for (const [id, b] of this.boxes) {
      const node = this.nodeOf(id)!;
      b.visible = node.visible;
      b.box.setFromObject(node);
    }
  }

  private hitId(): string | undefined {
    for (const h of this.ray.intersectObjects(this.pickables(), true)) {
      let shown = true;
      for (let o: THREE.Object3D | null = h.object; o; o = o.parent) shown &&= o.visible;
      if (!shown) continue;
      for (let o: THREE.Object3D | null = h.object; o; o = o.parent) {
        if (typeof o.userData.id === "string" && o.visible) return o.userData.id;
      }
    }
    return undefined;
  }

  private click(id: string | undefined, additive: boolean): void {
    let next: string[];
    if (!id) next = [];
    else if (additive) next = this.ids.includes(id) ? this.ids.filter((i) => i !== id) : [...this.ids, id];
    else if (this.ids.length === 1 && this.ids[0] === id) next = [this.parentOf(id) ?? id];
    else next = [id];
    this.choose(next);
  }

  private choose(next: string[]): void {
    this.set(next);
    this.onChange(next);
  }
}
