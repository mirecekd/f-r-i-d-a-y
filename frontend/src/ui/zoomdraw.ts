// frontend/src/ui/zoomdraw.ts
import { strokeRect, type Pt } from "../core/zoommath";

const FADE_MS = 380;

/** Full-screen display-only canvas that shows the glowing freehand outline and its dashed bounding rectangle. */
export class ZoomDraw {
  readonly canvas = document.createElement("canvas");
  private ctx = this.canvas.getContext("2d")!;
  private pts: Pt[] = [];
  private fadeFrom = 0;

  constructor() {
    this.canvas.id = "zoomdraw";
    document.body.appendChild(this.canvas);
    addEventListener("resize", () => this.resize());
    this.resize();
  }

  private resize(): void {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(innerWidth * dpr);
    this.canvas.height = Math.round(innerHeight * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.paint(1);
  }

  begin(p: Pt): void {
    this.pts = [p];
    this.fadeFrom = 0;
    this.paint(1);
  }

  add(p: Pt): void {
    this.pts.push(p);
    this.paint(1);
  }

  /** Fades the outline out after release. */
  end(): void {
    this.fadeFrom = performance.now();
    const step = (): void => {
      if (!this.fadeFrom) return;
      const a = 1 - (performance.now() - this.fadeFrom) / FADE_MS;
      if (a <= 0) {
        this.clear();
        return;
      }
      this.paint(a);
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  clear(): void {
    this.pts = [];
    this.fadeFrom = 0;
    this.paint(1);
  }

  private paint(alpha: number): void {
    const c = this.ctx;
    c.clearRect(0, 0, innerWidth, innerHeight);
    if (this.pts.length < 2) return;
    c.globalAlpha = alpha;
    const r = strokeRect(this.pts);
    c.setLineDash([8, 6]);
    c.lineWidth = 1;
    c.strokeStyle = "rgba(143, 232, 255, .7)";
    c.strokeRect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0);
    c.setLineDash([]);
    c.beginPath();
    c.moveTo(this.pts[0].x, this.pts[0].y);
    for (const p of this.pts.slice(1)) c.lineTo(p.x, p.y);
    c.closePath();
    c.fillStyle = "rgba(79, 216, 255, .13)";
    c.fill();
    c.lineJoin = "round";
    c.lineCap = "round";
    c.shadowColor = "#4fd8ff";
    c.shadowBlur = 14;
    c.strokeStyle = "#8fe8ff";
    c.lineWidth = 2.5;
    c.stroke();
    c.shadowBlur = 0;
    c.globalAlpha = 1;
  }
}
