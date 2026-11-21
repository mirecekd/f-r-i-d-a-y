// frontend/src/views/memory_view.ts
import { mountMemoryGraph, type GraphHandle } from "./memory_graph";
import { parseSearch } from "./memory_hits_logic";
import type { Renderer } from "./types";

const send = (m: { t: string; [k: string]: unknown }): void => (window as any).__friday?.send(m);

/**
 * `memory_graph` renderer. A later `memory_graph` view refreshes the same panel in place (`update`, see ViewHost.show):
 * a query result replaces the graph, a generic overview is cached so "Zrusit hledani" restores it without a server rebuild.
 */
export const renderMemoryGraph: Renderer = async (body, data) => {
  let handle: GraphHandle | null = null;
  let generic: any = parseSearch(data) ? null : data;
  let pending: string | null = null;
  let token = 0;
  let closed = false;

  const mount = async (next: any): Promise<void> => {
    const mine = ++token;
    const full = handle?.isFull() ?? false;
    if (handle) { handle.setFull(false); handle.dispose(); handle = null; }
    const h = await mountMemoryGraph(body, next, { submit, cancel });
    if (closed || mine !== token) return h.dispose(); // closed or superseded while loading
    handle = h;
    if (full) h.setFull(true);
    h.setBusy(pending);
  };
  function submit(query: string): void {
    pending = query;
    handle?.setBusy(query);
    window.setTimeout(() => { if (pending === query) { pending = null; handle?.setBusy(null); } }, 30000); // no answer (backend error): drop the spinner
    send({ t: "memory_search", query });
  }
  function cancel(): boolean {
    const wasPending = pending !== null;
    pending = null;
    handle?.setBusy(null);
    if (handle?.searching) {
      if (generic) void mount(generic);
      else send({ t: "show_memory_graph" }); // the voice path opened the panel with a result: no cached overview
      return true;
    }
    return wasPending;
  }
  await mount(data);
  const cleanup = () => { closed = true; token++; handle?.dispose(); handle = null; };
  cleanup.update = (next: any): void => {
    if (!parseSearch(next)) generic = next;
    pending = null;
    void mount(next);
  };
  return cleanup;
};
