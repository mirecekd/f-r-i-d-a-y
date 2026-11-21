// frontend/src/gesture/cammove.ts - camera pan, dolly and orbit driven by normalised hand motion.
import * as THREE from "three";

export interface CamRig {
  camera: THREE.PerspectiveCamera;
  controls: { target: THREE.Vector3 };
}

export interface CamSnapshot { pos: THREE.Vector3; target: THREE.Vector3 }

export const snapshot = (rig: CamRig): CamSnapshot => ({ pos: rig.camera.position.clone(), target: rig.controls.target.clone() });

export function restore(rig: CamRig, s: CamSnapshot): void {
  rig.camera.position.copy(s.pos);
  rig.controls.target.copy(s.target);
}

/** World-space size of one normalised screen unit (x, y) at distance d in front of the camera. */
export function unitsAt(camera: THREE.PerspectiveCamera, d: number): { w: number; h: number } {
  const h = 2 * d * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  return { w: h * camera.aspect, h };
}

/** World displacement for a normalised screen delta, in the camera plane at distance d. */
export function screenToWorld(camera: THREE.PerspectiveCamera, dx: number, dy: number, d: number): THREE.Vector3 {
  const u = unitsAt(camera, d);
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  return right.multiplyScalar(dx * u.w).add(up.multiplyScalar(-dy * u.h));
}

/** Drags the scene with the hand: camera and target move opposite to the hand. */
export function pan(rig: CamRig, dx: number, dy: number): void {
  const d = rig.camera.position.distanceTo(rig.controls.target);
  const m = screenToWorld(rig.camera, -dx, -dy, d);
  rig.camera.position.add(m);
  rig.controls.target.add(m);
}

/** Camera distance to the target becomes start / ratio (hands apart = closer), clamped to 1.5..40. */
export function dolly(rig: CamRig, start: CamSnapshot, ratio: number): void {
  const dir = start.pos.clone().sub(start.target);
  const dist = THREE.MathUtils.clamp(dir.length() / Math.max(ratio, 0.05), 1.5, 40);
  rig.camera.position.copy(start.target).add(dir.normalize().multiplyScalar(dist));
}

/** Orbits the camera around the target about the world up axis by `angle` radians. */
export function orbit(rig: CamRig, start: CamSnapshot, angle: number): void {
  const off = start.pos.clone().sub(start.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), -angle);
  rig.camera.position.copy(start.target).add(off);
}
