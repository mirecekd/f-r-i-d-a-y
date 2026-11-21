// frontend/src/views/chart-draw.ts
export interface Dataset { label?: string; data: any[] }
export interface ChartData { type: string; labels?: string[]; datasets: Dataset[] }
export interface Box { x: number; y: number; w: number; h: number }

export const PALETTE = ["#4fd8ff", "#ff9a3d", "#3dffa0", "#b36bff", "#ffd23d", "#ff5d8f"];
const GRID = "rgba(79,216,255,.18)";
const TEXT = "#8fc7dc";

export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

export function nums(d: Dataset): number[] {
  return d.data.map((v) => (Array.isArray(v) ? Number(v[1]) : Number(v)) || 0);
}

/** Horizontal grid lines with y labels; returns mapper from value to canvas y. */
export function drawAxes(g: CanvasRenderingContext2D, b: Box, min: number, max: number): (v: number) => number {
  g.font = "11px ui-monospace, monospace";
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (let i = 0; i <= 4; i++) {
    const v = min + ((max - min) * i) / 4;
    const y = b.y + b.h - (b.h * i) / 4;
    g.strokeStyle = GRID;
    g.beginPath();
    g.moveTo(b.x, y);
    g.lineTo(b.x + b.w, y);
    g.stroke();
    g.fillStyle = TEXT;
    g.fillText(String(Math.round(v * 100) / 100), b.x - 6, y);
  }
  return (v) => b.y + b.h - ((v - min) / (max - min || 1)) * b.h;
}

export function drawXLabels(g: CanvasRenderingContext2D, b: Box, labels: string[], centered: boolean): (i: number) => number {
  const n = labels.length;
  const step = centered ? b.w / n : b.w / Math.max(n - 1, 1);
  const xAt = (i: number) => b.x + (centered ? step * (i + 0.5) : step * i);
  g.fillStyle = TEXT;
  g.textAlign = "center";
  g.textBaseline = "top";
  const skip = Math.ceil(n / Math.max(1, Math.floor(b.w / 50)));
  labels.forEach((l, i) => i % skip === 0 && g.fillText(String(l), xAt(i), b.y + b.h + 6));
  return xAt;
}

export function drawLegend(g: CanvasRenderingContext2D, w: number, sets: { label?: string }[], names?: string[]): void {
  g.font = "11px ui-monospace, monospace";
  g.textAlign = "left";
  g.textBaseline = "middle";
  let x = 10;
  const items = names ?? sets.map((s, i) => s.label ?? `#${i + 1}`);
  items.forEach((name, i) => {
    const tw = g.measureText(name).width;
    if (x + tw + 24 > w) return;
    g.fillStyle = PALETTE[i % PALETTE.length];
    g.fillRect(x, 8, 10, 10);
    g.fillStyle = TEXT;
    g.fillText(name, x + 15, 13);
    x += tw + 30;
  });
}
