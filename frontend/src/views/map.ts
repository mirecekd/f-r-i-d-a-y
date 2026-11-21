// frontend/src/views/map.ts
import "./content.css";
import { el } from "./dom";
import type { Renderer } from "./types";

const TILE = 256;
const GRID = 3;
const MAX_ZOOM = 18;

interface Marker { lat: number; lon: number; label?: string }

/** Web-mercator world pixel coordinates at a zoom level. */
function project(lat: number, lon: number, z: number): [number, number] {
  const s = TILE * 2 ** z;
  const sin = Math.sin((Math.max(-85.05, Math.min(85.05, lat)) * Math.PI) / 180);
  return [((lon + 180) / 360) * s, (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * s];
}

/**
 * data: `{center: [lat, lon], zoom?: 0-18, markers?: [{lat, lon, label?}]}`.
 * Renders a 3x3 grid of static OpenStreetMap tiles centred on `center`; markers are DOM overlays.
 */
export const renderMap: Renderer = (body, data) => {
  const c = data?.center;
  if (!Array.isArray(c) || c.length !== 2 || c.some((v) => typeof v !== "number")) throw new Error("map: center [lat, lon] required");
  const z = Math.max(0, Math.min(MAX_ZOOM, Math.round(Number(data.zoom ?? 12))));
  const markers: Marker[] = Array.isArray(data.markers) ? data.markers : [];
  const [cx, cy] = project(c[0], c[1], z);
  const n = 2 ** z;

  const view = el("div", "v-map");
  const stage = el("div", "v-map-stage");
  // Stage is TILE*GRID px, positioned so (cx, cy) sits at the view centre.
  const originX = Math.floor(cx / TILE) - 1;
  const originY = Math.floor(cy / TILE) - 1;
  stage.style.width = stage.style.height = `${TILE * GRID}px`;
  stage.style.left = `calc(50% - ${cx - originX * TILE}px)`;
  stage.style.top = `calc(50% - ${cy - originY * TILE}px)`;
  for (let ty = 0; ty < GRID; ty++) {
    for (let tx = 0; tx < GRID; tx++) {
      const wy = originY + ty;
      if (wy < 0 || wy >= n) continue;
      const wx = ((originX + tx) % n + n) % n;
      const img = el("img");
      img.src = `https://tile.openstreetmap.org/${z}/${wx}/${wy}.png`;
      img.referrerPolicy = "no-referrer";
      img.draggable = false;
      img.style.left = `${tx * TILE}px`;
      img.style.top = `${ty * TILE}px`;
      stage.append(img);
    }
  }
  for (const m of markers) {
    if (typeof m?.lat !== "number" || typeof m?.lon !== "number") continue;
    const [px, py] = project(m.lat, m.lon, z);
    const pin = el("div", "v-pin");
    pin.style.left = `${px - originX * TILE}px`;
    pin.style.top = `${py - originY * TILE}px`;
    if (m.label) pin.append(el("span", "", String(m.label)));
    stage.append(pin);
  }
  view.append(stage, el("div", "v-attrib", "\u00A9 OpenStreetMap contributors"));
  body.append(view);
};
