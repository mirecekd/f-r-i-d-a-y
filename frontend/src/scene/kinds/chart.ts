// frontend/src/scene/kinds/chart.ts
import * as THREE from "three";
import type { Kind } from "../types";
import { colorOf, holo, list, lineSegments, num } from "./util";
import { makeTextSprite } from "./text";

/** 3D bar chart: bars stand on y=0, centred on x. `height` is the height of the tallest bar. */
export const CHART3D: Kind = {
  tint: false,
  build: (o) => {
    const values = list(o.values).map((v) => num(v, 0));
    const labels = list(o.labels).map(String);
    const gap = num(o.gap, 0.4);
    const maxH = num(o.height, 3);
    const peak = Math.max(...values.map(Math.abs), 1e-9);
    const base = colorOf(o);
    const hi = new THREE.Color(typeof o.color2 === "string" ? o.color2 : "#ffffff");
    const g = new THREE.Group();
    const total = values.length + (values.length - 1) * gap;
    values.forEach((v, i) => {
      const h = Math.max((Math.abs(v) / peak) * maxH, 0.02);
      const x = i * (1 + gap) - total / 2 + 0.5;
      const bar = holo(new THREE.BoxGeometry(1, h, 1), base.clone().lerp(hi, (Math.abs(v) / peak) * 0.35), 0.4);
      bar.position.set(x, v < 0 ? -h / 2 : h / 2, 0);
      g.add(bar);
      if (o.show_values !== false) {
        const t = makeTextSprite(String(Math.round(v * 100) / 100), "#dff9ff", 0.32);
        t.position.set(x, (v < 0 ? -h : h) + (v < 0 ? -0.3 : 0.3), 0);
        g.add(t);
      }
      if (labels[i]) {
        const t = makeTextSprite(labels[i], "#8fe8ff", 0.3);
        t.position.set(x, -0.35 - (v < 0 ? h : 0), 0.9);
        g.add(t);
      }
    });
    const half = total / 2 + 0.4;
    g.add(lineSegments([[-half, 0, 0.6], [half, 0, 0.6], [-half, 0, -0.6], [half, 0, -0.6], [-half, 0, 0.6], [-half, 0, -0.6], [half, 0, 0.6], [half, 0, -0.6]], base, 0.6));
    return g;
  },
};
