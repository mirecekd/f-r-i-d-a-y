// frontend/src/ui/workshop_throttle.ts

export const PARAM_SEND_PER_SECOND = 12;

/** Latest-wins throttle per parameter name: the first change goes out at once, later ones at most PARAM_SEND_PER_SECOND times a second, the last value always arrives. */
export class ParamThrottle {
  private last = new Map<string, number>();
  private pending = new Map<string, number>();
  private timers = new Map<string, unknown>();

  private send: (name: string, value: number) => void;
  private now: () => number;
  private later: (fn: () => void, ms: number) => unknown;
  private cancel: (handle: unknown) => void;
  private gapMs: number;

  constructor(
    send: (name: string, value: number) => void,
    now: () => number,
    later: (fn: () => void, ms: number) => unknown,
    cancel: (handle: unknown) => void,
    gapMs = 1000 / PARAM_SEND_PER_SECOND,
  ) {
    this.send = send; this.now = now; this.later = later; this.cancel = cancel; this.gapMs = gapMs;
  }

  push(name: string, value: number): void {
    const wait = this.gapMs - (this.now() - (this.last.get(name) ?? -Infinity));
    if (wait <= 0 && !this.timers.has(name)) return this.emit(name, value);
    this.pending.set(name, value);
    if (!this.timers.has(name)) this.timers.set(name, this.later(() => { this.timers.delete(name); this.flush(name); }, Math.max(wait, 0)));
  }

  /** Sends the held value of `name` (or of every name) now. */
  flush(name?: string): void {
    for (const n of name ? [name] : [...this.pending.keys()]) {
      const t = this.timers.get(n);
      if (t !== undefined) { this.cancel(t); this.timers.delete(n); }
      const v = this.pending.get(n);
      if (v !== undefined) this.emit(n, v);
    }
  }

  private emit(name: string, value: number): void {
    this.pending.delete(name);
    this.last.set(name, this.now());
    this.send(name, value);
  }
}
