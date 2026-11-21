// frontend/src/ui/imageprep.ts

export const ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp", "image/gif"];
export const MAX_BYTES = 12 * 1024 * 1024;
const DOWNSCALE_OVER = 6 * 1024 * 1024;
const MAX_SIDE = 2400;

export interface Prepared {
  name: string;
  mime: string;
  blob: Blob;
  /** True when the picture was re-encoded on a canvas, which drops EXIF including GPS. */
  downscaled: boolean;
}

/** Message for an unusable file, or null when it may be sent. */
export function validate(file: File): string | null {
  if (!ALLOWED_MIME.includes(file.type)) return `Nepodporovany format (${file.type || "neznamy"}); jen JPEG, PNG, WebP a GIF.`;
  if (file.size > MAX_BYTES) return `Obrazek je moc velky (${(file.size / 1048576).toFixed(1)} MB, limit 12 MB).`;
  return null;
}

function hasAlpha(ctx: CanvasRenderingContext2D, w: number, h: number): boolean {
  const px = ctx.getImageData(0, 0, w, h).data;
  for (let i = 3; i < px.length; i += 4) if (px[i] < 255) return true;
  return false;
}

/** Files over 6 MB are scaled to 2400 px and re-encoded (jpeg 0.9, png only with transparency); smaller ones pass untouched. */
export async function prepare(file: File): Promise<Prepared> {
  if (file.size <= DOWNSCALE_OVER) return { name: file.name, mime: file.type, blob: file, downscaled: false };
  const bmp = await createImageBitmap(file);
  const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
  const w = Math.max(1, Math.round(bmp.width * k));
  const h = Math.max(1, Math.round(bmp.height * k));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  const png = file.type === "image/png" && hasAlpha(ctx, w, h);
  const mime = png ? "image/png" : "image/jpeg";
  const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, mime, 0.9));
  if (!blob) throw new Error("prekodovani obrazku selhalo");
  const base = file.name.replace(/\.[^.]+$/, "") || "obrazek";
  return { name: `${base}.${png ? "png" : "jpg"}`, mime, blob, downscaled: true };
}

/** Base64 payload of a blob without the data: prefix. */
export function toBase64(blob: Blob): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => rej(r.error);
    r.readAsDataURL(blob);
  });
}

/** RFC 4122 v4 id; randomUUID needs a secure context, which a LAN tablet over http does not have. */
export function newId(): string {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
