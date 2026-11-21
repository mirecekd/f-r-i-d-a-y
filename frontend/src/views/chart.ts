// frontend/src/views/chart.ts
import "./content.css";
import { el } from "./dom";
import { drawLegend, type ChartData } from "./chart-draw";
import { PAINTERS } from "./chart-kinds";
import type { Renderer } from "./types";

/** data: `{type: line|bar|pie|scatter|radar, labels?: string[], datasets: [{label?, data: number[] | [x,y][]}]}` */
export const renderChart: Renderer = (body, data) => {
  const c = data as ChartData;
  const paint = PAINTERS[c?.type];
  if (!paint) throw new Error(`chart: unknown type ${String(c?.type)}`);
  if (!Array.isArray(c.datasets) || !c.datasets.length) throw new Error("chart: datasets missing");
  const wrap = el("div", "v-chart");
  const canvas = el("canvas");
  wrap.append(canvas);
  body.append(wrap);

  const draw = () => {
    const w = wrap.clientWidth, h = wrap.clientHeight;
    if (w < 20 || h < 20) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const g = canvas.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    paint(g, w, h, c);
    const names = c.type === "pie" ? c.labels : undefined;
    drawLegend(g, w, c.datasets, names);
  };
  const ro = new ResizeObserver(draw);
  ro.observe(wrap);
  return () => ro.disconnect();
};
