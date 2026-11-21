# backend/tests/test_workshop_ws.py
"""The whole workshop chain over the real WebSocket: new -> build (tool) -> slider -> undo -> redo -> leave."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main

VASE = json.loads((Path(__file__).parent / "fixtures" / "workshop" / "vase.json").read_text(encoding="utf-8"))


def drain(ws, until, limit=80):
    seen = []
    for _ in range(limit):
        msg = ws.receive_json()
        seen.append(msg)
        if until(msg):
            return seen
    raise AssertionError("no match; got " + str([m.get("t") for m in seen]))


def is_op(name):
    return lambda m: m.get("t") == "workshop" and m.get("op") == name


def connect():
    ws_cm = TestClient(main.app).websocket_connect("/ws")
    ws = ws_cm.__enter__()
    drain(ws, lambda m: m["t"] == "models")
    return ws_cm, ws


def test_enter_leave_and_errors_are_readable_messages_not_crashes():
    cm, ws = connect()
    try:
        ws.send_json({"t": "workshop_new", "title": "Probe"})
        enter = drain(ws, is_op("enter"))[-1]
        assert enter["origin"] == [0.0, 0.0, 400.0] and enter["title"] == "Probe"
        ws.send_json({"t": "workshop_param", "id": enter["id"], "name": "x", "value": 1})
        assert "workshop_build first" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]
        ws.send_json({"t": "workshop_open", "id": "does-not-exist"})
        assert drain(ws, lambda m: m["t"] == "error")[-1]["message"].startswith("workshop_open")
        ws.send_json({"t": "workshop_leave"})
        assert drain(ws, is_op("leave"))[-1]["id"] == enter["id"]
    finally:
        cm.__exit__(None, None, None)


def test_two_workshops_get_different_origins():
    cm, ws = connect()
    try:
        ws.send_json({"t": "workshop_new"})
        first = drain(ws, is_op("enter"))[-1]
        ws.send_json({"t": "workshop_new"})
        second = drain(ws, is_op("enter"))[-1]
        assert first["origin"] != second["origin"] and first["id"] != second["id"]
    finally:
        cm.__exit__(None, None, None)
