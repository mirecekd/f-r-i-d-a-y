// frontend/src/core/stage.ts
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { params } from "./params";

export type Tick = (dt: number, t: number) => void;

/** Renderer, camera, bloom and the frame loop. Everything else plugs in via onTick. */
export class Stage {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: OrbitControls;
  private composer: EffectComposer;
  private ticks: Tick[] = [];
  private timer = new THREE.Timer();
  private simTime = 0;

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, params.pixelRatio));
    this.scene.fog = new THREE.FogExp2(0x02060c, 0.035);
    this.camera.position.set(0, 1.2, 9);

    this.scene.add(new THREE.AmbientLight(0x6fa8c8, 0.6));
    const key = new THREE.PointLight(0x8fe8ff, 40, 40);
    key.position.set(4, 6, 6);
    this.scene.add(key);

    const grid = new THREE.GridHelper(60, 60, 0x1b6a86, 0x0c2a3a);
    grid.position.y = -3.2;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.45;
    this.scene.add(grid);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.maxDistance = 40;
    // Tablet: one finger orbits, two fingers pinch-zoom and pan.
    this.controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
    canvas.style.touchAction = "none";

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    if (params.bloom) this.composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), 0.7, 0.5, 0.3));
    this.composer.addPass(new OutputPass());

    addEventListener("resize", () => this.resize());
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  onTick(fn: Tick): void {
    this.ticks.push(fn);
  }

  private resize(): void {
    const w = innerWidth;
    const h = innerHeight;
    this.renderer.setSize(w, h, false);
    this.composer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private frame(): void {
    this.timer.update();
    const real = Math.min(this.timer.getDelta(), 0.1);
    const dt = params.fixedStep || real;
    this.simTime += dt;
    const t = params.fixedStep ? this.simTime : this.timer.getElapsed();
    for (const fn of this.ticks) fn(dt, t);
    this.controls.update();
    this.composer.render();
  }
}
