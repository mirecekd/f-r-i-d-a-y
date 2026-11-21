// frontend/src/ui/gesturepreview.ts - draggable live preview of the hand tracker: mirrored video, skeleton, gesture label.
import type { Frame } from "../gesture/hand";

const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
const W = 160;
const H = 120;

export class GesturePreview {
  readonly root = document.createElement("div");
  private canvas = document.createElement("canvas");
  private tag = document.createElement("div");
  private note = document.createElement("div");
  private ctx = this.canvas.getContext("2d");

  constructor(video: HTMLVideoElement) {
    this.root.id = "gesturepreview";
    this.root.hidden = true;
    video.className = "gp-video";
    this.canvas.width = W;
    this.canvas.height = H;
    this.tag.className = "gp-tag";
    this.note.className = "gp-note";
    this.root.append(video, this.canvas, this.tag, this.note);
    document.body.appendChild(this.root);
    this.drag();
  }

  show(on: boolean): void {
    this.root.hidden = !on;
  }

  say(text: string): void {
    this.note.textContent = text;
    this.note.hidden = !text;
  }

  label(text: string): void {
    this.tag.textContent = text;
  }

  draw(f: Frame): void {
    const c = this.ctx;
    if (!c) return;
    c.clearRect(0, 0, W, H);
    c.strokeStyle = "#8fe8ff";
    c.fillStyle = "#ffd24a";
    c.lineWidth = 1.5;
    for (const h of f.hands) {
      const p = h.landmarks.map((q) => [(1 - q.x) * W, q.y * H]);
      c.beginPath();
      for (const [a, b] of BONES) {
        c.moveTo(p[a][0], p[a][1]);
        c.lineTo(p[b][0], p[b][1]);
      }
      c.stroke();
      for (const [x, y] of p) c.fillRect(x - 1.5, y - 1.5, 3, 3);
    }
  }

  private drag(): void {
    this.root.addEventListener("pointerdown", (e) => {
      const r = this.root.getBoundingClientRect();
      const dx = e.clientX - r.left;
      const dy = e.clientY - r.top;
      this.root.setPointerCapture(e.pointerId);
      const move = (m: PointerEvent): void => {
        this.root.style.left = `${Math.max(0, Math.min(innerWidth - r.width, m.clientX - dx))}px`;
        this.root.style.top = `${Math.max(0, Math.min(innerHeight - r.height, m.clientY - dy))}px`;
        this.root.style.right = "auto";
        this.root.style.bottom = "auto";
      };
      const up = (): void => {
        this.root.removeEventListener("pointermove", move);
        this.root.removeEventListener("pointerup", up);
      };
      this.root.addEventListener("pointermove", move);
      this.root.addEventListener("pointerup", up);
    });
  }
}
