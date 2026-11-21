// frontend/src/ui/deck_url.ts
import type { Net } from "../net";
import { el } from "../views/dom";

/** Normalises what the user pasted into an http(s) URL, or null (the server checks it again and refuses private addresses). */
export function parseLinkInput(text: string): string | null {
  const t = text.trim();
  if (!t || /\s/.test(t) || t.length > 2048) return null;
  const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(t) ? t : `https://${t}`;
  try {
    const u = new URL(withScheme);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** The small 'Pridat odkaz' input of the Deck top bar: paste a URL, press Enter, the server fetches it (web_add). */
export function linkInput(net: Net): HTMLInputElement {
  const input = el("input", "dk-search dk-link");
  input.type = "url";
  input.placeholder = "Pridat odkaz...";
  input.setAttribute("aria-label", "Pridat odkaz");
  input.onkeydown = (e) => {
    if (e.key !== "Enter") return;
    const url = parseLinkInput(input.value);
    input.classList.toggle("bad", url === null);
    if (url === null) return;
    net.send({ t: "web_add", url });
    input.value = "";
  };
  return input;
}
