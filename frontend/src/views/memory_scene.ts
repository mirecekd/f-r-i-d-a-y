// frontend/src/views/memory_scene.ts
import { MOUSE } from "three";
import type { ForceGraph3DInstance } from "3d-force-graph";
import { params } from "../core/params";

/** The 3d-force-graph instance with the orbit controls this view wants (library is lazy-loaded). */
export async function createScene(holder: HTMLElement, heavy: boolean): Promise<{ graph: ForceGraph3DInstance; controls: any }> {
  const { default: ForceGraph3D } = await import("3d-force-graph");
  const graph = new ForceGraph3D(holder, { controlType: "orbit", rendererConfig: { alpha: true, antialias: !heavy } });
  graph.renderer().setPixelRatio(Math.min(devicePixelRatio, params.pixelRatio, 1.5));
  const controls = graph.controls() as any;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.55;
  controls.enableDamping = true;
  controls.zoomSpeed = 1.4;
  controls.minDistance = 30;
  controls.maxDistance = 4000;
  controls.zoomToCursor = true;
  // Middle button held + drag moves the whole scene (pan); left rotates, right pans too, the wheel zooms.
  controls.mouseButtons = { LEFT: MOUSE.ROTATE, MIDDLE: MOUSE.PAN, RIGHT: MOUSE.PAN };
  controls.screenSpacePanning = true;
  controls.panSpeed = 1.2;
  // A middle press must not start the browser's autoscroll (the round scroll cursor) over the graph.
  holder.addEventListener("mousedown", (e) => { if (e.button === 1) e.preventDefault(); });
  holder.addEventListener("auxclick", (e) => { if (e.button === 1) e.preventDefault(); });
  return { graph, controls };
}
