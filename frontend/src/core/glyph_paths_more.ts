// frontend/src/core/glyph_paths_more.ts
import type { Draw } from "./glyph_paths";

export type ExtraGlyph = "audio" | "archive" | "tool" | "model" | "note" | "workshop";

/** Glyphs for the 3D entity tiles, on the same 64x64 grid and stroke style as glyph_paths.ts. */
export const EXTRA_PATHS: Record<ExtraGlyph, Draw> = {
  audio(g) {
    g.beginPath(); g.moveTo(10, 26); g.lineTo(20, 26); g.lineTo(32, 16); g.lineTo(32, 48); g.lineTo(20, 38); g.lineTo(10, 38); g.closePath(); g.stroke();
    g.beginPath(); g.arc(34, 32, 9, -1, 1); g.stroke();
    g.beginPath(); g.arc(34, 32, 17, -1, 1); g.stroke();
  },
  archive(g) {
    g.beginPath(); g.roundRect(8, 12, 48, 12, 3); g.stroke();
    g.beginPath(); g.moveTo(12, 24); g.lineTo(12, 52); g.lineTo(52, 52); g.lineTo(52, 24); g.stroke();
    g.beginPath(); g.moveTo(26, 35); g.lineTo(38, 35); g.stroke();
  },
  tool(g) {
    g.beginPath(); g.arc(32, 32, 9, 0, 7); g.stroke();
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4;
      g.beginPath(); g.moveTo(32 + Math.cos(a) * 15, 32 + Math.sin(a) * 15); g.lineTo(32 + Math.cos(a) * 22, 32 + Math.sin(a) * 22); g.stroke();
    }
    g.beginPath(); g.arc(32, 32, 15, 0, 7); g.stroke();
  },
  model(g) {
    g.beginPath(); g.moveTo(32, 8); g.lineTo(54, 20); g.lineTo(54, 44); g.lineTo(32, 56); g.lineTo(10, 44); g.lineTo(10, 20); g.closePath(); g.stroke();
    g.beginPath(); g.moveTo(10, 20); g.lineTo(32, 32); g.lineTo(54, 20); g.moveTo(32, 32); g.lineTo(32, 56); g.stroke();
  },
  workshop(g) {
    g.beginPath(); g.moveTo(8, 28); g.lineTo(56, 28); g.moveTo(12, 28); g.lineTo(12, 52); g.moveTo(52, 28); g.lineTo(52, 52); g.stroke();
    g.beginPath(); g.moveTo(28, 28); g.lineTo(28, 18); g.lineTo(44, 10); g.lineTo(44, 28); g.stroke();
    g.beginPath(); g.arc(20, 20, 5, 0, 7); g.stroke();
  },
  note(g) {
    g.beginPath(); g.roundRect(12, 10, 40, 44, 4); g.stroke();
    g.beginPath(); g.moveTo(20, 22); g.lineTo(44, 22); g.moveTo(20, 31); g.lineTo(44, 31); g.moveTo(20, 40); g.lineTo(36, 40); g.stroke();
  },
};
