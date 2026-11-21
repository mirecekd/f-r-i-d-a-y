// frontend/src/views/memory_filters.ts
import { KINDS_ORDER, type Kind } from "./memory_orbs";

export type TimeRange = "all" | "30d" | "7d" | "24h" | "today";
export type LabelMode = "auto" | "always" | "never";
export type PresetId = "overview" | "all" | "focus" | "custom";

export interface FilterState {
  v: 1;
  preset: PresetId;
  kinds: Record<Kind, boolean>;
  hiddenProjects: string[];
  time: TimeRange;
  hiddenLinks: string[];
  hideOrphans: boolean;
  focusDepth: 0 | 1 | 2; // 0 = off; otherwise only the neighbourhood of the selected node
  labels: LabelMode;
  particles: boolean;
  sizeByWeight: boolean;
  autoRotate: boolean;
  nodeSize: number; // 0.5 .. 2
  frozen: boolean;
}

export const FILTER_KEY = "friday.memory.filters";
export const TIME_RANGES: [TimeRange, string][] = [["all", "Vse"], ["30d", "30 dni"], ["7d", "7 dni"], ["24h", "24 h"], ["today", "Dnes"]];
export const LABEL_MODES: [LabelMode, string][] = [["auto", "Auto"], ["always", "Vzdy"], ["never", "Nikdy"]];
export const PRESETS: [Exclude<PresetId, "custom">, string][] = [["overview", "Prehled"], ["all", "Vse"], ["focus", "Soustredit"]];

const kindsOn = (...on: Kind[]): Record<Kind, boolean> => Object.fromEntries(KINDS_ORDER.map((k) => [k, on.includes(k)])) as Record<Kind, boolean>;

/** Display options (labels aside) are not touched by presets. */
const DISPLAY = { particles: true, sizeByWeight: true, autoRotate: true, nodeSize: 1, frozen: false };

const BASE: FilterState = {
  v: 1, preset: "overview", kinds: kindsOn("project", "memory", "concept"), hiddenProjects: [], time: "30d", hiddenLinks: [],
  hideOrphans: true, focusDepth: 0, labels: "auto", ...DISPLAY,
};

export const defaultFilters = (): FilterState => ({ ...BASE, kinds: { ...BASE.kinds } });

/** Preset values replace the data filters; the display options of `s` are kept. */
export function withPreset(s: FilterState, id: Exclude<PresetId, "custom">): FilterState {
  const d = defaultFilters();
  const data = { ...d, hiddenProjects: [], hiddenLinks: [], preset: id };
  if (id === "all") Object.assign(data, { kinds: kindsOn(...KINDS_ORDER), time: "all", hideOrphans: false });
  if (id === "focus") Object.assign(data, { kinds: kindsOn(...KINDS_ORDER), time: "all", focusDepth: 2 });
  const { particles, sizeByWeight, autoRotate, nodeSize, frozen } = s;
  return { ...data, particles, sizeByWeight, autoRotate, nodeSize, frozen };
}

const strList = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, 500) : []);
const oneOf = <T extends string>(v: unknown, allowed: readonly T[], d: T): T => (allowed.includes(v as T) ? (v as T) : d);
const bool = (v: unknown, d: boolean): boolean => (typeof v === "boolean" ? v : d);

/** Defensive parse of whatever localStorage holds; unknown version or garbage gives the defaults. */
export function sanitizeFilters(raw: unknown): FilterState {
  const d = defaultFilters();
  const r = raw as Partial<FilterState> | null;
  if (!r || typeof r !== "object" || r.v !== 1) return d;
  const k = (r.kinds ?? {}) as Partial<Record<Kind, unknown>>;
  const size = Number(r.nodeSize);
  return {
    v: 1,
    preset: oneOf(r.preset, ["overview", "all", "focus", "custom"] as const, d.preset),
    kinds: Object.fromEntries(KINDS_ORDER.map((x) => [x, bool(k[x], d.kinds[x])])) as Record<Kind, boolean>,
    hiddenProjects: strList(r.hiddenProjects),
    time: oneOf(r.time, TIME_RANGES.map((t) => t[0]), d.time),
    hiddenLinks: strList(r.hiddenLinks),
    hideOrphans: bool(r.hideOrphans, d.hideOrphans),
    focusDepth: r.focusDepth === 1 || r.focusDepth === 2 ? r.focusDepth : 0,
    labels: oneOf(r.labels, LABEL_MODES.map((t) => t[0]), d.labels),
    particles: bool(r.particles, d.particles),
    sizeByWeight: bool(r.sizeByWeight, d.sizeByWeight),
    autoRotate: bool(r.autoRotate, d.autoRotate),
    nodeSize: Number.isFinite(size) ? Math.max(0.5, Math.min(2, size)) : 1,
    frozen: bool(r.frozen, d.frozen),
  };
}

export function loadFilters(): FilterState {
  try {
    return sanitizeFilters(JSON.parse(localStorage.getItem(FILTER_KEY) ?? "null"));
  } catch {
    return defaultFilters();
  }
}

export function saveFilters(s: FilterState): void {
  try {
    localStorage.setItem(FILTER_KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable: settings last for this session only */
  }
}
