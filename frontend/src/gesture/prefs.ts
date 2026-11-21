// frontend/src/gesture/prefs.ts - persisted gesture settings (localStorage `friday.gestures`).
const KEY = "friday.gestures";

export interface GesturePrefs { enabled: boolean; stop: boolean; preview: boolean; seenHint: boolean }

const DEFAULTS: GesturePrefs = { enabled: false, stop: false, preview: true, seenHint: false };

export function loadPrefs(): GesturePrefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
  } catch {
    return { ...DEFAULTS };
  }
}

export function savePrefs(p: GesturePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* storage may be unavailable (private mode): the setting then lasts for this page only */
  }
}
