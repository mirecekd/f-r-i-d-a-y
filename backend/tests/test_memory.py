# backend/tests/test_memory.py
import httpx
import pytest
from memory_fakes import MEMORY, ROUTES, iso, run

from app.memory import awareness, briefing, client
from app.voice import session as live


def test_client_sends_bearer_and_turns_failures_into_error(server):
    fake = server({("GET", "/counts"): {"counts": {}}, ("GET", "/bad"): 500})
    assert run(client.request("GET", "/counts")) == {"counts": {}}
    assert fake.calls[0][2] == "Bearer s3cret"
    assert run(client.request("GET", "/bad"))["error"].startswith("agentmemory HTTP 500")
    assert "unreachable" not in run(client.request("GET", "/missing"))["error"]
    with pytest.raises(client.MemoryUnavailable):
        run(client.get("/bad"))


def test_client_without_url_reports_error(monkeypatch):
    monkeypatch.delenv("AGENTMEMORY_URL", raising=False)
    assert "not configured" in run(client.request("GET", "/counts"))["error"]


def test_client_network_error_has_no_secret(server, monkeypatch):
    def boom(_request):
        raise httpx.ConnectError("refused s3cret")

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(boom))
    assert run(client.request("GET", "/x")) == {"error": "agentmemory unreachable: ConnectError"}


def test_today_digest_groups_by_project(server):
    server(ROUTES)
    text = run(awareness.today_digest())
    assert "Last 24h (UTC): 1 sessions, 9 observations; projects: FRIDAY 1." in text
    assert "FRIDAY:" in text and "abcdef12" in text
    assert "asked: Build the memory orbs" in text and "1 file edits, 1 errors" in text
    assert "Friday core (mem_1)" in text


def test_recall_dedupes_merges_window_and_trims(server):
    hit = {"obsId": "mem_1", "sessionId": "memory", "timestamp": iso(1), "title": "Friday core", "type": "decision", "score": 0.9}
    old = {"obsId": "obs_old", "sessionId": "s", "timestamp": iso(24 * 30), "title": "old", "type": "bash", "score": 0.99}
    long_obs = {"obsId": "obs_long", "sessionId": "s", "timestamp": iso(2), "title": "t", "type": "bash", "score": 0.5}
    fake = server({("POST", "/smart-search"): {"results": [hit, old, long_obs]}})
    text = run(awareness.recall("friday", days=7))
    assert text.count("[mem_1]") == 1
    assert "obs_old" not in text
    assert len(text) <= awareness.RECALL_CHARS
    assert any(b"expandIds" in c[3] for c in fake.calls)


def test_recall_nothing_found(server):
    server({("POST", "/smart-search"): {"results": []}})
    assert run(awareness.recall("zzz")) == "No matching memories."


def test_recent_decisions_newest_first_then_memories(server):
    nodes = [
        {"name": "old", "createdAt": iso(10), "properties": {}},
        {"name": "new", "createdAt": iso(1), "properties": {"description": "why"}},
    ]
    server({("POST", "/graph/query"): {"nodes": nodes}, ("GET", "/memories"): {"memories": [MEMORY]}})
    assert run(awareness.recent_decisions(3)) == ["new: why", "old", "Friday core"]


def test_startup_context_fits_budget_and_skips_when_down(server):
    server({**ROUTES, ("POST", "/graph/query"): {"nodes": [{"name": "d" * 400, "createdAt": iso(1), "properties": {}}] * 5}})
    text = run(briefing.startup_context())
    assert text.startswith("Last 24h") and len(text) <= briefing.MAX_CHARS
    server({})
    assert run(briefing.startup_context()) == ""
    assert run(briefing.briefing_or_empty()) == ""


def test_system_prompt_fences_briefing():
    plain = live.system_prompt(language="cs-CZ")
    assert plain.startswith("Jsi Friday")
    fenced = live.system_prompt("Last 24h", "cs-CZ")
    assert fenced.startswith(plain) and "<memory-data>\nLast 24h\n</memory-data>" in fenced
