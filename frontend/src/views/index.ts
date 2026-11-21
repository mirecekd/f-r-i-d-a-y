// frontend/src/views/index.ts
import { renderChart } from "./chart";
import { renderCode } from "./code";
import { renderDiagram } from "./diagram";
import { renderFileCard } from "./file_card";
import { renderImage } from "./image";
import { renderImageCard } from "./image_card";
import { renderJson } from "./json";
import { renderMap } from "./map";
import { renderMarkdown } from "./markdown";
import { renderTable } from "./table";
import type { ViewKind } from "./types";

/** Registry of view kinds; the key is the `kind` field of the `view` message. */
export const KINDS: Record<string, ViewKind> = {
  image: { render: renderImage, size: [380, 300] },
  image_card: { render: renderImageCard, size: [400, 600] },
  file_card: { render: renderFileCard, size: [420, 620] },
  chart: { render: renderChart, size: [420, 300] },
  table: { render: renderTable, size: [420, 240] },
  markdown: { render: renderMarkdown, size: [380, 300] },
  code: { render: renderCode, size: [440, 280] },
  diagram: { render: renderDiagram, size: [440, 320] },
  map: { render: renderMap, size: [420, 320] },
  json: { render: renderJson, size: [340, 280] },
  // Whole module (and 3d-force-graph) is loaded on first use to keep the main bundle small.
  memory_graph: { render: (body, data) => import("./memory_view").then((m) => m.renderMemoryGraph(body, data)), size: [560, 420] },
};
