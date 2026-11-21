// frontend/tests/memhits_page/entry.ts
/// <reference types="vite/client" />
import "../../src/views/memory.css";
import { demoSearchGraph } from "../../src/views/memory_demo";
import { buildHitsPanel } from "../../src/views/memory_hits";
import { parseSearch } from "../../src/views/memory_hits_logic";

const w = window as any;
w.picked = [];
w.cancelled = 0;
const state = parseSearch(demoSearchGraph(new URLSearchParams(location.search).get("q") ?? "nginx"))!;
const panel = buildHitsPanel({ pick: (id) => w.picked.push(id), cancel: () => w.cancelled++ });
panel.set(state, state.hits);
document.getElementById("host")!.append(panel.root);
w.panel = panel;
