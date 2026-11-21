// frontend/src/gesture/tracker.ts - lazy MediaPipe HandLandmarker on a camera stream (glue: never run with a real camera here).
import type { Frame } from "./hand";

export const MODEL_MISSING = "Model gest neni nainstalovan: spust scripts/fetch-gesture-model.sh";
const DEFAULT_MODEL = "/models/hand_landmarker.task";
const FRAME_MS = 33;
const HIDDEN_MS = 1000;

/** Model URL: `?gesturemodel=` overrides, else the backend static path. */
export const modelUrl = (): string => new URLSearchParams(location.search).get("gesturemodel") ?? DEFAULT_MODEL;

type Landmarker = import("@mediapipe/tasks-vision").HandLandmarker;

async function modelPresent(url: string): Promise<boolean> {
  try {
    const r = await fetch(url, { method: "HEAD" });
    return r.ok && !(r.headers.get("content-type") ?? "").includes("text/html");
  } catch {
    return false;
  }
}

async function load(url: string): Promise<Landmarker> {
  // Dynamic imports keep MediaPipe and its wasm out of the main chunk.
  const [{ HandLandmarker }, loader, binary] = await Promise.all([
    import("@mediapipe/tasks-vision"),
    import("@mediapipe/tasks-vision/vision_wasm_internal.js?url"),
    import("@mediapipe/tasks-vision/vision_wasm_internal.wasm?url"),
  ]);
  const fileset = { wasmLoaderPath: loader.default, wasmBinaryPath: binary.default };
  const make = (delegate: "GPU" | "CPU") =>
    HandLandmarker.createFromOptions(fileset, { baseOptions: { modelAssetPath: url, delegate }, runningMode: "VIDEO", numHands: 2 });
  try {
    return await make("GPU");
  } catch {
    return await make("CPU");
  }
}

export class HandTracker {
  readonly video = document.createElement("video");
  private lm: Landmarker | null = null;
  private stream: MediaStream | null = null;
  private own = false;
  private timer = 0;
  private lastVideoTime = -1;

  constructor(private onFrame: (f: Frame) => void) {
    this.video.muted = true;
    this.video.playsInline = true;
  }

  /** Starts tracking; resolves to an error text (shown to the user) or null on success. */
  async start(): Promise<string | null> {
    const url = modelUrl();
    if (!(await modelPresent(url))) return MODEL_MISSING;
    try {
      this.lm = await load(url);
    } catch (e) {
      return `Gesta: ${e instanceof Error ? e.message : String(e)}`;
    }
    const shared = (document.querySelector("#capprev video") as HTMLVideoElement | null)?.srcObject;
    if (shared instanceof MediaStream && shared.active) this.stream = shared;
    else {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 } }, audio: false });
        this.own = true;
      } catch {
        return "Kamera neni dostupna";
      }
    }
    this.video.srcObject = this.stream;
    await this.video.play().catch(() => {});
    this.loop();
    return null;
  }

  stop(): void {
    clearTimeout(this.timer);
    if (this.own) this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.own = false;
    this.video.srcObject = null;
    this.lm?.close();
    this.lm = null;
  }

  private loop(): void {
    if (!this.lm) return;
    const v = this.video;
    if (!document.hidden && v.readyState >= 2 && v.currentTime !== this.lastVideoTime) {
      this.lastVideoTime = v.currentTime;
      const t = performance.now();
      const r = this.lm.detectForVideo(v, t);
      this.onFrame({
        t,
        hands: r.landmarks.map((landmarks, i) => ({
          landmarks,
          handedness: r.handedness[i]?.[0]?.categoryName ?? "?",
          score: r.handedness[i]?.[0]?.score ?? 0,
        })),
      });
    }
    this.timer = window.setTimeout(() => this.loop(), document.hidden ? HIDDEN_MS : FRAME_MS);
  }
}
