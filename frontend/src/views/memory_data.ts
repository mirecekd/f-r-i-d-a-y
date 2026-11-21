// frontend/src/views/memory_data.ts
import { KINDS_ORDER, type MemLink, type MemNode } from "./memory_orbs";

/** Validates the wire payload (see docs/protocol.md): unknown kinds become concepts, dangling links are dropped. */
export function cleanGraph(data: any): { nodes: MemNode[]; links: MemLink[] } {
  const nodes: MemNode[] = (Array.isArray(data?.nodes) ? data.nodes : []).map((n: any) => ({
    id: String(n.id),
    label: String(n.label ?? n.id),
    kind: (KINDS_ORDER as string[]).includes(n.kind) ? n.kind : "concept",
    weight: Math.max(0, Math.min(1, Number(n.weight) || 0)),
    ts: Number(n.ts) || 0,
    project: String(n.project ?? ""),
  }));
  const ids = new Set(nodes.map((n) => n.id));
  const links: MemLink[] = (Array.isArray(data?.links) ? data.links : [])
    .filter((l: any) => ids.has(String(l.source)) && ids.has(String(l.target)))
    .map((l: any) => ({ source: String(l.source), target: String(l.target), kind: String(l.kind ?? ""), weight: Number(l.weight) || 0.3 }));
  return { nodes, links };
}

export function adjacency(nodes: MemNode[], links: MemLink[]): Map<string, Set<string>> {
  const adj = new Map<string, Set<string>>(nodes.map((n) => [n.id, new Set<string>()]));
  for (const l of links) {
    adj.get(l.source as string)!.add(l.target as string);
    adj.get(l.target as string)!.add(l.source as string);
  }
  return adj;
}
