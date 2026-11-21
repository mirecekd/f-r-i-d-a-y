// frontend/src/views/chart-kinds.ts
import { PALETTE, drawAxes, drawXLabels, niceMax, nums, type Box, type ChartData } from "./chart-draw";

type Painter = (g: CanvasRenderingContext2D, w: number, h: number, c: ChartData) => void;

const plotBox = (w: number, h: number): Box => ({ x: 44, y: 28, w: w - 58, h: h - 58 });
const labelsOf = (c: ChartData): string[] =>
  c.labels ?? Array.from({ length: Math.max(...c.datasets.map((d) => d.data.length), 0) }, (_, i) => String(i + 1));

function range(c: ChartData, zero: boolean): [number, number] {
  const all = c.datasets.flatMap(nums);
  const lo = Math.min(...all, zero ? 0 : Infinity);
  return [lo < 0 ? -niceMax(-lo) : 0, niceMax(Math.max(...all, 0))];
}

const line: Painter = (g, w, h, c) => {
  const b = plotBox(w, h);
  const labels = labelsOf(c);
  const [lo, hi] = range(c, true);
  const y = drawAxes(g, b, lo, hi);
  const x = drawXLabels(g, b, labels, false);
  c.datasets.forEach((d, k) => {
    const col = PALETTE[k % PALETTE.length];
    g.strokeStyle = col;
    g.fillStyle = col;
    g.lineWidth = 2;
    g.shadowColor = col;
    g.shadowBlur = 8;
    g.beginPath();
    nums(d).forEach((v, i) => (i ? g.lineTo(x(i), y(v)) : g.moveTo(x(i), y(v))));
    g.stroke();
    g.shadowBlur = 0;
    nums(d).forEach((v, i) => { g.beginPath(); g.arc(x(i), y(v), 3, 0, 7); g.fill(); });
  });
};

const bar: Painter = (g, w, h, c) => {
  const b = plotBox(w, h);
  const labels = labelsOf(c);
  const [lo, hi] = range(c, true);
  const y = drawAxes(g, b, lo, hi);
  const x = drawXLabels(g, b, labels, true);
  const slot = b.w / labels.length;
  const bw = (slot * 0.75) / c.datasets.length;
  c.datasets.forEach((d, k) => {
    g.fillStyle = PALETTE[k % PALETTE.length];
    nums(d).forEach((v, i) => {
      const x0 = x(i) - (bw * c.datasets.length) / 2 + bw * k;
      g.fillRect(x0, Math.min(y(v), y(0)), bw - 1, Math.abs(y(0) - y(v)));
    });
  });
};

const scatter: Painter = (g, w, h, c) => {
  const b = plotBox(w, h);
  const pts = c.datasets.map((d) => d.data.map((p) => (Array.isArray(p) ? [Number(p[0]), Number(p[1])] : [0, Number(p)])));
  const xs = pts.flat().map((p) => p[0]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y = drawAxes(g, b, Math.min(0, ...pts.flat().map((p) => p[1])), niceMax(Math.max(...pts.flat().map((p) => p[1]), 0)));
  const x = (v: number) => b.x + ((v - x0) / (x1 - x0 || 1)) * b.w;
  g.fillStyle = "#8fc7dc";
  g.textAlign = "center";
  g.textBaseline = "top";
  for (let i = 0; i <= 4; i++) g.fillText(String(Math.round((x0 + ((x1 - x0) * i) / 4) * 100) / 100), b.x + (b.w * i) / 4, b.y + b.h + 6);
  pts.forEach((set, k) => {
    g.fillStyle = PALETTE[k % PALETTE.length];
    set.forEach((p) => { g.beginPath(); g.arc(x(p[0]), y(p[1]), 4, 0, 7); g.fill(); });
  });
};

const pie: Painter = (g, w, h, c) => {
  const vals = nums(c.datasets[0] ?? { data: [] }).map((v) => Math.max(v, 0));
  const total = vals.reduce((a, v) => a + v, 0) || 1;
  const r = Math.min(w, h - 30) / 2 - 12;
  const cx = w / 2, cy = h / 2 + 12;
  let a = -Math.PI / 2;
  vals.forEach((v, i) => {
    const da = (v / total) * Math.PI * 2;
    g.fillStyle = PALETTE[i % PALETTE.length];
    g.globalAlpha = 0.85;
    g.beginPath();
    g.moveTo(cx, cy);
    g.arc(cx, cy, r, a, a + da);
    g.fill();
    g.globalAlpha = 1;
    g.strokeStyle = "#02060c";
    g.stroke();
    a += da;
  });
};

const radar: Painter = (g, w, h, c) => {
  const labels = labelsOf(c);
  const n = labels.length;
  const cx = w / 2, cy = h / 2 + 12;
  const r = Math.min(w, h - 30) / 2 - 30;
  const max = niceMax(Math.max(...c.datasets.flatMap(nums), 0));
  const pt = (i: number, f: number): [number, number] => {
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
    return [cx + Math.cos(a) * r * f, cy + Math.sin(a) * r * f];
  };
  g.strokeStyle = "rgba(79,216,255,.18)";
  g.fillStyle = "#8fc7dc";
  g.font = "11px ui-monospace, monospace";
  g.textAlign = "center";
  g.textBaseline = "middle";
  for (let ring = 1; ring <= 4; ring++) {
    g.beginPath();
    for (let i = 0; i < n; i++) g.lineTo(...pt(i, ring / 4));
    g.closePath();
    g.stroke();
  }
  labels.forEach((l, i) => {
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(...pt(i, 1)); g.stroke();
    g.fillText(l, ...pt(i, 1.14));
  });
  c.datasets.forEach((d, k) => {
    g.strokeStyle = g.fillStyle = PALETTE[k % PALETTE.length];
    g.beginPath();
    nums(d).forEach((v, i) => g.lineTo(...pt(i, v / max)));
    g.closePath();
    g.globalAlpha = 0.2; g.fill(); g.globalAlpha = 1;
    g.lineWidth = 2; g.stroke();
  });
};

export const PAINTERS: Record<string, Painter> = { line, bar, scatter, pie, radar };
