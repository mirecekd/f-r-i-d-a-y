# backend/tests/test_workshop_session.py
"""WorkshopSession end to end without a browser: build the vase fixture, move a slider, undo, redo, leave."""

import asyncio
import json
from pathlib import Path

import pytest

from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.workshop.session import WORKSHOP_ERRORS, WorkshopSession

FIXTURES = Path(__file__).parent / "fixtures" / "workshop"
VASE = json.loads((FIXTURES / "vase.json").read_text(encoding="utf-8"))


def run(coro):
    return asyncio.run(coro)


def make():
    sent: list[dict] = []

    async def emit(msg):
        sent.append(msg)

    return WorkshopSession(Ctx(SceneStore(), emit)), sent


def height(session) -> float:
    return session.require()["values"]["height"]


def test_build_param_undo_redo_cycle():
    async def go():
        s, sent = make()
        await s.open(None, "Vase")
        await s.build(VASE)
        assert height(s) == 240
        await s.param("height", 300)
        assert height(s) == 300
        await s.step(True)
        assert height(s) == 240
        await s.step(False)
        assert height(s) == 300
        return sent

    sent = run(go())
    assert any(m.get("t") == "scene" for m in sent)
    assert any(m.get("op") == "params" for m in sent)


def test_slider_value_is_clamped_and_unknown_names_are_refused():
    async def go():
        s, _ = make()
        await s.open(None, "Vase")
        await s.build(VASE)
        await s.param("height", 99999)
        assert height(s) == 400  # the fixture's max
        with pytest.raises(WORKSHOP_ERRORS):
            await s.param("no_such_parameter", 1)

    run(go())


def test_a_bad_spec_is_refused_and_keeps_the_previous_build():
    async def go():
        s, _ = make()
        await s.open(None, "Vase")
        await s.build(VASE)
        with pytest.raises(WORKSHOP_ERRORS):
            await s.build({"parts": [{"id": "x", "kind": "box", "size": ["=nope", 1, 1]}]})
        assert height(s) == 240

    run(go())
