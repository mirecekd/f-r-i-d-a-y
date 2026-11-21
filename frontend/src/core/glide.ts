// frontend/src/core/glide.ts
import * as THREE from "three";

export interface CamGoal {
  pos: THREE.Vector3;
  look: THREE.Vector3;
}

/** Camera pose that fits `box` in view, keeping the current viewing direction. */
export function fitGoal(box: THREE.Box3, camera: THREE.PerspectiveCamera, look: THREE.Vector3): CamGoal {
  const centre = box.getCenter(new THREE.Vector3());
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 0.3);
  const half = Math.min(THREE.MathUtils.degToRad(camera.fov) / 2, Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * camera.aspect));
  const dir = camera.position.clone().sub(look);
  if (dir.lengthSq() < 1e-6) dir.set(0, 0.2, 1);
  const dist = Math.min((radius / Math.sin(half)) * 1.15, 40);
  return { pos: centre.clone().add(dir.normalize().multiplyScalar(dist)), look: centre };
}

/** Moves camera and orbit target a fraction of the way to `goal`; returns false once arrived. */
export function glideStep(goal: CamGoal, camera: THREE.Camera, target: THREE.Vector3, dt: number): boolean {
  const k = 1 - Math.exp(-dt * 3);
  camera.position.lerp(goal.pos, k);
  target.lerp(goal.look, k);
  return camera.position.distanceTo(goal.pos) >= 0.02;
}
