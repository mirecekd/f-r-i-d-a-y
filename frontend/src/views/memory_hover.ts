// frontend/src/views/memory_hover.ts

const REST_MS = 120; // cursor must rest on the same node this long before it dims the rest
const QUIET_MS = 250; // no hover effect while interacting and this long after the last wheel event

export interface HoverGate<T> {
  /** Raw hover from the graph library: the node under the cursor, or null. */
  set(node: T | null): void;
  /** A wheel/pinch/drag is in progress: drop the effect now and hold it back. */
  interact(): void;
  /** Pointer press/release on the canvas (drag, pinch): effect stays off while any pointer is down. */
  pointers(down: boolean): void;
  dispose(): void;
}

/** Debounces node hover: `apply` runs only after the cursor rests on a node and never during camera interaction. */
export function createHoverGate<T>(apply: (node: T | null) => void): HoverGate<T> {
  let raw: T | null = null;
  let shown: T | null = null;
  let timer = 0;
  let quietAt = 0;
  let down = 0;
  const show = (n: T | null) => { if (n !== shown) { shown = n; apply(n); } };
  const busy = () => down > 0 || performance.now() < quietAt;
  const schedule = () => {
    clearTimeout(timer);
    if (raw === shown) return;
    const wait = Math.max(REST_MS, quietAt - performance.now());
    timer = window.setTimeout(() => (busy() ? schedule() : show(raw)), wait);
  };
  return {
    set(n) { raw = n; schedule(); },
    interact() { quietAt = performance.now() + QUIET_MS; show(null); schedule(); },
    pointers(isDown) {
      down = Math.max(0, down + (isDown ? 1 : -1));
      if (isDown) show(null);
      else quietAt = performance.now() + QUIET_MS;
      schedule();
    },
    dispose() { clearTimeout(timer); },
  };
}
