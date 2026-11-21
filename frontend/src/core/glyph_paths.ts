// frontend/src/core/glyph_paths.ts
export type BaseGlyph = "gantt" | "bubble" | "brain" | "bulb" | "doc" | "book" | "code" | "image" | "table" | "globe";
export type Draw = (g: CanvasRenderingContext2D) => void;

/** Canvas 2D paths on a 64x64 grid, drawn with the stroke style the caller has set. No fonts, no emoji. */
export const BASE_PATHS: Record<BaseGlyph, Draw> = {
  gantt(g) {
    g.beginPath(); g.moveTo(9, 10); g.lineTo(9, 54); g.stroke();
    for (const [x, y, w] of [[15, 14, 22], [25, 27, 28], [19, 40, 20]]) { g.beginPath(); g.roundRect(x, y, w, 9, 3); g.fill(); g.stroke(); }
  },
  bubble(g) {
    g.beginPath(); g.moveTo(14, 12); g.lineTo(50, 12); g.quadraticCurveTo(57, 12, 57, 19); g.lineTo(57, 36);
    g.quadraticCurveTo(57, 43, 50, 43); g.lineTo(30, 43); g.lineTo(18, 54); g.lineTo(19, 43); g.lineTo(14, 43);
    g.quadraticCurveTo(7, 43, 7, 36); g.lineTo(7, 19); g.quadraticCurveTo(7, 12, 14, 12); g.closePath(); g.stroke();
    for (const x of [21, 32, 43]) { g.beginPath(); g.arc(x, 28, 2.2, 0, 7); g.fill(); }
  },
  brain(g) {
    for (const flip of [1, -1]) {
      g.save(); g.translate(32, 0); g.scale(flip, 1); g.translate(-32, 0);
      g.beginPath(); g.moveTo(32, 12); g.bezierCurveTo(26, 5, 13, 9, 15, 20); g.bezierCurveTo(6, 22, 6, 36, 15, 38);
      g.bezierCurveTo(15, 47, 25, 51, 32, 46); g.stroke();
      g.beginPath(); g.moveTo(15, 20); g.quadraticCurveTo(23, 21, 23, 28); g.moveTo(15, 38); g.quadraticCurveTo(24, 37, 25, 31); g.stroke();
      g.restore();
    }
    g.beginPath(); g.moveTo(32, 12); g.lineTo(32, 46); g.moveTo(32, 46); g.lineTo(32, 55); g.stroke();
  },
  bulb(g) {
    g.beginPath(); g.arc(32, 25, 15, Math.PI * 0.78, Math.PI * 0.22); g.lineTo(39, 41); g.lineTo(25, 41); g.closePath(); g.stroke();
    g.beginPath(); g.moveTo(28, 41); g.lineTo(28, 33); g.lineTo(32, 28); g.lineTo(36, 33); g.lineTo(36, 41); g.stroke();
    g.beginPath(); g.moveTo(26, 47); g.lineTo(38, 47); g.moveTo(29, 53); g.lineTo(35, 53); g.stroke();
  },
  doc(g) {
    g.beginPath(); g.moveTo(15, 7); g.lineTo(37, 7); g.lineTo(49, 19); g.lineTo(49, 57); g.lineTo(15, 57); g.closePath(); g.stroke();
    g.beginPath(); g.moveTo(37, 7); g.lineTo(37, 19); g.lineTo(49, 19); g.stroke();
    g.beginPath(); g.moveTo(22, 31); g.lineTo(42, 31); g.moveTo(22, 39); g.lineTo(42, 39); g.moveTo(22, 47); g.lineTo(34, 47); g.stroke();
  },
  book(g) {
    g.beginPath(); g.moveTo(32, 19); g.bezierCurveTo(24, 12, 14, 12, 7, 15); g.lineTo(7, 48); g.bezierCurveTo(14, 45, 24, 45, 32, 52);
    g.bezierCurveTo(40, 45, 50, 45, 57, 48); g.lineTo(57, 15); g.bezierCurveTo(50, 12, 40, 12, 32, 19); g.closePath(); g.stroke();
    g.beginPath(); g.moveTo(32, 19); g.lineTo(32, 52); g.stroke();
  },
  code(g) {
    g.beginPath(); g.moveTo(23, 18); g.lineTo(8, 32); g.lineTo(23, 46); g.moveTo(41, 18); g.lineTo(56, 32); g.lineTo(41, 46); g.moveTo(36, 13); g.lineTo(28, 51); g.stroke();
  },
  image(g) {
    g.beginPath(); g.roundRect(7, 11, 50, 42, 5); g.stroke();
    g.beginPath(); g.arc(22, 24, 5, 0, 7); g.stroke();
    g.beginPath(); g.moveTo(8, 46); g.lineTo(24, 32); g.lineTo(34, 41); g.lineTo(42, 34); g.lineTo(56, 47); g.stroke();
  },
  table(g) {
    g.beginPath(); g.roundRect(7, 11, 50, 42, 4); g.stroke();
    g.beginPath(); g.moveTo(7, 25); g.lineTo(57, 25); g.moveTo(7, 39); g.lineTo(57, 39); g.moveTo(24, 11); g.lineTo(24, 53); g.moveTo(41, 11); g.lineTo(41, 53); g.stroke();
  },
  globe(g) {
    g.beginPath(); g.arc(32, 32, 23, 0, 7); g.stroke();
    g.beginPath(); g.ellipse(32, 32, 10, 23, 0, 0, 7); g.moveTo(9, 32); g.lineTo(55, 32);
    g.moveTo(13, 20); g.quadraticCurveTo(32, 26, 51, 20); g.moveTo(13, 44); g.quadraticCurveTo(32, 38, 51, 44); g.stroke();
  },
};

