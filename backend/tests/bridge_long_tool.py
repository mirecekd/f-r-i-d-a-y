# backend/tests/bridge_long_tool.py
"""Drive VoiceBridge directly with a slow `draw` tool (real Gemini) and print the event timeline.

Usage (run from backend/, GEMINI_API_KEY in the environment): python tests/bridge_long_tool.py
Expected: tool start, the model keeps speaking, tool ok after ~8 s, then the model announces the result.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.voice import Tool, ToolRegistry, VoiceBridge  # noqa: E402


async def slow_draw(args: dict) -> dict:
    await asyncio.sleep(8)
    return {"output": f"Obrazek '{args.get('request')}' je hotovy."}


async def main() -> None:
    t0 = time.time()
    audio = 0

    async def send_json(m: dict) -> None:
        if m["t"] == "transcript" and not m["final"]:
            return
        print(f"[{time.time() - t0:5.1f}s] {json.dumps(m, ensure_ascii=False)[:200]}", flush=True)

    async def send_bytes(b: bytes) -> None:
        nonlocal audio
        audio += len(b)

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="draw",
            description="Nakresli obrazek podle zadani. Trva dlouho (desitky sekund).",
            parameters={"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]},
            handler=slow_draw,
            long=True,
        )
    )
    bridge = VoiceBridge(send_json, send_bytes, registry)
    await bridge.start()
    await bridge.send_text("Nakresli mi lva. Mezitim mi povez neco o Praze, dve vety.")
    await asyncio.sleep(22)
    await bridge.stop()
    print(f"audio bytes: {audio} ({audio / 48000:.1f} s)")


asyncio.run(main())
