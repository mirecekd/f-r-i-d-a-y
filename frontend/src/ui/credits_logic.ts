// frontend/src/ui/credits_logic.ts
/** Pure helpers of the model credits list (no DOM, testable with node --experimental-strip-types). */

export interface Credit { name: string; author: string; license: string; source_page: string }

const MAX_ITEMS = 500;

function text(v: unknown, max = 200): string {
  return typeof v === "string" ? v.slice(0, max) : "";
}

/** Keeps only well-formed credit rows from an `assets` message; the source link only when it is https. */
export function parseCredits(items: unknown): Credit[] {
  if (!Array.isArray(items)) return [];
  const out: Credit[] = [];
  for (const raw of items.slice(0, MAX_ITEMS)) {
    if (typeof raw !== "object" || raw === null) continue;
    const r = raw as Record<string, unknown>;
    const name = text(r.name);
    if (!name) continue;
    const page = text(r.source_page, 500);
    out.push({ name, author: text(r.author), license: text(r.license), source_page: /^https:\/\//i.test(page) ? page : "" });
  }
  return out;
}

export function summaryLabel(count: number): string {
  if (count === 0) return "Zatim zadne";
  return count === 1 ? "1 model" : count < 5 ? `${count} modely` : `${count} modelu`;
}
