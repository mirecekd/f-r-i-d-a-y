// frontend/tests/memorypan.mjs - the memory graph pans with the middle mouse button (no WebGL, no DOM package).
// Drives the real three.js OrbitControls with synthetic pointer events on a minimal stub element: node tests/memorypan.mjs
import { MOUSE, PerspectiveCamera, Vector3 } from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const listeners = new Map();
const doc = {
  addEventListener: (t, f) => listeners.set("doc:" + t, f),
  removeEventListener: (t) => listeners.delete("doc:" + t),
};
const el = {
  ownerDocument: doc,
  style: {},
  clientWidth: 800,
  clientHeight: 600,
  addEventListener: (t, f) => listeners.set("el:" + t, f),
  removeEventListener: (t) => listeners.delete("el:" + t),
  setPointerCapture() {},
  releasePointerCapture() {},
  hasPointerCapture: () => false,
  getRootNode: () => doc,
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }),
};

const camera = new PerspectiveCamera(50, 800 / 600, 0.1, 5000);
camera.position.set(0, 0, 300);
const controls = new OrbitControls(camera, el);
controls.enableDamping = false;

// the exact assignment made in views/memory_scene.ts
controls.mouseButtons = { LEFT: MOUSE.ROTATE, MIDDLE: MOUSE.PAN, RIGHT: MOUSE.PAN };
controls.screenSpacePanning = true;

function drag(button, dx) {
  const ev = (type, x) => ({ type, pointerId: 1, pointerType: "mouse", button, buttons: 1 << (button === 1 ? 2 : button), clientX: x, clientY: 300, pageX: x, pageY: 300, preventDefault() {}, stopPropagation() {} });
  listeners.get("el:pointerdown")(ev("pointerdown", 400)); // registers the document listeners
  const move = listeners.get("doc:pointermove");
  const up = listeners.get("doc:pointerup");
  for (let i = 1; i <= 10; i++) move(ev("pointermove", 400 + (dx * i) / 10));
  up(ev("pointerup", 400 + dx));
  controls.update();
}

const t0 = controls.target.clone();
const c0 = camera.position.clone();
drag(1, 150); // middle button, drag right
const moved = controls.target.distanceTo(t0);
const dir = new Vector3().subVectors(controls.target, t0);
const camMoved = camera.position.distanceTo(c0);
const rotated = Math.abs(camera.position.length() - c0.length()) > 1e-6; // pan keeps the orbit radius

console.log(`middle drag 150 px: target moved ${moved.toFixed(2)} units (x ${dir.x.toFixed(2)}), camera moved ${camMoved.toFixed(2)}, radius changed: ${rotated}`);
let bad = 0;
if (!(moved > 1)) { console.error("FAIL: middle button did not pan the scene"); bad++; }
if (Math.abs(dir.y) > 1e-6 || Math.abs(dir.z) > 0.5) { console.error("FAIL: pan was not parallel to the screen"); bad++; }
if (bad) process.exit(1);
console.log("middle button pans ok");
