// frontend/src/scene/kinds/media.ts
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import type { Kind } from "../types";
import { num } from "./util";

const loader = new GLTFLoader();

/** Textured plane from an http(s) url or data URI. Width `w` (default 3); height follows the aspect unless `h` is set. */
export const IMAGE: Kind = {
  tint: false,
  build: (o) => {
    const w = num(o.w, 3);
    const mat = new THREE.MeshBasicMaterial({ transparent: true, side: THREE.DoubleSide, opacity: num(o.opacity, 1) });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, num(o.h, w * 0.66)), mat);
    new THREE.TextureLoader().load(
      String(o.url ?? ""),
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        mat.map = tex;
        mat.needsUpdate = true;
        const img = tex.image as { width: number; height: number };
        if (o.h === undefined && img.width) {
          mesh.geometry.dispose();
          mesh.geometry = new THREE.PlaneGeometry(w, (w * img.height) / img.width);
        }
      },
      undefined,
      () => console.warn("image load failed", o.id),
    );
    return mesh;
  },
};

/** glTF/GLB model from `url`, centred and scaled so its largest dimension equals `fit` (default 2). */
export const GLTF: Kind = {
  tint: false,
  build: (o) => {
    const holder = new THREE.Group();
    loader.load(
      String(o.url ?? ""),
      (gltf) => {
        const box = new THREE.Box3().setFromObject(gltf.scene);
        const size = box.getSize(new THREE.Vector3());
        const k = num(o.fit, 2) / Math.max(size.x, size.y, size.z, 1e-6);
        gltf.scene.scale.setScalar(k);
        gltf.scene.position.copy(box.getCenter(new THREE.Vector3()).multiplyScalar(-k));
        holder.add(gltf.scene);
      },
      undefined,
      () => console.warn("gltf load failed", o.id),
    );
    return holder;
  },
};
