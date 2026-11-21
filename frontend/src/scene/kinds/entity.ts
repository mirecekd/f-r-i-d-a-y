// frontend/src/scene/kinds/entity.ts
import * as THREE from "three";
import type { Kind, Obj } from "../types";
import { glyphCanvas } from "../../core/glyphs";
import { clampOnScreen } from "../../views/memory_label_clamp";
import { DEFAULT_TILE, glyphForEntity, shortTitle, tileSize } from "../entity_logic";
import { makeTextSprite } from "./text";
import { DEFAULT_COLOR } from "./util";

const WORKSHOP_ACCENT = "#ffb347";
const DEPTH = 0.08;
const FRAME = 0.07;

function slab(w: number, h: number, accent: THREE.Color): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, DEPTH),
    new THREE.MeshStandardMaterial({ color: 0x06141f, transparent: true, opacity: 0.82, roughness: 0.4 }),
  );
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(w + FRAME, h + FRAME, DEPTH * 0.6),
    new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.9, wireframe: false }),
  );
  frame.position.z = -DEPTH * 0.45;
  g.add(frame, body);
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry), new THREE.LineBasicMaterial({ color: accent })));
  return g;
}

function face(w: number, h: number, map: THREE.Texture): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map, transparent: true }));
  m.position.z = DEPTH / 2 + 0.005;
  return m;
}

function portRing(w: number, accent: THREE.Color): THREE.Mesh {
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.02, 8, 24), new THREE.MeshBasicMaterial({ color: accent }));
  ring.position.set(w / 2 + 0.12, 0, 0);
  return ring;
}

/** Holographic tile for a stored file, image, model, memory or tool: slab + accent frame + thumbnail or glyph + title + link port. */
export const ENTITY: Kind = {
  tint: false,
  build: (o: Obj) => {
    const accent = new THREE.Color(String(o.accent ?? o.color ?? (o.shape === "workshop" ? WORKSHOP_ACCENT : DEFAULT_COLOR)));
    const title = String(o.title ?? o.label ?? o.id);
    const root = new THREE.Group();
    const [w, h] = typeof o.thumb === "string" ? tileSize(1.4) : DEFAULT_TILE;
    const body = new THREE.Group();
    root.add(body);
    const rebuild = (bw: number, bh: number, map: THREE.Texture): void => {
      body.clear();
      body.add(slab(bw, bh, accent), face(bw, bh, map), portRing(bw, accent));
    };
    const glyph = new THREE.CanvasTexture(glyphCanvas(glyphForEntity(String(o.shape ?? "note"), title), accent.getStyle(), 128));
    glyph.colorSpace = THREE.SRGBColorSpace;
    rebuild(w, h, glyph);
    if (typeof o.thumb === "string") {
      new THREE.TextureLoader().load(o.thumb, (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        const img = tex.image as { width: number; height: number };
        const [tw, th] = tileSize(img.width / img.height);
        rebuild(tw, th, tex);
        label.position.y = -th / 2 - 0.3;
      });
    }
    const label = makeTextSprite(shortTitle(title) + (o.subtitle ? `\n${shortTitle(String(o.subtitle), 34)}` : ""), "#e8fbff", o.subtitle ? 0.7 : 0.4);
    label.position.set(0, -h / 2 - 0.3, 0.1);
    clampOnScreen(label, label.scale.x, label.scale.y);
    root.add(label);
    return root;
  },
};
