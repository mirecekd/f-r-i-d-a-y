// frontend/src/scene/tween.ts
import * as THREE from "three";
import type { Entry } from "./entry";

export type TweenKey = "pos" | "rot" | "scale" | "color" | "ex";

interface Tween {
  entry: Entry;
  key: TweenKey;
  from: THREE.Vector3 | THREE.Color;
  to: THREE.Vector3 | THREE.Color;
  t: number;
  ms: number;
}

const ease = (k: number): number => k * k * (3 - 2 * k);

/** Time-based lerp of entry.pos / rot / scale / color. A new tween on the same entry+key replaces the old one. */
export class Tweens {
  private list: Tween[] = [];
  private last = performance.now();

  start(entry: Entry, key: TweenKey, to: THREE.Vector3 | THREE.Color, ms: number): void {
    this.list = this.list.filter((w) => !(w.entry === entry && w.key === key));
    this.list.push({ entry, key, from: entry[key].clone(), to, t: 0, ms });
  }

  drop(entry: Entry): void {
    this.list = this.list.filter((w) => w.entry !== entry);
  }

  /** Advances all tweens by wall-clock time (so slow frame rates do not stretch them); returns the entries that changed. */
  update(): Map<Entry, TweenKey[]> {
    const changed = new Map<Entry, TweenKey[]>();
    const now = performance.now();
    const elapsed = now - this.last;
    this.last = now;
    for (const w of this.list) {
      w.t += elapsed;
      const k = ease(Math.min(w.t / w.ms, 1));
      if (w.from instanceof THREE.Color) (w.entry.color as THREE.Color).lerpColors(w.from, w.to as THREE.Color, k);
      else (w.entry[w.key] as THREE.Vector3).lerpVectors(w.from, w.to as THREE.Vector3, k);
      const keys = changed.get(w.entry) ?? [];
      keys.push(w.key);
      changed.set(w.entry, keys);
    }
    this.list = this.list.filter((w) => w.t < w.ms);
    return changed;
  }
}
