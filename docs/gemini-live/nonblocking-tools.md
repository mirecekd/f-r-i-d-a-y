# Non-blocking tools in Gemini Live

SDK google-genai 2.34.0, model `gemini-3.8-live`
(`GEMINI_LIVE_MODEL`), voice Algieba, `cs-CZ`.
Input was text only; output was read from `output_audio_transcription` plus a count of audio bytes.

## Verdict: WORKS with this model

A tool declared with `behavior=NON_BLOCKING` does not stall the model. The model keeps talking, answers
new user input while the task runs, and the late result is injected by `send_tool_response` and
announced according to `FunctionResponse.scheduling`.

## Exact SDK calls that work

```python
decl = types.FunctionDeclaration(
    name="draw", description="...",
    parameters=types.Schema(type=types.Type.OBJECT,
        properties={"request": types.Schema(type=types.Type.STRING)}, required=["request"]),
    behavior=types.Behavior.NON_BLOCKING,          # the key setting
)
config = types.LiveConnectConfig(..., tools=[types.Tool(function_declarations=[decl])])

# user turn: both work
await session.send_realtime_input(text="...")
await session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text="...")]),
                                  turn_complete=True)

# on resp.tool_call: start asyncio task, do NOT answer yet (the receive loop must keep running)
# when the task ends, possibly 15 s later:
await session.send_tool_response(function_responses=[types.FunctionResponse(
    id=fc.id, name=fc.name, response={"output": "..."},
    scheduling=types.FunctionResponseScheduling.INTERRUPT)])   # or WHEN_IDLE / SILENT
```

## Observations (delay 6 to 12 s standing in for a slow task)

| Case | Result |
|---|---|
| `NON_BLOCKING`, no immediate ack | Tool call arrives together with `turn_complete`. The model speaks on (Prague monologue, answers a follow-up "2+2" within 0.5 s). Works. |
| `NON_BLOCKING` plus ack `will_continue=True, scheduling=SILENT` | Same behaviour; the ack is optional and not needed. |
| `INTERRUPT` late result | Cuts off current speech (`interrupted`) and announces the result at once ("Obrazek lva je hotovy."). If the model is idle, it simply speaks. |
| `WHEN_IDLE` late result | Does not cut off speech; the model finishes (or continues) and mentions the result afterwards or woven in. |
| `SILENT` late result | Accepted into context, nothing spoken. A later user question can use it. |
| `BLOCKING` (control) | Model is silent from tool call until the response is sent (10 s of silence), then speaks. This is the behaviour we avoid. |
| `client` vs `realtime` text input | Both work with NON_BLOCKING. |

## Decisions for the app

- Long tools (`draw`, later artist / Hermes) are registered with `long=True`: declared NON_BLOCKING, run
  in an asyncio task, result sent with `scheduling=WHEN_IDLE` by default (`INTERRUPT` selectable).
- The tool call itself needs no immediate response, but any task failure must still send a response
  (`{"error": ...}`) so the model does not wait forever.
- Not tested: parallel long tools, a session reconnect during a running task (the result would be sent to a
  dead session and is dropped), real microphone audio.
