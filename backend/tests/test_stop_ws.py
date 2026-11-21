# backend/tests/test_stop_ws.py
"""STOP over the real /ws: a text-chat turn in flight is cancelled and the state returns to idle."""

import asyncio

from fastapi.testclient import TestClient

from app import agent_wiring, main


def drain(ws, until):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if until(msg):
            return seen


def test_stop_cancels_text_chat_turn(monkeypatch):
    blocked = {"cancelled": False}

    async def hanging_turn(model, history, tools, emit, on_delta):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            blocked["cancelled"] = True
            raise

    monkeypatch.setattr(agent_wiring.live_text, "run_turn", hanging_turn)
    with TestClient(main.app).websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "chat", "text": "hello"})
        drain(ws, lambda m: m == {"t": "state", "state": "thinking"})
        ws.send_json({"t": "stop"})
        seen = drain(ws, lambda m: m["t"] == "notice")
        assert {"t": "stopped", "cancelled": ["chat"]} in seen
        assert seen[-1] == {"t": "notice", "text": "Zastaveno"}
        assert blocked["cancelled"]
        ws.send_json({"t": "stop"})  # idle: still answers
        assert {"t": "stopped", "cancelled": []} in drain(ws, lambda m: m["t"] == "notice")
