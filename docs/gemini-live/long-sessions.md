# Long voice sessions: SDK calls used

SDK google-genai 2.34.0, model `gemini-3.8-live`. Facts from the official Gemini Live docs (2026-11-20):
audio-only sessions end after ~15 min without compression; one connection lasts ~10 min and the server
sends `go_away` before closing; resumption handles are valid ~2 h.

## Config (`app/voice/session.py`)

```python
types.LiveConnectConfig(
    ...,
    context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
    session_resumption=types.SessionResumptionConfig(handle=handle),   # handle=None on the first connect
)
```
`proactive_audio` is intentionally not set.

## Server messages handled (`app/voice/bridge.py`)

| `LiveServerMessage` field | Handling |
|---|---|
| `session_resumption_update` | if `.resumable` and `.new_handle`: store as the latest handle |
| `go_away` (`.time_left`) | raise internal `_GoAway`, leave the `async with` block, reconnect with the handle |
| `tool_call_cancellation.ids` | `ToolRunner.cancel(ids)`: cancel the matching task, emit `tool ... error`, send NO response |
| `usage_metadata` | forwarded as `{t:'usage', prompt, response, thoughts, total}` (missing counts omitted) |

An unexpected close surfaces from `session.receive()` as `errors.APIError` (code 1000/1006); any exception after the
first successful connect triggers a reconnect. A failure before the first connect is reported as `error` at once.

## Reconnect policy

- GoAway: reconnect immediately, does not count as a failure.
- Other drops: up to 5 consecutive retries, backoff 0.5, 1, 2, 4, 8 s. Any received message resets the counter.
- Browser sees `{t:'notice', text:'reconnecting'}` and a `state thinking` blip, then `state listening`.
- Audio and text sent while reconnecting are dropped (a gap of about one second).
- Long tools keep running while the link is down. `ToolRunner.detach()/attach(session)` swap the session; a finished
  tool waits up to 120 s for the new session and sends its result there (`send_tool_response`, same call id).
  Caveat: whether the model still accepts a tool response for a call id issued in the previous connection
  is NOT verified against the real server (only the fake-session unit test covers delivery).

## Tests

- `tests/test_bridge_resume.py`: fake Live session (GoAway + handle + reconnect, non-resumable update, retries,
  give-up after 5, usage, late tool result after reconnect, cancellation).
- `tests/real_resume_drop.py`: real Gemini; closes the client websocket (`bridge._session._ws.close()`) after the
  model memorised a word, then asks for it after the automatic resume.

## Not tested

- A real 10+ minute run (natural GoAway, real compression kicking in, 15 min limit). Only the client-forced drop
  was exercised against the server. The real GoAway message shape is covered only by the SDK types.
- A real `tool_call_cancellation` from the server (needs real barge-in with a pending tool call).
- Resume of a pending NON_BLOCKING tool call id across connections.
