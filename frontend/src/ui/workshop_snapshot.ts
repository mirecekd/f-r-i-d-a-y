// frontend/src/ui/workshop_snapshot.ts

/** Pure snapshot sizing and encoding loop (no DOM, so node can test it). */
export const MAX_SNAPSHOT_BYTES = 800_000;
export const MAX_SNAPSHOT_WIDTH = 1024;

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Snapshot size: at most `maxWidth` wide (never upscaled, capped at MAX_SNAPSHOT_WIDTH), aspect kept, at least 1 px. */
export function snapshotSize(srcW: number, srcH: number, maxWidth: number): { w: number; h: number } {
  const cap = Math.min(finite(maxWidth) && maxWidth > 0 ? maxWidth : MAX_SNAPSHOT_WIDTH, MAX_SNAPSHOT_WIDTH);
  const s = Math.min(1, cap / Math.max(1, srcW));
  return { w: Math.max(1, Math.round(srcW * s)), h: Math.max(1, Math.round(srcH * s)) };
}

/** Decoded byte size of the base64 part of a data URL. */
export function dataUrlBytes(url: string): number {
  const b64 = url.slice(url.indexOf(",") + 1);
  return Math.floor((b64.length * 3) / 4) - (b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0);
}

const QUALITIES = [0.8, 0.6, 0.45, 0.3];
const WIDTH_STEPS = [1, 0.75, 0.5];

/** Renders at `width`, encodes at falling quality and then falls back to narrower renders until the JPEG fits `maxBytes`; returns its base64 or null. */
export function encodeSnapshot<C>(render: (width: number) => C, encode: (canvas: C, quality: number) => string, width: number, maxBytes = MAX_SNAPSHOT_BYTES): string | null {
  for (const k of WIDTH_STEPS) {
    const canvas = render(Math.max(1, Math.round(width * k)));
    for (const q of QUALITIES) {
      const url = encode(canvas, q);
      if (dataUrlBytes(url) <= maxBytes) return url.slice(url.indexOf(",") + 1);
    }
  }
  return null;
}
