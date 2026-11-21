# backend/app/memory/focus.py
"""Query-focused memory graph: hybrid search hits mapped onto orb ids plus their 1-hop neighbours.

Result: {nodes, links, query, highlight, hits, summary}; nodes/links follow the generic memory_graph schema.
Recalled text is untrusted data: labels, snippets and the summary are control-char free and length capped.
"""

import asyncio
import re
import unicodedata

from app.memory import awareness, fetch, graph

FOCUS_MAX_NODES = 120
TOP_HITS = 12
SEARCH_HITS = 24
LABEL_MAX = 80
SNIPPET_MAX = 160
SUMMARY_MAX = 400
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def clean(text: object, n: int) -> str:
    """Control characters removed, whitespace collapsed, at most n chars."""
    return awareness.clip(_CONTROL.sub(" ", str(text or "")), n)


def _fold(text: object) -> str:
    return unicodedata.normalize("NFKD", str(text or "").casefold()).encode("ascii", "ignore").decode()


def _lexical_match(query: str, found: list[dict], records: dict) -> bool:
    """True when some hit mentions a query word (accent-insensitive). Vector search always returns nearest
    neighbours, so a nonsense query would otherwise light up unrelated orbs."""
    words = re.findall(r"\w{3,}", _fold(query))
    for hit in found:
        rec = records.get(hit["obsId"]) or {}
        blob = _fold(" ".join([str(hit.get("title") or ""), str(rec.get("title") or ""), str(rec.get("narrative") or ""),
                               " ".join(map(str, rec.get("facts") or [])), " ".join(map(str, rec.get("concepts") or []))]))
        if any(w in blob for w in words):
            return True
    return False


def _lookup(nodes: dict[str, dict], label: str, kind: str) -> str | None:
    """Id of a graph node of `kind` whose label equals `label` (files also match by path suffix)."""
    want = label.lower()
    for n in nodes.values():
        if n["kind"] == kind and (n["label"].lower() == want or (kind == "file" and want.endswith("/" + n["label"].lower()))):
            return n["id"]
    return None


def _hit_node(hit: dict, record: dict, nodes: dict[str, dict]) -> tuple[str, str, str, str]:
    """(node id, kind, label, snippet) for one search hit; creates the node when the slice lacks it."""
    ts = int(fetch.parse_ts(hit.get("timestamp")) * 1000)
    text = (record.get("facts") or [None])[0] or record.get("narrative") or hit.get("title")
    snippet = clean(text, SNIPPET_MAX)
    title = clean(record.get("title") or hit.get("title"), LABEL_MAX)
    sid = hit.get("sessionId")
    if hit["obsId"].startswith("mem_") or sid in (None, "memory"):
        node_id, kind, label = hit["obsId"], "memory", title
    else:
        node_id, kind = f"session:{sid}", "session"
        label = nodes[node_id]["label"] if node_id in nodes else clean(snippet or title, LABEL_MAX)
    if node_id not in nodes:
        project = clean(record.get("project"), LABEL_MAX)
        nodes[node_id] = {"id": node_id, "label": label, "kind": kind, "weight": 0.8, "ts": ts, "project": project}
    return node_id, kind, nodes[node_id]["label"], snippet


def _summary(query: str, hits: list[dict]) -> str:
    q = clean(query, 60)
    if not hits:
        return f"Nic nenalezeno k dotazu '{q}'."
    parts = "; ".join(h["snippet"] or h["label"] for h in hits[:3])
    return clean(f"K dotazu '{q}' jsem nasel {len(hits)} zaznamu. Nejvyraznejsi: {parts}", SUMMARY_MAX)


def _empty(query: str) -> dict:
    return {"nodes": [], "links": [], "query": clean(query, 200), "highlight": [], "hits": [], "summary": _summary(query, [])}


async def focused_graph(query: str, project: str | None = None, days: int | None = None) -> dict:
    """Search `query` and return the matching orbs highlighted among their neighbours; never empty-errors."""
    found, base = await asyncio.gather(awareness.search_hits(query, days, SEARCH_HITS), graph.cached_graph(), return_exceptions=True)
    if isinstance(found, BaseException):  # includes client.MemoryUnavailable
        raise found
    cached = base if isinstance(base, dict) else {"nodes": [], "links": []}  # a down graph build still allows hit nodes
    if not found:
        return _empty(query)
    nodes: dict[str, dict] = {n["id"]: dict(n) for n in cached["nodes"]}
    records = await awareness.expand_hits(query, found)
    if not _lexical_match(query, found, records):
        return _empty(query)
    highlight: dict[str, float] = {}
    hits: list[dict] = []
    for hit in found:
        record = records.get(hit["obsId"]) or {}
        node_id, kind, label, snippet = _hit_node(hit, record, nodes)
        node = nodes[node_id]
        if project and node["project"] and node["project"] != project:
            continue
        score = round(float(hit.get("score") or 0), 3)
        if node_id not in highlight:
            hits.append({"id": node_id, "label": label, "kind": kind, "score": score, "snippet": snippet,
                         "ts": node["ts"], "project": node["project"]})
        highlight[node_id] = max(highlight.get(node_id, 0.0), score)
        for key, ckind in (("concepts", "concept"), ("files", "file")):
            for name in (record.get(key) or [])[:5]:
                if (cid := _lookup(nodes, clean(name, LABEL_MAX), ckind)) and cid not in highlight:
                    highlight[cid] = score * 0.5
    ordered = sorted(highlight, key=lambda i: -highlight[i])
    if not ordered:
        return _empty(query)
    links = list(cached["links"])
    known = {n["id"] for n in cached["nodes"]}
    for node_id in ordered:  # hit nodes missing from the cached slice still hang under their project
        node = nodes[node_id]
        if node_id not in known and f"project:{node['project']}" in nodes:
            links.append({"source": node_id, "target": f"project:{node['project']}", "kind": "in", "weight": 1.0})
    return _assemble(query, nodes, links, ordered, hits[:TOP_HITS])


def _assemble(query: str, nodes: dict[str, dict], links: list[dict], ordered: list[str], hits: list[dict]) -> dict:
    keep = list(dict.fromkeys(ordered))[:FOCUS_MAX_NODES]
    chosen = set(keep)
    near: dict[str, float] = {}
    for lk in links:
        for a, b in ((lk["source"], lk["target"]), (lk["target"], lk["source"])):
            if a in chosen and b not in chosen and b in nodes:
                near[b] = max(near.get(b, 0.0), float(nodes[b]["weight"]))
    keep += sorted(near, key=lambda i: -near[i])[: FOCUS_MAX_NODES - len(keep)]
    chosen = set(keep)
    seen: set[tuple[str, str, str]] = set()
    out_links = []
    for lk in links:
        key = (lk["source"], lk["target"], lk["kind"])
        if lk["source"] in chosen and lk["target"] in chosen and key not in seen:
            seen.add(key)
            out_links.append(lk)
    out_nodes = [{**nodes[i], "label": clean(nodes[i]["label"], LABEL_MAX)} for i in keep]
    return {"nodes": out_nodes, "links": out_links, "query": clean(query, 200), "highlight": ordered[:FOCUS_MAX_NODES],
            "hits": hits, "summary": _summary(query, hits)}
