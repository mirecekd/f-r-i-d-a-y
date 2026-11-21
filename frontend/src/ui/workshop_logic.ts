// frontend/src/ui/workshop_logic.ts

/** Pure Workshop logic (state reducer, message routing, param throttle, snapshot sizing and encoding, keys); no DOM, so node can test it. */
export type Vec3 = [number, number, number];
export interface Cam { pos: Vec3; look: Vec3 }
export interface WsParam { name: string; label: string; value: number; min: number; max: number; step: number; unit: string }
export interface WsSource { entity_id: string; title: string; kind: string }
export interface WorkshopState {
  open: boolean;
  id: string;
  title: string;
  params: WsParam[];
  sources: WsSource[];
  notes: string[];
  home: Cam | null;
}
type Msg = { t: string; [k: string]: any };

export const EMPTY_STATE: WorkshopState = { open: false, id: "", title: "", params: [], sources: [], notes: [], home: null };
export const HINT = "Hod sem obrazek nebo soubor z Decku a rekni, co mam postavit.";

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const vec3 = (v: unknown): Vec3 | null => (Array.isArray(v) && v.length === 3 && v.every(finite) ? [v[0], v[1], v[2]] : null);

/** A camera pose from the wire format, or null when malformed. */
export function toCam(c: any): Cam | null {
  const pos = vec3(c?.pos);
  const look = vec3(c?.look);
  return pos && look ? { pos, look } : null;
}

/** Wire params cleaned up: unusable entries dropped, missing step derived from the range, value kept inside min..max. */
export function normParams(list: unknown): WsParam[] {
  if (!Array.isArray(list)) return [];
  const out: WsParam[] = [];
  for (const p of list) {
    if (typeof p?.name !== "string" || !p.name || !finite(p.value) || !finite(p.min) || !finite(p.max) || p.max < p.min) continue;
    const step = finite(p.step) && p.step > 0 ? p.step : (p.max - p.min) / 100 || 1;
    out.push({ name: p.name, label: String(p.label ?? p.name), value: Math.min(p.max, Math.max(p.min, p.value)), min: p.min, max: p.max, step, unit: String(p.unit ?? "") });
  }
  return out;
}

const normSources = (list: unknown): WsSource[] =>
  (Array.isArray(list) ? list : []).filter((s) => typeof s?.entity_id === "string").map((s) => ({ entity_id: s.entity_id, title: String(s.title ?? s.entity_id), kind: String(s.kind ?? "") }));
const normNotes = (list: unknown): string[] => (Array.isArray(list) ? list.filter((n) => typeof n === "string" && n) : []);

/** Folds one server `workshop` message into the state. `fallbackHome` is the camera at the moment of entering (used when the server sends none). */
export function reduce(state: WorkshopState, m: Msg, fallbackHome: Cam | null = null): WorkshopState {
  if (m.t !== "workshop") return state;
  if (m.op === "enter" && typeof m.id === "string") {
    return {
      open: true, id: m.id, title: String(m.title ?? ""), params: normParams(m.params), sources: normSources(m.sources),
      notes: normNotes(m.notes), home: toCam(m.home) ?? (state.open ? state.home : fallbackHome),
    };
  }
  if (!state.open || m.id !== state.id) return state;
  if (m.op === "params") return { ...state, params: normParams(m.params), notes: normNotes(m.notes) };
  if (m.op === "leave") return { ...EMPTY_STATE, home: state.home };
  return state;
}

/** Where the camera goes on leave: the server's pose, else the remembered home. */
export function leaveCam(state: WorkshopState, m: Msg): Cam | null {
  return toCam(m.camera) ?? state.home;
}

export type Route = "state" | "snapshot" | "ignore";
export function routeServerMessage(m: Msg): Route {
  if (m.t === "workshop") return "state";
  if (m.t === "workshop_snapshot_request") return "snapshot";
  return "ignore";
}

/** True when both lists have the same sliders (name, label, range, step), so the DOM can be updated in place instead of rebuilt. */
export function sameParamShape(a: WsParam[], b: WsParam[]): boolean {
  return a.length === b.length && a.every((p, i) => p.name === b[i].name && p.label === b[i].label && p.min === b[i].min && p.max === b[i].max && p.step === b[i].step && p.unit === b[i].unit);
}

export const showHint = (s: WorkshopState): boolean => s.params.length === 0 && s.sources.length === 0;

/** Number text with only the decimals the step needs. */
export function formatValue(v: number, step: number): string {
  const decimals = Math.min(4, Math.max(0, Math.ceil(-Math.log10(step) - 1e-9)));
  return v.toFixed(decimals);
}

/** Parsed and clamped value of a numeric field, or null when the text is not a number. */
export function parseField(text: string, p: Pick<WsParam, "min" | "max">): number | null {
  const v = Number(text.replace(",", "."));
  return text.trim() !== "" && Number.isFinite(v) ? Math.min(p.max, Math.max(p.min, v)) : null;
}

export type KeyAction = "toggle" | "leave" | null;
/** W toggles the workshop, Esc leaves it (only when nothing else - dropdown, dialog, chat, deck - wants the key). */
export function workshopKeyAction(e: { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; defaultPrevented: boolean }, ctx: { open: boolean; typing: boolean; blocked: boolean }): KeyAction {
  if (e.ctrlKey || e.metaKey || e.altKey || ctx.blocked) return null;
  if (e.key === "Escape") return ctx.open && !e.defaultPrevented ? "leave" : null;
  return (e.key === "w" || e.key === "W") && !ctx.typing && !e.defaultPrevented ? "toggle" : null;
}

/** The message for the W key: leave when inside; else open the selected workshop tile, the last visited workshop or a new one. */
export function toggleMessage(state: WorkshopState, selectedWorkshopId: string | null, lastId: string | null): Msg {
  if (state.open) return { t: "workshop_leave" };
  const id = selectedWorkshopId ?? lastId;
  return id ? { t: "workshop_open", id } : { t: "workshop_new" };
}

export const dropChatText = (title: string, id: string): string => `Pridej do dilny ${title} (${id})`;
export const removeSourceText = (title: string): string => `Odeber zdroj ${title} z dilny`;
