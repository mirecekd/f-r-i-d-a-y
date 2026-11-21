// frontend/src/views/memory_labels.ts
import type { LabelMode } from "./memory_filters";
import { disposeLabel, labelSprite, KIND_COLOR, partsOf, setOrbLevel, type Kind, type MemNode } from "./memory_orbs";

export const NEAR = 110; // in auto mode, non-project/session nodes closer than this to the camera get a label
export const alwaysLabel = (n: MemNode): boolean => n.kind === "project" || n.kind === "session";

export interface LabelCtx {
  mode: LabelMode;
  nodes: any[];
  camera: { x: number; y: number; z: number };
  hover: MemNode | null;
  selected: MemNode | null;
  matches(n: MemNode): boolean;
  /** Search results always carry a label. */
  pinned?(n: MemNode): boolean;
  level(n: MemNode): number;
}

/** Adds or drops label sprites so that exactly the wanted nodes carry one. */
export function syncLabels(c: LabelCtx): void {
  for (const n of c.nodes) {
    const p = partsOf(n.__threeObj);
    if (!p) continue;
    const near = n.x !== undefined && c.matches(n) && Math.hypot(n.x - c.camera.x, n.y - c.camera.y, n.z - c.camera.z) < NEAR;
    const want =
      n === c.hover || n === c.selected || !!c.pinned?.(n) || (c.mode === "always" && c.matches(n)) || (c.mode === "auto" && (alwaysLabel(n) || near));
    if (want && !p.label) { p.label = labelSprite(n.label, KIND_COLOR[n.kind as Kind], p.radius); n.__threeObj.add(p.label); setOrbLevel(p, c.level(n)); }
    else if (!want && p.label) disposeLabel(p);
  }
}
