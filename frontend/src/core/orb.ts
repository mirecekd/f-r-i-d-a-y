// frontend/src/core/orb.ts
import * as THREE from "three";
import { params } from "./params";
import { LOOKS, cloneLook, stepLook, type Look, type OrbState } from "./orblook";

export type { OrbState };

// Sprite size in CSS px at camera distance 9; scaled up when fewer particles are used.
const POINT_SIZE = 4.5;
const FULL_COUNT = 24000;

const VERT = /* glsl */ `
  uniform float uTime, uLevel, uRadius, uNoise, uRing, uPx;
  attribute vec3 aDir;
  attribute float aSeed;
  varying float vGlow;
  void main() {
    float n = sin(aDir.x * 3.1 + uTime * 0.9 + aSeed * 6.0)
            * sin(aDir.y * 2.7 - uTime * 0.7)
            * sin(aDir.z * 3.4 + uTime * 0.6);
    float r = uRadius * (1.0 + n * (uNoise + uLevel * 0.6));
    vec3 p = aDir * r;
    // thinking: a third of the particles leave the shell and orbit as a ring
    float a = atan(aDir.z, aDir.x) + uTime * 0.6;
    vec3 ringP = vec3(cos(a), sin(aSeed * 40.0) * 0.06, sin(a)) * uRadius * 1.45;
    p = mix(p, ringP, uRing * step(aSeed, 0.33));
    vGlow = 0.5 + 0.5 * n + uLevel;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = uPx * (1.0 + uLevel) * (6.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const FRAG = /* glsl */ `
  uniform vec3 uColor;
  varying float vGlow;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float a = smoothstep(0.5, 0.0, d);
    // Additive blending: keep per-particle intensity low so the state colour survives instead of clipping to white.
    gl_FragColor = vec4(uColor * (0.25 + 0.45 * vGlow), a * 0.8);
  }
`;

/** The Friday core: a GPU particle sphere whose look follows the assistant state. */
export class Orb {
  readonly object: THREE.Points;
  level = 0; // 0..1 audio level, set by the audio layer
  private state: OrbState = "idle";
  private cur: Look = cloneLook(LOOKS.idle);
  private mat: THREE.ShaderMaterial;

  /** `pointPx` overrides the sprite size (device px at distance 6); the mini orb passes its own. */
  constructor(count = params.particles, pointPx?: number) {
    const dirs = new Float32Array(count * 3);
    const seeds = new Float32Array(count);
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2;
      const rad = Math.sqrt(1 - y * y);
      const th = golden * i;
      dirs.set([Math.cos(th) * rad, y, Math.sin(th) * rad], i * 3);
      seeds[i] = Math.random();
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    geo.setAttribute("aDir", new THREE.BufferAttribute(dirs, 3));
    geo.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);

    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uLevel: { value: 0 },
        uRadius: { value: 1.8 },
        uNoise: { value: 0.08 },
        uRing: { value: 0 },
        uPx: { value: pointPx ?? POINT_SIZE * Math.sqrt(FULL_COUNT / count) * Math.min(devicePixelRatio, params.pixelRatio) },
        uColor: { value: new THREE.Color(0.2, 0.75, 1) },
      },
    });
    this.object = new THREE.Points(geo, this.mat);
  }

  setState(s: OrbState): void {
    this.state = s;
  }

  update(dt: number, t: number): void {
    const to = LOOKS[this.state];
    const k = 1 - Math.exp(-dt * 4);
    stepLook(this.cur, to, k);

    const u = this.mat.uniforms;
    // Idle breathing keeps the core alive even without audio.
    const breath = this.state === "idle" ? 0.03 * Math.sin(t * 1.2) : 0;
    u.uTime.value = t;
    u.uLevel.value += (this.level + breath - u.uLevel.value) * (1 - Math.exp(-dt * 12));
    u.uRadius.value = this.cur.radius;
    u.uNoise.value = this.cur.noise;
    u.uRing.value = this.cur.ring;
    u.uColor.value.setRGB(...this.cur.color);
    this.object.rotation.y += dt * this.cur.spin;
  }
}
