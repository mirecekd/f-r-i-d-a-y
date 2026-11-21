// frontend/src/views/dom.ts
/** Tiny element factory. Text always goes through textContent, never innerHTML. */
export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Only http(s), data:image and same-origin paths may be used as image/link targets. */
export function safeUrl(url: unknown, allowDataImage = false): string | null {
  if (typeof url !== "string") return null;
  const u = url.trim();
  if (/^https?:\/\//i.test(u) || /^\/(?!\/)/.test(u)) return u;
  if (allowDataImage && /^data:image\/(png|jpe?g|gif|webp|svg\+xml|bmp);/i.test(u)) return u;
  return null;
}
