// frontend/src/ui/orbmini.ts
import * as THREE from "three";
import { Orb } from "../core/orb";
import { PALETTE, type OrbState } from "../core/orblook";
import { params } from "../core/params";

const SIZE = 140; // CSS px
const MINI_PARTICLES = 1500;
const MINI_POINT_PX = 2.2; // sprite size per device pixel ratio at camera distance 6.2

/** The Friday core as a small 2D element: own canvas, renderer, scene, camera and frame loop. */
export class OrbMini {
  readonly orb: Orb;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(50, 1, 0.1, 50);
  private clock = new THREE.Clock();
  private simTime = 0;
  private label = document.getElementById("orbstate");
  private state: OrbState = "idle";
  private down = !params.offline; // websocket down; starts down until net.onStatus(true)

  constructor(private canvas: HTMLCanvasElement) {
    const dpr = Math.min(devicePixelRatio, 2, params.pixelRatio);
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(SIZE, SIZE, false);
    this.renderer.setClearColor(0x000000, 0);
    this.camera.position.set(0, 0, 6.2);
    this.orb = new Orb(Math.min(params.particles, MINI_PARTICLES), MINI_POINT_PX * dpr);
    this.scene.add(this.orb.object);
    this.renderer.setAnimationLoop(() => this.frame());
    this.show();
  }

  /** Assistant state; while the websocket is down the orb keeps showing OFFLINE. */
  setState(s: OrbState): void {
    this.state = s;
    this.show();
  }

  setOffline(down: boolean): void {
    if (this.down && !down) this.state = "idle"; // state before the reconnect is stale
    this.down = down;
    this.show();
  }

  private show(): void {
    const s = this.down ? "offline" : this.state;
    this.orb.setState(s);
    if (!this.label) return;
    this.label.textContent = PALETTE[s].label;
    this.label.style.color = PALETTE[s].text;
    this.label.dataset.state = s;
  }

  hide(): void {
    if (this.label) this.label.hidden = true;
    this.renderer.setAnimationLoop(null);
    this.canvas.hidden = true;
  }

  private frame(): void {
    const real = Math.min(this.clock.getDelta(), 0.1);
    const dt = params.fixedStep || real;
    this.simTime += dt;
    this.orb.update(dt, params.fixedStep ? this.simTime : this.clock.elapsedTime);
    this.renderer.render(this.scene, this.camera);
  }
}
