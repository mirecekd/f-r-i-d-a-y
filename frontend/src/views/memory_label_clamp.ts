// frontend/src/views/memory_label_clamp.ts
import * as THREE from "three";

const LABEL_MIN_PX = 9; // a label never gets smaller than this on screen ...
const LABEL_MAX_PX = 18; // ... nor bigger: close to the camera it would otherwise swallow the whole view
const _wp = new THREE.Vector3();
const _sz = new THREE.Vector2();

/** Keeps a label sprite's on-screen height between LABEL_MIN_PX and LABEL_MAX_PX whatever the camera distance. */
export function clampOnScreen(sp: THREE.Sprite, w: number, h: number): void {
  sp.onBeforeRender = (renderer, _scene, camera) => {
    const cam = camera as THREE.PerspectiveCamera;
    if (!cam.isPerspectiveCamera) return;
    sp.scale.set(w, h, 1);
    sp.updateWorldMatrix(true, false);
    sp.getWorldPosition(_wp);
    const parentScale = sp.parent ? sp.parent.getWorldScale(new THREE.Vector3()).y : 1;
    const dist = Math.max(0.01, _wp.distanceTo(cam.position));
    const px = (h * parentScale * renderer.getSize(_sz).y) / (2 * dist * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)));
    const k = px > LABEL_MAX_PX ? LABEL_MAX_PX / px : px < LABEL_MIN_PX ? LABEL_MIN_PX / Math.max(px, 0.01) : 1;
    if (k !== 1) sp.scale.set(w * k, h * k, 1);
  };
}
