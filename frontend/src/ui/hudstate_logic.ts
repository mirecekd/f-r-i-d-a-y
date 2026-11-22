// frontend/src/ui/hudstate_logic.ts
// Pure logic of the task-state line: tool name -> category -> Czech label, and the show / hide timing.

export type Category = "search" | "memory" | "files" | "images" | "building" | "tool" | "work";

export const LABELS: Record<Category, string> = {
  search: "Hledam",
  memory: "Vzpominam",
  files: "Pracuji se soubory",
  images: "Divam se na obrazky",
  building: "Stavim",
  tool: "Volam nastroj",
  work: "Pracuji",
};

export const MIN_SHOW_MS = 600; // a label stays at least this long, so bursts of fast tools do not flicker
export const FADE_AFTER_MS = 1500; // the line fades out this long after the last tool ended

// First matching rule wins. Matched against the name's tokens by prefix, never against a fixed list of tools.
const RULES: [Category, RegExp][] = [
  ["tool", /^(mcp|hermes|ask)$|__/],
  ["memory", /^(memory|memories|remember|recall|digest)/],
  ["search", /^(search|web|google|find)/],
  ["images", /^(image|img|vision|photo|picture|house|analyze)/],
  ["files", /^(deck|entity|entities|file|files|read|list|summarize)$|^(deck|entit|file)/],
  ["building", /^(model|pack|workshop|scene|draw|show|close|selected)/],
];

export function categoryOf(toolName: string): Category {
  const name = String(toolName || "").toLowerCase();
  if (/__/.test(name)) return "tool";
  const tokens = name.split(/[^a-z0-9]+/).filter(Boolean);
  for (const [cat, rule] of RULES) if (tokens.some((t) => rule.test(t))) return cat;
  return "work";
}

export const labelOf = (toolName: string): string => LABELS[categoryOf(toolName)];

export interface HudView { label: string | null }

/** Tracks running tools; `view(now)` says which label to show (null = hidden). Time is passed in, so it is testable. */
export class HudStateModel {
  private active = new Map<string, string>(); // call id -> label
  private shown: string | null = null;
  private shownSince = 0;
  private lastEnd = -Infinity;
  private latest: string | null = null;

  start(id: string, name: string, now: number): void {
    const label = labelOf(name);
    this.active.set(id, label);
    this.latest = label;
    if (this.shown === null) this.show(label, now);
  }

  end(id: string, now: number): void {
    if (!this.active.delete(id)) return;
    this.lastEnd = now;
    if (this.active.size) this.latest = [...this.active.values()].at(-1) ?? this.latest;
  }

  /** Milliseconds until `view` could change on its own, or null when nothing is pending. */
  nextChangeIn(now: number): number | null {
    if (this.shown === null) return null;
    const wait = (until: number): number => Math.max(0, until - now);
    const swapAt = this.shownSince + MIN_SHOW_MS;
    if (this.latest !== this.shown) return wait(swapAt);
    if (this.active.size) return null;
    return wait(Math.max(this.lastEnd + FADE_AFTER_MS, swapAt));
  }

  view(now: number): HudView {
    if (this.shown === null) return { label: null };
    if (this.latest !== null && this.latest !== this.shown && now - this.shownSince >= MIN_SHOW_MS) this.show(this.latest, now);
    if (!this.active.size && now - this.lastEnd >= FADE_AFTER_MS && now - this.shownSince >= MIN_SHOW_MS) this.shown = null;
    return { label: this.shown };
  }

  private show(label: string, now: number): void {
    this.shown = label;
    this.shownSince = now;
  }
}
