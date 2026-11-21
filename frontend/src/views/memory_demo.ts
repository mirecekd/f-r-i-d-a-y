// frontend/src/views/memory_demo.ts
import type { Kind, MemLink, MemNode } from "./memory_orbs";

/** Deterministic synthetic memory graph (no backend): 4 projects, 14 sessions, the rest memories/concepts/files. */
export function demoGraph(total = 150): { nodes: MemNode[]; links: MemLink[] } {
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const now = Date.now();
  const nodes: MemNode[] = [];
  const links: MemLink[] = [];
  const add = (id: string, label: string, kind: Kind, weight: number, project: string): MemNode => {
    const n: MemNode = { id, label, kind, weight, ts: kind === "project" ? 0 : now - Math.floor(rnd() * 30 * 864e5), project };
    nodes.push(n);
    return n;
  };
  const projects = ["FRIDAY", "Dashboard", "Homelab", "Notes"].map((p) => add("p:" + p, p, "project", 1, p));
  const sessions = Array.from({ length: 14 }, (_, i) => {
    const p = projects[i % projects.length];
    const s = add(`s:${i}`, `${p.label} session ${i + 1}`, "session", 0.5 + rnd() * 0.4, p.label);
    links.push({ source: s.id, target: p.id, kind: "in", weight: 0.8 });
    return s;
  });
  const concepts = ["voice", "orbs", "three.js", "mcp", "nginx", "docker", "gemini", "memory", "tests", "wifi"].map((c) =>
    add("c:" + c, c, "concept", 0.35 + rnd() * 0.4, "FRIDAY"),
  );
  const rest = total - nodes.length;
  for (let i = 0; i < rest; i++) {
    const s = sessions[Math.floor(rnd() * sessions.length)];
    if (i % 3 === 0) {
      const f = add(`f:${i}`, `src/${["views", "core", "ui", "audio"][i % 4]}/file${i}.ts`, "file", rnd() * 0.4, s.project);
      links.push({ source: f.id, target: s.id, kind: "seen_in", weight: 0.4 });
    } else {
      const m = add(`m:${i}`, `Decision ${i}: ${["use", "drop", "split", "cache"][i % 4]} ${concepts[i % concepts.length].label}`, "memory", rnd() * 0.7, s.project);
      links.push({ source: m.id, target: s.id, kind: "in", weight: 0.5 });
      links.push({ source: m.id, target: concepts[Math.floor(rnd() * concepts.length)].id, kind: "tagged", weight: 0.5 });
    }
  }
  concepts.forEach((c, i) => links.push({ source: c.id, target: sessions[i % sessions.length].id, kind: "seen_in", weight: 0.6 }));
  return { nodes, links };
}
