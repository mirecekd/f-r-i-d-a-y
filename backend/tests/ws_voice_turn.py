# backend/tests/ws_voice_turn.py
"""Scripted /ws client: voice_start, one text turn, print transcript/state/tool events (no audio bytes).

Usage: python tests/ws_voice_turn.py [ws://127.0.0.1:8684/ws] ["text"] [seconds]
The server needs GEMINI_API_KEY in its environment.
"""

import asyncio
import json
import sys
import time

import websockets


async def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8684/ws"
    text = sys.argv[2] if len(sys.argv) > 2 else "Ahoj Friday, kdo jsi? Odpovez jednou vetou."
    listen = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
    t0 = time.time()
    audio_frames = audio_bytes = 0

    def log(s: str) -> None:
        print(f"[{time.time() - t0:5.1f}s] {s}", flush=True)

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"t": "voice_start"}))
        await ws.send(json.dumps({"t": "chat", "text": text}))
        log(f">> voice_start, chat: {text!r}")
        end = time.time() + listen
        while time.time() < end:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=end - time.time())
            except TimeoutError:
                break
            if isinstance(msg, bytes):
                audio_frames += 1
                audio_bytes += len(msg)
                continue
            m = json.loads(msg)
            if m["t"] == "transcript" and not m["final"]:
                continue
            log(f"<< {json.dumps(m, ensure_ascii=False)[:200]}")
        await ws.send(json.dumps({"t": "voice_stop"}))
        log(f"<< audio: {audio_frames} binary frames, {audio_bytes} bytes (24 kHz PCM16 = {audio_bytes / 48000:.1f} s)")
        try:
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                log(f"<< {json.dumps(m)[:200]}")
        except (TimeoutError, TypeError, websockets.ConnectionClosed):
            pass


asyncio.run(main())
