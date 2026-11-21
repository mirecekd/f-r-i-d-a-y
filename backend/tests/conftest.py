# backend/tests/conftest.py
import httpx
import pytest
from memory_fakes import FakeServer

from app.agent.catalog import catalog
from app.memory import client, graph


@pytest.fixture(autouse=True)
def isolated_agent_state(tmp_path, monkeypatch):
    """No network catalog fetches and no writes to /srv/data from any test."""
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "friday-data"))
    monkeypatch.delenv("AGENTMEMORY_URL", raising=False)  # no real agentmemory calls from tests
    # load_dotenv() in voice/session.py pulls the real .env in: keep Hermes out of tool-registry tests
    monkeypatch.delenv("HERMES_URL", raising=False)
    monkeypatch.delenv("HERMES_KEY", raising=False)

    async def empty_catalog():
        return []

    monkeypatch.setattr(catalog, "get", empty_catalog)


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("AGENTMEMORY_URL", "http://mem:3111")
    monkeypatch.setenv("AGENTMEMORY_SECRET", "s3cret")
    graph._cache.clear()

    def install(routes):
        fake = FakeServer(routes)
        monkeypatch.setattr(client, "_transport", httpx.MockTransport(fake))
        return fake

    return install
