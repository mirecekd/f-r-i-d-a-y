# backend/app/main.py
"""Friday backend: serves the built frontend and the /ws event channel."""

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.agent_wiring import AgentSession
from app.mcp import api_router as mcp_router
from app.memory.handlers import memory_search, show_memory_graph
from app.memory.warm import lifespan
from app.scene import SceneStore
from app.scene_demo import DEMO_CAMERA, demo_objects
from app.stop import StopController
from app.views_demo import sample_views
from app.vision import router as vision_router
from app.voice import ToolRegistry, VoiceBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("friday")

VERSION = os.getenv("FRIDAY_VERSION") or __version__
STATIC = Path(os.getenv("STATIC_DIR", Path(__file__).parent.parent / "static"))

app = FastAPI(title="Friday", lifespan=lifespan)
scene = SceneStore()
tool_registry = ToolRegistry()  # hook: MCP / Hermes / artist tools register here
app.include_router(vision_router)
app.include_router(mcp_router)


@app.get("/health")
async def health():
    return {"ok": True, "version": VERSION}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"t": "hello", "version": VERSION, "models": {}})
    await ws.send_json({"t": "scene_full", "objects": scene.objects()})
    await ws.send_json({"t": "state", "state": "idle"})
    # AgentSession owns the per-connection registry: Friday tools + `draw` close over this ws
    agent = AgentSession(scene, ws.send_json, tool_registry)
    await agent.send_models()
    voice = VoiceBridge(ws.send_json, ws.send_bytes, agent.registry, agent.approvals)
    stopper = StopController(ws.send_json, agent, voice)
    stopper.start_monitor()
    try:
        while True:
            frame = await ws.receive()
            if frame["type"] == "websocket.disconnect":
                break
            if frame.get("bytes"):
                if voice.active:
                    await voice.send_audio(frame["bytes"])
            elif frame.get("text"):
                await handle(ws, json.loads(frame["text"]), voice, agent, stopper)
    except WebSocketDisconnect:
        pass
    finally:
        await stopper.close()
        await voice.stop()
        await agent.close()


async def handle(ws: WebSocket, msg: dict, voice: VoiceBridge, agent: AgentSession, stopper: StopController) -> None:
    kind = msg.get("t")
    if kind == "ping":
        await ws.send_json({"t": "pong"})
    elif kind == "stop":
        await stopper.stop()
    elif kind == "voice_start":
        await voice.start()
    elif kind == "voice_stop":
        await voice.stop()
    elif kind == "chat" and voice.active:
        await voice.send_text(str(msg.get("text", "")))
    elif kind == "chat":
        agent.chat(str(msg.get("text", "")))
    elif kind in ("frame", "frames_stop"):
        await voice.frames.handle(msg)
    elif kind == "confirm":
        agent.approvals.resolve(msg)
    elif kind == "image_upload":
        await agent.vision.on_upload(msg)
    elif kind == "image_to_scene":
        await agent.vision.on_image_to_scene(msg)
    elif kind == "set_model":
        await agent.set_model(msg, voice.active)
    elif kind == "set_language":
        await agent.set_language(msg, voice.active)
    elif kind == "set_voice":
        await agent.set_voice(msg, voice.active)
    elif kind == "demo" and os.getenv("FRIDAY_DEMO") == "1" and msg.get("what") == "views":
        for v in sample_views():
            await ws.send_json(v)
    elif kind == "show_memory_graph":
        await show_memory_graph(ws.send_json, msg)
    elif kind == "memory_search":
        await memory_search(ws.send_json, msg)
    elif kind == "select":
        scene.select(msg.get("ids", []))
    elif kind == "demo" and os.getenv("FRIDAY_DEMO") == "1" and msg.get("what") == "scene":
        scene.apply([{"op": "clear"}, *({"op": "add", "obj": o} for o in demo_objects())])
        await ws.send_json({"t": "scene_full", "objects": scene.objects()})
        await ws.send_json({"t": "scene", "ops": [DEMO_CAMERA]})
    else:
        await ws.send_json({"t": "error", "message": f"unknown message type: {kind}"})


if STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")
