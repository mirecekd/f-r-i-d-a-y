// frontend/src/views/image.ts
import "./content.css";
import { el, safeUrl } from "./dom";
import type { Renderer } from "./types";

/** data: `{url, alt?, caption?}`; url is http(s), a same-origin path, or a data:image URI. */
export const renderImage: Renderer = (body, data) => {
  const url = safeUrl(data?.url, true);
  if (!url) throw new Error("image: missing or unsafe url");
  const wrap = el("div", "v-image");
  const img = el("img");
  img.src = url;
  img.alt = String(data.alt ?? "");
  img.referrerPolicy = "no-referrer";
  img.onerror = () => wrap.replaceChildren(el("div", "vp-err", "image failed to load"));
  img.onclick = () => wrap.classList.toggle("actual");
  wrap.append(img);
  if (data.caption) wrap.append(el("div", "v-caption", String(data.caption)));
  body.append(wrap);
};
