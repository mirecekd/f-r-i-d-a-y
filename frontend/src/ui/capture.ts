// frontend/src/ui/capture.ts
import "./capture.css";
import type { Net } from "../net";
import type { Voice } from "../audio/voice";
import { grabFrame } from "./capture-frame";

type Source = "camera" | "screen";
const INTERVAL_MS = 1000;

/** Camera / screen sharing: HUD toggles, draggable preview, ~1 fps JPEG frames to the Live session while voice is on. */
export class Capture {
  private source: Source | null = null;
  private stream: MediaStream | null = null;
  private facing: "user" | "environment" = "user";
  private timer = 0;
  private sending = false;
  private lastSent = 0;
  private voiceOn: boolean;
  private starting = false;
  private box = document.getElementById("capprev")!;
  private video = this.box.querySelector("video")!;
  private tag = this.box.querySelector<HTMLElement>(".cap-tag")!;
  private flip = this.box.querySelector<HTMLButtonElement>(".cap-flip")!;
  private note = document.getElementById("capnote")!;
  private noteTimer = 0;
  private buttons: Record<Source, HTMLElement> = { camera: document.getElementById("camerabtn")!, screen: document.getElementById("screenbtn")! };

  constructor(private net: Net, voice: Voice) {
    const md = navigator.mediaDevices;
    if (!md?.getUserMedia) this.buttons.camera.hidden = true;
    if (md && "getDisplayMedia" in md) this.buttons.screen.hidden = false;
    for (const s of ["camera", "screen"] as Source[]) this.buttons[s].onclick = () => void this.toggle(s);
    this.flip.onclick = () => void this.start("camera", true);
    this.flip.onpointerdown = (e) => e.stopPropagation();
    this.makeDraggable();
    this.voiceOn = voice.active;
    voice.onActive = (on) => {
      this.voiceOn = on;
      if (on) this.setSending(true);
      else this.stop();
    };
    document.addEventListener("visibilitychange", () => this.tickSoon());
    addEventListener("pagehide", () => this.stop());
  }

  private makeDraggable(): void {
    const box = this.box;
    box.style.left = "30px";
    box.style.top = "210px";
    box.onpointerdown = (e) => {
      const dx = e.clientX - box.offsetLeft, dy = e.clientY - box.offsetTop;
      box.setPointerCapture(e.pointerId);
      box.onpointermove = (m) => {
        box.style.left = `${Math.max(0, Math.min(innerWidth - box.offsetWidth, m.clientX - dx))}px`;
        box.style.top = `${Math.max(0, Math.min(innerHeight - box.offsetHeight, m.clientY - dy))}px`;
      };
      box.onpointerup = box.onpointercancel = () => (box.onpointermove = null);
    };
  }

  private async toggle(source: Source): Promise<void> {
    if (this.source === source) this.stop();
    else await this.start(source, false);
  }

  private async start(source: Source, flipFacing: boolean): Promise<void> {
    if (this.starting) return;
    this.starting = true;
    try {
      const md = navigator.mediaDevices;
      const next = flipFacing ? (this.facing === "user" ? "environment" : "user") : this.facing;
      const stream = source === "camera"
        ? await md.getUserMedia({ video: { facingMode: next, width: { ideal: 1280 } }, audio: false })
        : await md.getDisplayMedia({ video: true, audio: false });
      this.release();
      this.facing = next;
      this.stream = stream;
      this.source = source;
      stream.getVideoTracks()[0].onended = () => this.stop();
      this.video.srcObject = stream;
      await this.video.play().catch(() => {});
      this.show();
      this.setSending(this.voiceOn);
      if (!this.voiceOn) this.notify("Zapni mikrofon - Friday vidi jen behem hlasove relace");
    } catch (e) {
      console.warn("capture unavailable", e);
      this.notify(source === "camera" ? "Kamera neni dostupna" : "Sdileni obrazovky neni dostupne");
    } finally {
      this.starting = false;
    }
  }

  private show(): void {
    const cam = this.source === "camera";
    this.box.hidden = !this.source;
    this.video.classList.toggle("mirror", cam && this.facing === "user");
    this.flip.hidden = !cam;
    for (const s of ["camera", "screen"] as Source[]) {
      this.buttons[s].classList.toggle("on", this.source === s);
      this.buttons[s].setAttribute("aria-pressed", String(this.source === s));
    }
  }

  private setSending(on: boolean): void {
    if (!this.source) return;
    this.sending = on;
    this.box.classList.toggle("idle", !on);
    this.tag.querySelector("b")!.textContent = on ? "LIVE" : "NEODESILA";
    clearInterval(this.timer);
    if (on) this.timer = window.setInterval(() => this.tick(), INTERVAL_MS);
  }

  private tickSoon(): void {
    if (!document.hidden && this.sending) this.tick();
  }

  private tick(): void {
    if (!this.source || !this.sending || document.hidden || !this.voiceOn) return;
    if (performance.now() - this.lastSent < INTERVAL_MS * 0.5) return; // timers fire in bursts after a stall
    const data_b64 = grabFrame(this.video);
    if (!data_b64) return;
    this.lastSent = performance.now();
    this.net.send({ t: "frame", source: this.source, mime: "image/jpeg", data_b64 });
  }

  private release(): void {
    this.stream?.getTracks().forEach((t) => (t.onended = null, t.stop()));
    this.stream = null;
    this.video.srcObject = null;
  }

  /** Stop tracks, hide the preview and tell the server the stream ended. */
  stop(): void {
    if (!this.source) return;
    clearInterval(this.timer);
    this.release();
    this.source = null;
    this.sending = false;
    this.show();
    this.net.send({ t: "frames_stop" });
  }

  private notify(text: string): void {
    this.note.textContent = text;
    this.note.classList.add("show");
    clearTimeout(this.noteTimer);
    this.noteTimer = window.setTimeout(() => this.note.classList.remove("show"), 5000);
  }
}
