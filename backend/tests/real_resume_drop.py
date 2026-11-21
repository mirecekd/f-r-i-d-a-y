# backend/tests/real_resume_drop.py
"""Real Gemini check: drop the websocket client-side, expect a transparent resume with context kept.

Usage (from backend/, GEMINI_API_KEY in the environment): python tests/real_resume_drop.py
Prints a text-only transcript of the bridge events. Exit code 0 when the word is recalled after the drop.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.voice import ToolRegistry, VoiceBridge  # noqa: E402

WORD = "ZELVA"


async def main() -> int:
    t0 = time.time()
    events: list[dict] = []
    audio = 0

    async def send_json(m: dict) -> None:
        events.append(m)
        if m["t"] == "transcript" and not m["final"]:
            return
        print(f"[{time.time() - t0:5.1f}s] {json.dumps(m, ensure_ascii=False)[:200]}", flush=True)

    async def send_bytes(b: bytes) -> None:
        nonlocal audio
        audio += len(b)

    bridge = VoiceBridge(send_json, send_bytes, ToolRegistry())
    await bridge.start()
    print(">>> user: remember the word", flush=True)
    await bridge.send_text(f"Zapamatuj si tajne slovo {WORD}. Potvrd jednou kratkou vetou.")
    for _ in range(300):  # wait for the answer and a resumption handle
        await asyncio.sleep(0.1)
        if bridge._handle and any(m["t"] == "transcript" and m["final"] and m["role"] == "assistant" for m in events):
            break
    print(f">>> handle stored: {bridge._handle is not None}", flush=True)
    before = len(events)
    print(">>> forcing client-side websocket close", flush=True)
    await bridge._session._ws.close()
    for _ in range(150):
        await asyncio.sleep(0.1)
        if bridge._session is not None and any(m.get("t") == "notice" for m in events[before:]):
            break
    print(">>> user: what was the word?", flush=True)
    mark = len(events)
    await bridge.send_text("Jake bylo to tajne slovo, ktere jsem ti rekl? Rekni jen to slovo.")
    for _ in range(300):
        await asyncio.sleep(0.1)
        if any(m["t"] == "transcript" and m["final"] and m["role"] == "assistant" for m in events[mark:]):
            break
    await bridge.stop()
    answer = " ".join(m["text"] for m in events[mark:] if m["t"] == "transcript" and m["final"] and m["role"] == "assistant")
    notice = any(m.get("t") == "notice" for m in events[before:])
    ok = WORD.lower() in answer.lower().replace("ž", "z")
    print(f"RESULT notice={notice} audio_bytes={audio} recalled={ok} answer={answer!r}")
    return 0 if (notice and ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
