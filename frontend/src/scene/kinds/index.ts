// frontend/src/scene/kinds/index.ts
import type { Kind } from "../types";
import { PRIMITIVES, GROUP } from "./primitives";
import { TEXT, LABEL } from "./text";
import { LINE, POLYLINE, ARROW } from "./lines";
import { PARTICLES } from "./particles";
import { GRAPH } from "./graph";
import { CHART3D } from "./chart";
import { SURFACE } from "./surface";
import { EXTRUDE } from "./extrude";
import { CSG } from "./csg";
import { IMAGE, GLTF } from "./media";

export const KINDS: Record<string, Kind> = {
  ...PRIMITIVES,
  group: GROUP,
  text: TEXT,
  label: LABEL,
  line: LINE,
  polyline: POLYLINE,
  arrow: ARROW,
  particles: PARTICLES,
  image: IMAGE,
  graph: GRAPH,
  chart3d: CHART3D,
  surface: SURFACE,
  gltf: GLTF,
  extrude: EXTRUDE,
  csg: CSG,
};
