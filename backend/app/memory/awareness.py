# backend/app/memory/awareness.py
"""Awareness over agentmemory: today's digest, recall and recent decisions as compact text.

Endpoints: GET /sessions, GET /observations, GET /memories, POST /smart-search, POST /graph/query.
Functions raise client.MemoryUnavailable when the server cannot be used.
"""

import time
from collections import defaultdict
from datetime import UTC, datetime

from app.memory import client, fetch

MAX_SESSIONS = 25
RECALL_CHARS = 1500
DIGEST_CHARS = 3000
KEY_TYPES = {"file_write", "file_edit"}
RECALL_FETCH = 12  # hits requested per layer before the time window and expansion


def clip(text: object, n: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def short_id(session: dict) -> str:
    """Last 8 chars: session ids are time-ordered uuids whose first 8 chars repeat within minutes."""
    return str(session["id"])[-8:]


def _hhmm(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%H:%M")


def _day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%d")


async def headline(hours: int = 24) -> tuple[str, list[dict]]:
    """One-line header ("Last 24h: ...") plus the sessions it counts, newest first."""
    sessions = await fetch.recent_sessions(time.time() - hours * 3600)
    projects: dict[str, int] = defaultdict(int)
    for s in sessions:
        projects[s.get("project") or "?"] += 1
    obs = sum(int(s.get("observationCount") or 0) for s in sessions)
    top = ", ".join(f"{p} {n}" for p, n in sorted(projects.items(), key=lambda kv: -kv[1])[:5])
    return f"Last {hours}h (UTC): {len(sessions)} sessions, {obs} observations; projects: {top or 'none'}.", sessions


def _session_line(s: dict, observations: list[dict]) -> str:
    asked = next((o for o in observations if o.get("type") == "conversation"), None)
    writes = sum(1 for o in observations if o.get("type") in KEY_TYPES)
    errors = sum(1 for o in observations if o.get("type") == "error")
    key = [clip(o.get("title"), 60) for o in observations if int(o.get("importance") or 0) >= 7][:2]
    parts = [f"{_hhmm(fetch.parse_ts(s.get('startedAt')))} {short_id(s)} ({s.get('observationCount', 0)} obs)"]
    if asked:
        parts.append(f"asked: {clip(asked.get('narrative'), 110)}")
    if writes or errors:
        parts.append(f"{writes} file edits, {errors} errors")
    if key:
        parts.append("key: " + "; ".join(key))
    return "  - " + " | ".join(parts)


async def today_digest() -> str:
    """Sessions of the last 24 h grouped by project with their key observations, plus memories saved."""
    head, sessions = await headline()
    sessions = sessions[:MAX_SESSIONS]
    observed = await fetch.gather_limited([fetch.session_observations(str(s["id"])) for s in sessions])
    by_project: dict[str, list[str]] = defaultdict(list)
    for s, obs in zip(sessions, observed, strict=True):
        by_project[s.get("project") or "?"].append(_session_line(s, obs or []))
    lines = [head]
    for project, rows in by_project.items():
        lines.append(f"{project}:")
        lines += rows[:6]
    since = time.time() - 86400
    saved = [m for m in await fetch.recent_memories(50) if fetch.parse_ts(m.get("createdAt")) >= since]
    if saved:
        lines.append("Memories saved:")
        lines += [f"  - {clip(m.get('title'), 90)} ({m['id']})" for m in saved[:8]]
    return clip_block("\n".join(lines), DIGEST_CHARS)


def clip_block(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


async def recent_decisions(n: int = 5) -> list[str]:
    """Newest decisions first: graph decision nodes, topped up with the latest saved memories."""
    found: list[tuple[str, str]] = []
    graph = await client.request("POST", "/graph/query", body={"nodeType": "decision", "limit": 20})
    if "error" not in graph:  # decisions are a bonus; saved memories fill in below
        for node in graph.get("nodes") or []:
            desc = (node.get("properties") or {}).get("description") or ""
            found.append((str(node.get("createdAt") or ""), clip(f"{node.get('name')}: {desc}" if desc else node.get("name"), 160)))
    found.sort(reverse=True)
    out = [text for _, text in found[:n]]
    if len(out) < n:
        out += [clip(m.get("title"), 160) for m in await fetch.recent_memories(n - len(out))]
    return out[:n]


def _entry(hit: dict, expanded: dict) -> str:
    ts = fetch.parse_ts(hit.get("timestamp"))
    obs = expanded.get(hit.get("obsId")) or {}
    text = (obs.get("facts") or [None])[0] or obs.get("narrative") or hit.get("title")
    return f"[{hit['obsId']}] {_day(ts)} {hit.get('type', '?')}: {clip(text, 220)}"


async def search_hits(query: str, days: int | None = None, top: int = 8) -> list[dict]:
    """Hybrid search over memories and observations: deduplicated by obsId, newest-window only, best score first."""
    mixed = await client.post("/smart-search", {"query": query, "limit": RECALL_FETCH})
    memory = await client.post("/smart-search", {"query": query, "limit": RECALL_FETCH, "targetLayer": "memory"})
    since = time.time() - days * 86400 if days else 0.0
    seen: dict[str, dict] = {}
    for hit in (memory.get("results") or []) + (mixed.get("results") or []):
        if hit.get("obsId") and hit["obsId"] not in seen and fetch.parse_ts(hit.get("timestamp")) >= since:
            seen[hit["obsId"]] = hit
    return sorted(seen.values(), key=lambda h: -float(h.get("score") or 0))[:top]


async def expand_hits(query: str, hits: list[dict]) -> dict:
    """obsId -> full observation/memory record; empty on failure (titles alone are still a valid answer)."""
    ids = [{"obsId": h["obsId"], "sessionId": h.get("sessionId") or "memory"} for h in hits]
    full = await client.request("POST", "/smart-search", body={"query": query, "expandIds": ids})
    return {r.get("obsId"): r.get("observation") for r in full.get("results") or []}


async def recall(query: str, days: int | None = None) -> str:
    """Hybrid search (memories and observations) limited to the last `days`, deduplicated, ~1500 chars."""
    hits = await search_hits(query, days)
    if not hits:
        return "No matching memories."
    expanded = await expand_hits(query, hits)
    out, size = [], 0
    for hit in hits:
        line = _entry(hit, expanded)
        if size + len(line) > RECALL_CHARS and out:
            break
        out.append(line)
        size += len(line) + 1
    return clip_block("\n".join(out), RECALL_CHARS)
