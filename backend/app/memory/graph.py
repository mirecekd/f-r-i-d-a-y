# backend/app/memory/graph.py
"""Graph of agentmemory for the memory orbs: nodes {id,label,kind,weight,ts,project}, links {source,target,kind,weight}.

Endpoints: POST /graph/query (knowledge-graph nodes+edges), GET /observations/locate (node -> session),
GET /sessions, GET /memories. Cached for 60 s (stale-while-revalidate); capped at MAX_NODES with the newest/heaviest first.
"""

import asyncio
import time

from app.memory import awareness, client, fetch

MAX_NODES = 300
CACHE_S = 60  # freshness target: an older graph is served at once and rebuilt in the background
STALE_MAX_S = 3600  # beyond this the caller waits for a rebuild
SESSION_DAYS = 3
LOCATE_CHUNK = 60
GRAPH_FETCH = 500  # the server caps /graph/query at 500 nodes per call
_cache: dict[str, tuple[float, dict]] = {}
_inflight: dict[str, asyncio.Task] = {}

_KIND = {"file": "file"}  # every other graph node type (concept, decision, library, ...) is a concept


def _ms(iso: object) -> int:
    return int(fetch.parse_ts(iso) * 1000)


def _norm(n: float, top: float) -> float:
    return round(min(1.0, n / top), 3)


Nodes = dict[str, dict]


def _add(nodes: Nodes, id_: str, label: str, kind: str, weight: float, ts: int, project: str) -> None:
    nodes.setdefault(id_, {"id": id_, "label": label[:80], "kind": kind, "weight": weight, "ts": ts, "project": project})


def _link(source: str, target: str, kind: str, weight: float) -> dict:
    return {"source": source, "target": target, "kind": kind, "weight": weight}


def _structure(nodes: Nodes, links: list[dict], sessions: list[dict], memories: list[dict]) -> None:
    """Project, session and memory nodes with their `in` links."""
    for s in sessions:
        project = s.get("project") or "?"
        _add(nodes, f"project:{project}", project, "project", 1.0, 0, project)
        sid = f"session:{s['id']}"
        _add(nodes, sid, f"{project} {awareness.short_id(s)}", "session",
             _norm(s.get("observationCount") or 0, 200), _ms(s.get("startedAt")), project)
        links.append(_link(sid, f"project:{project}", "in", 1.0))
    for m in memories:
        project = m.get("project") or ""
        _add(nodes, m["id"], str(m.get("title") or m["id"]), "memory",
             _norm(m.get("strength") or 1, 10), _ms(m.get("createdAt")), project)
        if project:
            _add(nodes, f"project:{project}", project, "project", 1.0, 0, project)
            links.append(_link(m["id"], f"project:{project}", "in", 1.0))


async def _locate(gnodes: list[dict]) -> dict[str, str]:
    """observation id -> session id for the first observation of each graph node."""
    ids = sorted({n["sourceObservationIds"][0] for n in gnodes if n.get("sourceObservationIds")})
    found: dict[str, str] = {}
    for i in range(0, len(ids), LOCATE_CHUNK):  # keeps the query string short
        data = await client.request("GET", "/observations/locate", {"ids": ",".join(ids[i : i + LOCATE_CHUNK])})
        found |= data.get("sessions") or {}
    return found


async def _knowledge(nodes: Nodes, links: list[dict], gq: dict, sessions: list[dict]) -> None:
    """Knowledge-graph nodes and edges, each node tied to the session its first observation came from."""
    gnodes = gq.get("nodes") or []
    obs_session = await _locate(gnodes)
    session_project = {f"session:{s['id']}": s.get("project") or "" for s in sessions}
    for n in gnodes:
        src = n.get("sourceObservationIds") or []
        sid = f"session:{obs_session.get(src[0], '')}" if src else ""
        _add(nodes, n["id"], str(n.get("name") or n["id"]), _KIND.get(n.get("type"), "concept"),
             _norm(len(src), 32), _ms(n.get("createdAt")), session_project.get(sid, ""))
        if sid in nodes:
            links.append(_link(n["id"], sid, "seen_in", 0.5))
    for e in gq.get("edges") or []:
        links.append(_link(e["sourceNodeId"], e["targetNodeId"], e.get("type", "related_to"), float(e.get("weight") or 0.5)))


def _tags(nodes: Nodes, links: list[dict], memories: list[dict]) -> None:
    """memory -> concept links by tag name."""
    by_label = {v["label"].lower(): k for k, v in nodes.items() if v["kind"] == "concept"}
    for m in memories:
        links += [_link(m["id"], by_label[c.lower()], "tagged", 0.5) for c in m.get("concepts") or [] if c.lower() in by_label]


async def _build() -> dict:
    sessions = (await fetch.recent_sessions(time.time() - SESSION_DAYS * 86400))[:40]
    memories = await fetch.recent_memories(60)
    gq = await client.post("/graph/query", {"limit": GRAPH_FETCH})
    nodes: Nodes = {}
    links: list[dict] = []
    _structure(nodes, links, sessions, memories)
    await _knowledge(nodes, links, gq, sessions)
    _tags(nodes, links, memories)
    return _cap(nodes, links)


def _cap(nodes: dict[str, dict], links: list[dict]) -> dict:
    """Keep every project/session/memory first, fill the rest with the newest heaviest graph nodes."""
    core = [n for n in nodes.values() if n["kind"] in ("project", "session", "memory")]
    rest = sorted((n for n in nodes.values() if n not in core), key=lambda n: (n["ts"], n["weight"]), reverse=True)
    keep = {n["id"]: n for n in (core + rest)[:MAX_NODES]}
    seen: set[tuple[str, str, str]] = set()
    kept_links = []
    for lk in links:
        key = (lk["source"], lk["target"], lk["kind"])
        if lk["source"] in keep and lk["target"] in keep and key not in seen:
            seen.add(key)
            kept_links.append(lk)
    return {"nodes": list(keep.values()), "links": kept_links}


def filter_graph(graph: dict, project: str | None = None, query: str | None = None) -> dict:
    """Narrow to a project and/or to nodes whose label contains `query` plus their direct neighbours."""
    nodes, links = graph["nodes"], graph["links"]
    if project:
        keep = {n["id"] for n in nodes if n["project"] == project}
        nodes = [n for n in nodes if n["id"] in keep]
        links = [lk for lk in links if lk["source"] in keep and lk["target"] in keep]
    if query:
        q = query.lower()
        hit = {n["id"] for n in nodes if q in n["label"].lower()}
        near = hit | {x for lk in links for x in (lk["source"], lk["target"]) if lk["source"] in hit or lk["target"] in hit}
        nodes = [n for n in nodes if n["id"] in near]
        links = [lk for lk in links if lk["source"] in near and lk["target"] in near]
    return {"nodes": nodes, "links": links}


async def _refresh() -> dict:
    """Build once even when several callers arrive together; stores the result in the cache."""
    loop = asyncio.get_running_loop()
    task = _inflight.get("build")
    if task is None or task.done() or task.get_loop() is not loop:
        task = _inflight["build"] = loop.create_task(_build_and_store())
    return await asyncio.shield(task)


async def _build_and_store() -> dict:
    graph = await _build()
    _cache["graph"] = (time.time(), graph)
    return graph


def _refresh_in_background() -> None:
    task = asyncio.get_running_loop().create_task(_refresh())
    task.add_done_callback(lambda t: t.cancelled() or t.exception())  # a failed refresh keeps the stale graph


async def cached_graph() -> dict:
    """The full {nodes, links}: fresh within CACHE_S, stale-while-revalidate up to STALE_MAX_S, else rebuilt."""
    hit = _cache.get("graph")
    if hit is None or time.time() - hit[0] >= STALE_MAX_S:
        return await _refresh()
    if time.time() - hit[0] >= CACHE_S:
        _refresh_in_background()
    return hit[1]


async def memory_graph(project: str | None = None, query: str | None = None) -> dict:
    """{nodes, links} for the orbs; raises client.MemoryUnavailable when agentmemory is down and nothing is cached."""
    return filter_graph(await cached_graph(), project, query)
