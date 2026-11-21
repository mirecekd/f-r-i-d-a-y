// frontend/src/views/exif.ts
import { el } from "./dom";

export interface Exif {
  camera_make?: string;
  camera_model?: string;
  taken_at?: string;
  orientation?: number;
  lat?: number;
  lon?: number;
}

/** OpenStreetMap link for a position; null unless both numbers are finite and in range. */
export function mapLink(lat: unknown, lon: unknown): string | null {
  const a = Number(lat);
  const o = Number(lon);
  if (lat == null || lon == null || !Number.isFinite(a) || !Number.isFinite(o) || Math.abs(a) > 90 || Math.abs(o) > 180) return null;
  return `https://www.openstreetmap.org/?mlat=${a}&mlon=${o}#map=16/${a}/${o}`;
}

/** EXIF facts as small chips (camera, time, GPS link). Text only, never HTML. */
export function exifChips(exif: Exif | undefined | null): HTMLElement[] {
  const chips: HTMLElement[] = [];
  if (!exif) return chips;
  const camera = [exif.camera_make, exif.camera_model].filter((s) => typeof s === "string" && s).join(" ");
  if (camera) chips.push(el("span", "exif-chip", camera));
  if (exif.taken_at) chips.push(el("span", "exif-chip", String(exif.taken_at).replace("T", " ")));
  const link = mapLink(exif.lat, exif.lon);
  if (link) {
    const a = el("a", "exif-chip gps", `GPS ${Number(exif.lat).toFixed(5)}, ${Number(exif.lon).toFixed(5)}`);
    a.href = link;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    chips.push(a);
  }
  return chips;
}
