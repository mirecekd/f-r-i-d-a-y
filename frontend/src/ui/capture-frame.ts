// frontend/src/ui/capture-frame.ts
/** Grab one JPEG frame from a playing <video>: long side <= MAX_SIDE, quality 0.7 lowered until <= MAX_BYTES decoded. */
const MAX_SIDE = 768;
const MAX_BYTES = 350_000;
const QUALITIES = [0.7, 0.6, 0.5, 0.4, 0.3];

const canvas = document.createElement("canvas");

/** Base64 JPEG (no data: prefix) of the current video frame, or null when no picture is ready yet. */
export function grabFrame(video: HTMLVideoElement): string | null {
  const { videoWidth: w, videoHeight: h } = video;
  if (video.readyState < 2 || !w || !h) return null;
  let scale = Math.min(1, MAX_SIDE / Math.max(w, h));
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  for (let shrink = 0; shrink < 3; shrink++, scale *= 0.75) {
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    for (const q of QUALITIES) {
      const b64 = canvas.toDataURL("image/jpeg", q).split(",")[1] ?? "";
      if (b64 && (b64.length * 3) / 4 <= MAX_BYTES) return b64;
    }
  }
  return null;
}
