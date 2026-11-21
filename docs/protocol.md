# Friday WebSocket protocol (v0)

One WebSocket at `/ws`. Text frames carry JSON `{"t": "<type>", ...}`. Binary frames carry audio
(PCM16 mono: 16 kHz up from the browser, 24 kHz down from the model) - added in step 3.

Authentication is not built in: a reverse proxy in front of the app handles it; the backend never sees credentials.

## Server -> browser

| `t` | Fields | Meaning |
|---|---|---|
| `hello` | `version`, `models` | first frame after connect |
| `state` | `state`: `idle\|listening\|thinking\|speaking\|drawing\|error` | drives the core orb |
| `transcript` | `role`: `user\|assistant`, `text`, `final` | live and final speech transcript |
| `chat` | `role`, `text`, `id` | a complete chat message |
| `chat_delta` | `id`, `text` | streamed chunk of an assistant message |
| `tool` | `id`, `name`, `status`: `start\|ok\|error`, `ms?` | tool call chip |
| `scene` | `ops`: Op[] | scene patch (see below) |
| `scene_full` | `objects`: Obj[] | full replacement, sent on connect |
| `interrupted` | | barge-in: the browser drops queued playback |
| `stopped` | `cancelled` | answer to `stop`: names of what was cancelled (`draw`, `chat`, `voice`, ...), empty when idle |
| `busy` | `busy`, `count` | sent when the number of running things (voice, long tools, chat turns, open approvals) changes |
| `view` | `id`, `kind`, `title?`, `data` | rich floating panel, see "View panels" below; re-sending an `id` replaces the panel |
| `view_close` | `id` | close a panel |
| `notice` | `text` | informational, e.g. `reconnecting` while the Live session resumes after GoAway or a drop |
| `usage` | `prompt?`, `response?`, `thoughts?`, `total?` | token counts reported by Gemini Live |
| `models` | `catalog`: {id, provider, label, group}[], `pinned`: {agent_model, chat_model}, `language`, `languages`: {code, label}[], `voice`, `voices`: {id, label, gender, style}[], `thinking`, `thinking_levels` | model catalog, pinned choices, language and voices of the pinned chat model, see "Models"; sent on connect and echoed after `set_model`, `set_language`, `set_voice` and `set_thinking` |
| `confirm_request` | `id`, `tool`, `summary`, `args`, `expires_in` | a risky tool wants to run; the browser must answer with `confirm` within `expires_in` seconds; `args` is truncated and values under keys matching `key\|token\|secret\|password` are `***` |
| `confirm_closed` | `id`, `reason`: `timeout\|cancelled` | the question is over without an answer (timeout counts as deny); drop the prompt |
| `file_ready` | `id`, `client_id?`, `kind`, `name`, `size`, `url`, `meta` | a non-image file is stored and extracted; see "Files" |
| `image_ready` | `id`, `client_id?`, `url`, `w`, `h`, `exif` | an uploaded image is stored; see "Images" |
| `conversation_reset` | `clear_scene` | answer to `new_conversation`: the browser empties its chat log and history, see "Conversation" |
| `error` | `message`, `id?` | non-fatal error (`id` echoes the `image_upload` it answers) |

While a voice session is open, `chat` text goes to the same Live session as a user turn.
Long tools (NON_BLOCKING, see `docs/gemini-live/nonblocking-tools.md`) emit `tool start`, the state `drawing`
while they run, and `tool ok|error` when done; the model announces the late result itself.

## Browser -> server

| `t` | Fields | Meaning |
|---|---|---|
| `chat` | `text`, `attachments?` | typed message |
| `voice_start` | | open a Gemini Live session; binary PCM16 16 kHz frames are then forwarded to it |
| `voice_stop` | | close the Live session |
| `audio_profile` | `profile`: `speaker\|headphones` | output device class (speaker = echo gate on in the browser); stored on the bridge and applied at the next voice session start, see `docs/audio-echo.md`; any other value gets an `error` |
| `stop` | | STOP button / Esc (or the optional open-palm hand gesture, see ui-gestures.md): cancel long tools, agent turns and approvals (denied), end the voice session, back to `idle`; the socket stays open; server replies `stopped` and `notice` "Zastaveno" |
| `new_conversation` | `clear_scene?`: bool | start over, see "Conversation" |
| `select` | `ids`: string[] | scene selection, so "make this bigger" resolves |
| `file_upload` | `id?`, `name`, `mime`, `data_b64`, `analyze?` | upload any file (<= 25 MB decoded); images are routed to the image path; see "Files" |
| `image_upload` | `id?`, `name`, `mime`, `data_b64`, `analyze?` | upload one image (<= 12 MB decoded, jpeg/png/webp/gif); see "Images" |
| `image_to_scene` | `id` | add the stored image to the 3D scene as an `entity` tile (same as the `show_in_scene` tool); unknown id answers `error` |
| `entity_open` | `id` | emit the `image_card` / `file_card` of the entity's stored item; errors answer `error` |
| `entity_link` | `from`, `to` | add a `link` object between two scene objects; the scene patch is broadcast |
| `entity_remove` | `id` | delete the entity and its links from the scene (the stored file or image stays) |
| `set_model` | `role`: `agent\|chat`, `model`: catalog id | pin a model (persisted), server echoes `models` |
| `set_language` | `language`: code from `languages` | pin the conversation language (persisted), server echoes `models`; unknown code answers `error` |
| `set_thinking` | `level`: one of `thinking_levels` | pin the thinking level (persisted), server echoes `models`; unknown level answers `error` |
| `set_voice` | `voice`: id from `voices` | pin the voice of the current chat model (persisted per model), server echoes `models`; a voice the model does not offer answers `error` |
| `confirm` | `id`, `allow`: bool, `remember?`: `once\|session` | answer to `confirm_request`; `session` remembers an allow for that tool name on this connection only |
| `frame` | `source`: `camera\|screen`, `mime`: `image/jpeg`, `data_b64` | one live vision frame for the model, see "Live vision input" |
| `frames_stop` | | the browser stopped streaming frames |
| `show_memory_graph` | `project?`, `query?` | HUD button: server sends a `notice` ("Nacitam pamet..."), then a `memory_graph` view (or `error` if agentmemory is down) |
| `memory_search` | `query`, `project?` | HUD/search box: server sends a `notice` ("Hledam v pameti..."), then a query-focused `memory_graph` view with `highlight`, `hits` and `summary` (or `error` when agentmemory is down or `query` is empty) |
| `ping` | | keepalive |
| `demo` | `what: "views"` | server sends one sample of every view kind; only when `FRIDAY_DEMO=1` |

### Workshop (browser side)
Sent by the browser: `workshop_open {id}`, `workshop_new {title?}`, `workshop_leave`, `workshop_param {id, name, value}` (at most 12 per second per
parameter), `workshop_undo {id}`, `workshop_redo {id}`, `workshop_snapshot {req, id, jpeg_b64}` (<= 800 kB decoded, or `{req, id, error}` with
`hidden`, `too_large` or `failed`). Handled from the server: `workshop` with `op` `enter` (`id`, `title`, `camera`, `home`, `params`, `sources`, `notes`),
`params` (`id`, `params`, `notes`) and `leave` (`id`, `camera`); `workshop_snapshot_request {req, id, width?}`. See docs/desk.md "Workshop".
The server tool `workshop_look(question?)` sends `workshop_snapshot_request` (fresh random `req`, `width` 200..1600), waits up to 8 s for the
matching `workshop_snapshot` (same `req` and workshop `id`; bad base64, not a JPEG, > 800 kB, a foreign id, an unknown or repeated `req` are
dropped or fail the request with a readable error, at most 4 requests wait at once) and sends the JPEG to the vision model; it returns
`{ok, critique, parts, image_id?}` (the snapshot is also stored as an upload image). No answer gives `the browser did not answer (the tab may be in the background)`.

#### Workshop sources
A workshop record keeps `sources` (at most 12 deck ids). The `enter` message carries `sources:[{entity_id, title, kind}]`; after it the server
stands each source as an ordinary entity tile on a circle around the table (radius table + 1.2, centred on the workshop origin, idempotent).
Model tool `workshop_sources(add?: string[], remove?: string[])` returns `{ok, sources:[{deck_id, entity_id, title, kind, summary}], notes}`
(summary = stored text, at most 600 characters); removing a source deletes its tile. Items that left the deck (`deck_forget`) are dropped
silently on the next enter or tool call and named in `notes`.

## Conversation

`{t:'new_conversation', clear_scene?: bool}` (button "Nova konverzace" in the chat panel header, Ctrl+Shift+N while the
chat is open; the UI asks "Opravdu?" for 3 s when the chat holds more than 3 messages). The server:

1. stops everything exactly like `stop` (long tools, agent turns, approvals denied, voice session ended);
2. resets the text-chat history to the system prompt, drops the voice resumption handle, transcripts and briefing,
   open model proposals (their ghosts are removed) and the current-model pointer, and forgets the approval
   grants given with `remember: session`;
3. with `clear_scene: true` also clears the scene (`scene` op `clear`) and the selection; the browser closes the view panels;
4. answers `{t:'conversation_reset', clear_scene}` and `notice` "Nova konverzace".

The next `voice_start` opens a fresh Live session (no resumption) and fetches the agent-memory startup briefing again.
Kept: the scene and view panels (unless `clear_scene`), pinned models, language, voice, uploaded files, saved 3D
models, agent memory, MCP connections and the tool registry. Idempotent and safe while idle or while voice is active.

## Live vision input

`frame` messages are forwarded to the open Gemini Live session with
`session.send_realtime_input(video=Blob(jpeg, "image/jpeg"))` (`backend/app/voice/frames.py`); the model then
sees the latest picture when answering voice or `chat` turns (verified with `gemini-3.8-live` and the normal
audio-only session config, no extra setting needed). Limits per connection: 400 kB decoded per frame, 2 frames
per second in total (extra frames are dropped silently), only JPEG, only while a voice session is active
(otherwise dropped). Send roughly 1 frame per second at <= 768 px on the long side. `frames_stop` resets the limiter.

The first frame of a stream (and the first one after `source` switches, or after a reconnect) is preceded by one
context turn `[IMAGE SOURCE: WEBCAM]` or `[IMAGE SOURCE: SCREEN]`, sent with
`send_client_content(turn_complete=False)` so the model gets the label without answering it.

Browser side (`frontend/src/ui/capture.ts`): CAMERA and SCREEN HUD toggles (SCREEN is hidden when
`getDisplayMedia` is missing), draggable 160 px preview with a pulsing LIVE dot. Frames (about 1 per second, long
side <= 768 px, JPEG quality 0.7 lowered until <= 350 kB) are sent only while a voice session is active and the tab
is visible. `frames_stop` is sent and the tracks are stopped on toggle off, voice stop and page unload. Nothing is
stored; permission is requested only on click. Headless test: `node frontend/tests/capture.mjs` (Chrome flags
`--use-fake-device-for-media-stream --use-fake-ui-for-media-stream`; screen capture also needs the fake-device flag).

## Approval of risky tools

A `Tool` with `risky=True` (and optionally `confirm_summary=lambda args: "one line"`) is never run before the user
approves it: the backend sends `confirm_request`, waits up to 60 s for `confirm`, and on deny, timeout or disconnect
answers the model `{"error": "denied by user"}` without running the handler. This applies to the Live session and to
text chat / the `draw` agent alike. Nothing is risky by default. Hermes and MCP tools opt in at registration:

```python
registry.register(Tool(name="ask_hermes", ..., long=True, risky=True,
                       confirm_summary=lambda a: "Ask Hermes: " + a["request"][:160]))
```

`ask_hermes(request)` (`tools_friday/hermes.py`) is registered only when `HERMES_URL` and `HERMES_KEY` are set
(`HERMES_MODEL` defaults to `hermes-agent`, `HERMES_TIMEOUT` to 120 s; Hermes session id is `friday`).

## Models

Two user-selectable roles, pinned in `/srv/data/prefs.json` (`FRIDAY_DATA_DIR`) as `{agent_model, chat_model}`:

- `chat`: only Gemini Live models. The pinned chat model is the model the voice session connects with (read at every
  session start; `GEMINI_LIVE_MODEL`, then `gemini-3.8-live`, is the default when nothing valid is pinned). Text chat
  without a voice session also uses it: one short Live connection per turn with the same tools (all called blocking,
  no NON_BLOCKING). `gemini-3.8-live` rejects `response_modalities=['TEXT']` (close 1007), so the turn is answered
  as AUDIO with output transcription; the audio is dropped and the transcription streams as `chat_delta`. Models
  that accept TEXT use it. Only if the Live turn fails before any text is streamed does the old generateContent path
  (agent loop with the pinned agent model) answer, and a warning is logged. Reply text streams as `chat_delta`
  events sharing one `id`; history is kept per connection.
- `agent`: the executing agent behind the long voice tool `draw(request)`: an OpenAI-style tool-calling loop
  (`app/agent/loop.py`, max 8 tool rounds) over the scene/view tools, reporting `tool` events while it works.

Catalog (`app/agent/catalog*.py`, cached 10 minutes, a failing provider is skipped and retried). Entry:
`{id, provider: 'gemini'|'litellm', label, group, roles: ['chat'|'agent'], caps?: {tools, vision, reasoning}}`.

- chat: Gemini models whose `supported_actions` has `bidiGenerateContent`, minus ids containing `transcribe`,
  `translate`, `genie`, `robotics`; group `google live`. Labels mark `*-extended-thinking` as "async only, no
  scheduling" and `gemini-3.1-flash-live*` as "legacy: no async tools".
- agent: LiteLLM chat models from `GET {LITELLM_BASE_URL}/model/info` (falls back to `/models` without caps when the
  key may not read it): mode `chat`, `supports_function_calling` true, ids containing `embed`, `rerank`,
  `stability`, `nova-2-multimodal` or `image` dropped; group = vendor prefix, label `name (region)`; `caps` come
  from `supports_function_calling` / `supports_vision` / `supports_reasoning`. Plus Gemini `generateContent` text
  models whose id starts with `gemini` (live, tts, image, embedding, aqa, robotics, computer-use, omni, gemma, ...
  dropped), group `google`. The list is complete for the Friday key: LiteLLM exposes only what that key sees
  (for xAI only `global.xai.grok-4.7`; there is no grok 4.8).

Server -> browser: `{t:'models', catalog:[...], pinned:{agent_model, chat_model}}`. Browser -> server:
`{t:'set_model', role:'agent'|'chat', model}`; the model must belong to that role, otherwise the server answers
`error` (unknown role, unknown model, or "not available for role"). The UI shows only entries whose `roles`
include the dropdown's role, grouped, with T/V/R badges and a tooltip for the capabilities. Without an agent pin the
default is `FRIDAY_AGENT_MODEL`, then the newest `gemini-3*-flash` in the live catalog (stable before preview, picked
by version number at runtime, `app/agent/agent_model.py`; `gemini-3.8-flash` until the catalog is loaded). A pin whose
model vanished from its provider's catalog falls back to that default and the server sends a `notice`.

## Approval of risky tools

A `Tool` with `risky=True` (and optionally `confirm_summary=lambda args: "one line"`) is never run before the user
approves it: the backend sends `confirm_request`, waits up to 60 s for `confirm`, and on deny, timeout or disconnect
answers the model `{"error": "denied by user"}` without running the handler. This applies to the Live session and to
text chat / the `draw` agent alike. Nothing is risky by default. Hermes and MCP tools opt in at registration:

```python
registry.register(Tool(name="ask_hermes", ..., long=True, risky=True,
                       confirm_summary=lambda a: "Ask Hermes: " + a["request"][:160]))
```

`ask_hermes(request)` (`tools_friday/hermes.py`) is registered only when `HERMES_URL` and `HERMES_KEY` are set
(`HERMES_MODEL` defaults to `hermes-agent`, `HERMES_TIMEOUT` to 120 s; Hermes session id is `friday`).

## Models

The voice model is fixed (Gemini Live). Two other roles are user-selectable and pinned in `/srv/data/prefs.json`
(`FRIDAY_DATA_DIR`) as `{agent_model, chat_model}`:

- `agent`: the executing agent behind the long voice tool `draw(request)`. It is an OpenAI-style tool-calling loop
  (`app/agent/loop.py`, max 8 tool rounds) that uses the scene/view tools and reports `tool` events while it works.
- `chat`: text chat when no voice session is open. `chat` is answered by the pinned model with the same tools;
  the reply streams as `chat_delta` events sharing one `id`, history is kept per connection.

Catalog (`app/agent/catalog.py`, cached 10 minutes, a failing provider is skipped and retried):
Gemini API text models (`generateContent`, TTS/image/audio/agent models dropped; only generation >=
`MIN_GEMINI_GENERATION = 3` in `catalog_gemini.py`, so 2.x, 1.5 and the `*-latest` aliases are not offered;
`gemini-4-neon` is labelled "(high thinking only)"), provider `gemini`, group `google`;
plus LiteLLM chat models (`GET {LITELLM_BASE_URL}/models`, ids containing `embed`, `rerank`, `stability` or
`nova-2-multimodal` dropped), provider `litellm`, group = vendor prefix of the id (`anthropic`, `openai`, ...) and
label `name (region)`. `set_model` with an id missing from the catalog answers `error`. Without a pin the defaults are
`FRIDAY_AGENT_MODEL` (then the dynamic default above) / `FRIDAY_CHAT_MODEL` (then the Live default).

### Thinking level

One setting for every model: `thinking` in `prefs.json` (`minimal` | `low` | `medium` | `high` | `max`, default `high`,
fallback env `FRIDAY_THINKING`), read on every request. `models` carries `thinking` (current) and `thinking_levels`;
`{t:'set_thinking', level}` validates (unknown level answers `error`), persists, echoes `models` and, during a voice
session, sends the `notice` "applies to the next voice session". Mapping (`app/agent/thinking.py`):

- Live voice and Live text: `thinking_config.thinking_level` (`include_thoughts=false`). Probed: `gemini-3.8-live`
  rejects any thinking config (1007 "Thinking level is not supported"), so it is omitted there; `gemini-3.8-live-extended-thinking`
  requires one (without it 1007 "must be specified"; MINIMAL is rejected, the next level up is sent); `gemini-3.1-flash-live-preview`
  and the native-audio models accept all four levels.
- Gemini agent (`generateContent`): `thinking_level` for 3.x models; `gemini-2.5-*` accept only `thinking_budget`
  (high -1 dynamic, medium 8192, low 1024, minimal 0, or 128 for lite). `gemini-3.1-pro-preview`, `gemini-3.8-flash`, `gemini-flash-latest`
  and `gemini-4-neon` reject MINIMAL. A rejection is learned per model at runtime and the request is retried once.
- `max` is the strongest reasoning each model has. Live voice and Live text clamp it to `high`; Gemini agent models
  have nothing above HIGH (`thinking_level=HIGH`; the 2.5 budget path is -1 dynamic). `gemini-4-neon` accepts HIGH only.
  The UI hint says "Maximum pro agentni modely (hlasovy model max. vysoke)".
- LiteLLM (`thinking_litellm.py`): `reasoning_effort` (`minimal` -> `low`), only for models whose catalog `caps.reasoning`
  is true. `max` sends the model's strongest effort: `caps.max_effort` (`max` or `xhigh`, from `/model/info`
  `supports_max_reasoning_effort` / `supports_xhigh_reasoning_effort` / `reasoning_effort_levels`; such entries get
  the label suffix "(max thinking)"), else `high`. A 400 that lists the allowed values ("must be one of ...") sets the
  model's learned ceiling to the highest listed value and the call is retried; a 400 without a list steps max ->
  xhigh -> high, then drops `reasoning_effort` and remembers that. Probed on the real proxy: Claude, GPT, Kimi,
  Qwen and Grok ids accept low..xhigh and max, and a `thinking: {type:'enabled', budget_tokens}` passthrough as well;
  DeepSeek rejects xhigh/max (400, no list). No `thinking` budget is sent: every Claude id that advertises
  adaptive thinking also advertises max effort.
- A first Live connect failure ends with an `error` ("voice model X did not accept the connection: ...") and `state: idle`.

### Language and voice

`prefs.json` additionally holds `language` (default `cs-CZ`, fallback env `GEMINI_LANGUAGE`; also `en-US`, `sk-SK`,
`de-DE`, `pl-PL`, `es-ES`, `fr-FR`, `it-IT`, `uk-UA`) and `voice` (a map model id -> prebuilt voice id). Both are read
at every Live session start: `speech_config.language_code`, the voice, the system prompt (Czech persona for `cs-CZ`,
otherwise a first line "Answer in X unless the user switches language") and `input_audio_transcription.language_codes`.
Text chat uses the same language. Changing the chat model re-sends `models` with that model's voices; a pinned voice
that the new model does not offer falls back to the default voice (Kore, a female voice, documented as "firm";
`GEMINI_VOICE` overrides the default). When a voice session is active a language, voice or chat-model change is answered
with a `notice` ("applies to the next voice session"); the session is not restarted.

Probed against the real API (Live turn with audio out, all 30 prebuilt voices): every voice connects on
`gemini-3.8-live` and `gemini-2.5-flash-native-audio-latest`, so `voices_for(model)` returns all 30 for every model
(override table `MODEL_VOICES` in `app/voice/voices.py`). The native-audio models reject `cs-CZ`, `sk-SK` and `es-ES`
(close 1007 "Unsupported language code"); for them the code is omitted from `speech_config` and the model follows the
prompt. `gemini-3.8-live-extended-thinking` needs a thinking level and does not connect with this config.

### Speaker profile and self-echo

With `audio_profile: speaker` the next Live session uses `automatic_activity_detection` with `silence_duration_ms` 900,
`prefix_padding_ms` 300 and low start/end sensitivity (constants `SPEAKER_*` in `voice/session.py`); `headphones` uses
the `FRIDAY_VAD_*` values above. `activity_handling` is always `START_OF_ACTIVITY_INTERRUPTS` (barge-in stays on). The relay
also drops a model turn whose input transcript matches Friday's own last output transcript (normalised, similarity
>= 0.85, within 3 s): audio of that turn is not forwarded, the browser gets `interrupted` and, once per connection,
`notice` "Ozvena potlacena" (`voice/selfecho.py`).

### Czech recognition

- Mic capture downsamples with a windowed-sinc low-pass (cutoff 7.2 kHz) before decimation to 16 kHz, so 48 kHz and
  44.1 kHz input does not alias (`frontend/src/audio/resample.js`, check: `node frontend/tests/resample.mjs`).
- Turn detection (`realtime_input_config.automatic_activity_detection`) env constants: `FRIDAY_VAD_SILENCE_MS` (700),
  `FRIDAY_VAD_PREFIX_MS` (200), `FRIDAY_VAD_START` and `FRIDAY_VAD_END` (`low` or `high`, default `low`). Longer
  silence avoids cutting Czech sentences at mid-sentence pauses; lower the values for snappier turns.
- Also affecting recognition: a headset microphone close to the mouth beats laptop speakers and microphone (echo,
  room noise); browser echo cancellation is on and works best with a headset. Quality can only be judged by ear on the
  real device.

## Approval

A tool that needs the user's consent is held until the browser answers (UI: `frontend/src/ui/confirm.ts`, a modal
dialog; several requests queue and are shown one at a time; Deny is the default focus, Enter never allows).

Server -> browser:

| `t` | Fields | Meaning |
|---|---|---|
| `confirm_request` | `id`, `tool`, `summary`, `args` (any JSON), `expires_in` (seconds) | ask the user; the dialog shows a countdown from `expires_in` |
| `confirm_closed` | `id`, `reason` | the request is no longer pending (expired, answered elsewhere, cancelled); the dialog closes without answering |

Browser -> server:

| `t` | Fields | Meaning |
|---|---|---|
| `confirm` | `id`, `allow: boolean`, `remember?: "once"\|"session"` | answer; `remember` is sent only with `allow: true` (`session` = do not ask again for this tool during the session) |

Closing with Escape or the Deny button sends `allow: false`. The browser never answers a request after `confirm_closed`.

## Scene DSL (v1)

Every object has a stable `id`. Patches are idempotent. The backend (`app/scene_schema.py`) rejects unknown ops,
kinds and props, and caps the scene at 5000 objects; a batch with any invalid op is rejected as a whole.
Frontend kinds live in `frontend/src/scene/kinds/`.

Ops:

| Op | Fields |
|---|---|
| `add` | `obj`: Obj (same id replaces) |
| `set` | `id`, `props` (any Obj prop except `id`/`kind`), `ms?` (tween `pos`/`rot`/`scale`/`color` over that many ms) |
| `del` | `id` (children are removed too) |
| `clear` | |
| `camera` | `pos`, `look?` (camera glides) |
| `explode` | `factor` (0 restores; animated). Top-level objects move away from their centroid, children away from their parent's origin |

Common Obj props: `id`, `kind`, `pos [x,y,z]`, `rot [rx,ry,rz]` (radians), `scale` (number or `[x,y,z]`), `color` (CSS colour),
`label`, `parent` (id of a `group` or any object; transform is relative to it), `opacity`, `visible` (false hides the object and its children),
`ref` `{type: image|file|model|memory|tool, id}` (which stored item the object stands for; id up to 80 chars of letters, digits and `_ . : -`; shown by `scene_get`),
`anim`: `{type: spin|bob|pulse|orbit, speed?, axis?: x|y|z, amp?}` or a list of those.
`spin` rotates around `axis` (default y), `bob` oscillates along `axis` by `amp` (0.25), `pulse` scales by `amp` (0.12),
`orbit` circles in the plane normal to `axis` with radius `amp` (1).

| Kind | Kind-specific props |
|---|---|
| `box sphere cylinder cone torus plane` | none (unit size, use `scale`) |
| `group` | none; children use `parent` and move/animate with it |
| `text` | `text` (use `\n` for lines), `size` (line height, 0.5); camera-facing sprite |
| `label` | `text`, `size`, `target` (id; sits above that object's bounds), `offset [x,y,z]`; framed tag |
| `line` | `from`, `to` |
| `polyline` | `pts [[x,y,z],...]`, `closed` |
| `arrow` | `from`, `to`, `head` (0.3) |
| `particles` | `pts` or generator `gen`: `spiral\|galaxy\|grid\|sphere\|random` with `count` (1500, max 20000), `radius`, `seed`, `turns`, `height`, `arms`, `spacing`; `size`, `color2` (outer colour) |
| `image` | `url` (http(s), `data:` or `/path`), `w` (3), `h` (follows aspect) |
| `graph` | `nodes [{id,pos,label?,color?,size?}]`, `edges [[from,to],...]`, `directed`, `node_size` |
| `chart3d` | `values`, `labels`, `gap`, `height` (tallest bar, 3), `color2`, `show_values` |
| `surface` | `data` (2D array) or `fn` (expression of `x`,`z`, e.g. `sin(x)*cos(z)`), `res`, `range [min,max]`, `size [w,d]`, `height`, `color2` |
| `gltf` | `url`, `fit` (largest dimension, 2) |
| `entity` | `shape` (`image doc book table code audio archive tool model note`), `title`, `subtitle?`, `thumb?` (url, keeps its aspect), `accent?` (frame colour); holographic tile with a link port. Double-click sends `entity_open` when `ref` is set; context menu: open, link, remove from the deck |
| `link` | `from`, `to` (object ids), `label?`, `style?` (`solid\|dashed`), `color?`; glowing curve with flowing particles that follows both endpoints every frame and hides when one is missing |
| `extrude` | `walls [[x1,y1,x2,y2],...]`, `thickness` (0.2), `height` (2.5), or `outline [[x,y],...]` polygon; `floor` (true). Plan x,y maps to world x,z |
| `lathe` | `profile [[r,y],...]` (2..64 points, `r >= 0`, finite, below 1e4) turned around the y axis (vases, bottles, bowls, wheels), `segments` (3..96, 32), `cap` (true: both ends are closed against the axis) |

Selection: clicking an object in the 3D view sends `{t:"select", ids}` (shift-click toggles, clicking the sole selected
object again selects its parent, empty space clears). The backend keeps `scene.selected` and `scene.describe()` returns a
compact text tree (id, kind, pos, colour, label; `*` marks selected) for the `scene_get` tool.

Demo: with `FRIDAY_DEMO=1`, the browser may send `{t:"demo", what:"scene"}`; the server replies with `scene_full` showing
every kind, then a `camera` op. Open the UI with `?noorb` to hide the orb (headless tests).

Anything beyond these kinds goes through code mode (sandboxed iframe, step 6).

Entities: `show_in_scene`, `file_to_scene` and the `image_to_scene` message add an `entity` object `ent-<kind>-<id8>` with a `ref`,
placed by a deterministic auto-layout (`app/entities/layout.py`: next free slot on an arc in front of the camera, spacing >= 3.5).
Dropping a file no longer opens the 2D card; double-click it. The client selects the new entity, glides to it and shows a toast; see docs/desk.md for the action bar, the Deck window and the browser messages `deck_list`, `deck_open`, `deck_place {id, pos?}`, `deck_pin`, `deck_tag`, `deck_forget` and the server messages `deck`, `deck_changed`. Tools: `entity_link(from_id,to_id,label?,style?)`, `entity_unlink(link_id)`,
`entity_list()`, `entity_open(id)`, `entity_arrange(layout: arc|grid|around, center_id?)` (tweened `set` ops) and
`entity_run(tool_entity_id)`: runs the tool of a `ref.type: "tool"` entity on the file/image entities linked to it through the normal
tool path (risky tools ask for approval); only tools with a `ref` parameter (`read_file`, `summarize_file`, `analyze_image`) accept this.

## Workshop part tree

`backend/app/workshop` turns a data-only spec (no code from the model) into model3d parts. `expand(spec)` returns
`Expanded(parts, params, notes)`; `parts` are dicts accepted by `Part.from_dict` (kind props in `geom`, rotation in radians,
`props.source` = the spec part id), `params` is `[{name,label,value,min,max,step,unit}]`, `notes` lists clamped values and
approximations. `with_params(spec, values)` returns a new spec with values clamped to each parameter's range. Every
`SpecError` message names the field path (`parts[3].size[1]: unknown parameter 'wdth'; did you mean 'width'?`).

Spec: `{name, units: mm|cm|m, params: {name: number | {value,min,max,step,label,unit}}, parts: [...]}`. Kinds: `box`, `sphere`,
`cylinder` (`r` or `r1`+`r2`; a zero radius gives a cone), `capsule`, `torus`, `plane`, `extrude`, `lathe` (`profile [[r,y],...]`, `segments` 24), `polyline`, `label`, `group`.
Common keys: `id`, `kind`, `name`, `pos`, `rot` (degrees), `color`, `material {metal,rough,opacity}`, `parent` (a group), `tags`
(first tag is the layer), `mirror` (`x|y|z`, copy `<id>.m`) and `array` (`linear {count,step}` or `radial {count,axis,radius,
start_deg}`, members `<id>.<i>`). Numbers may be `"=expression"` strings (hand-written evaluator, 160 characters, depth 12,
200 nodes). Caps: 2000 parts after expansion, 40 parameters, group depth 6, array count 200; exceeding one is a `SpecError`.
The LLM-facing description is `app.workshop.doc.SPEC_DOC`.

## View panels

`{t:'view', id, kind, title?, data}` opens a draggable, resizable glass panel over the canvas;
`{t:'view_close', id}` closes it. Built by `backend/app/views.py::view_msg(kind, data, title=None)`,
which rejects unknown kinds and payloads over 2 MB. Model text is never inserted as HTML.

| `kind` | `data` |
|---|---|
| `image` | `{url, alt?, caption?}` - `url` is http(s), a same-origin path, or a `data:image/...` URI |
| `chart` | `{type: line\|bar\|pie\|scatter\|radar, labels?: string[], datasets: [{label?, data: number[]}]}`; for `scatter` each `data` item is `[x, y]`; `pie` uses the first dataset and `labels` |
| `table` | `{columns: string[], rows: (string\|number\|boolean\|null)[][]}` - click a header to sort |
| `markdown` | `{text}` - headings, bold/italic, inline and fenced code, lists, quotes, links (http/https only); raw HTML is shown literally |
| `code` | `{code, lang?}` - monospace, light highlighting, copy button |
| `diagram` | `{code}` - mermaid source, rendered to SVG (mermaid is lazy-loaded, `securityLevel: strict`) |
| `map` | `{center: [lat, lon], zoom?: 0-18, markers?: [{lat, lon, label?}]}` - 3x3 OpenStreetMap tile grid |
| `json` | `{value}` - collapsible tree |
| `memory_graph` | `{nodes: [{id, label, kind: project\|session\|memory\|concept\|file, weight 0-1, ts (ms epoch, 0 = none), project}], links: [{source, target, kind, weight}]}` - memory orbs (3d-force-graph); at most ~300 nodes, every link endpoint is a node id; link kinds: `in` (session/memory to project), `seen_in` (concept/file to session), `tagged` (memory to concept), plus agentmemory edge types (`uses`, `modifies`, `related_to`, ...) Optional keys of a query-focused graph (`memory_search`, `show_memory_graph` with `query`): `query` (string), `highlight` (node ids, most relevant first: the orbs to light up; the rest of `nodes` is 1-hop context, at most 120 nodes, hits first), `hits` (top 12 `{id, label, kind, score, snippet <= 160 chars, ts, project}`) and `summary` (<= 400 chars of plain text built from the top hits, no model call; "Nic nenalezeno k dotazu ..." with empty `nodes`/`highlight` when nothing matches). Node ids are the same as in the generic graph. Labels/snippets are untrusted memory text: control characters stripped, render as text only. |

Client behaviour for a query-focused `memory_graph` (frontend `views/memory_view.ts`, `memory_hits*.ts`): the panel is updated in place when a second `memory_graph` view arrives (`ViewHost.show` folds a view of the same kind into the open panel when its renderer returned an `update` function; no second window, `view_close` of either id closes it). Enter in the toolbar search box or the magnifier button sends `memory_search` and shows "Hledam v pameti..." until that view arrives (30 s timeout). `highlight` ids that are not nodes of `nodes` are ignored; the highlighted orbs get the emphasis ring and full opacity, all others recede to 0.35, the camera flies to `highlight[0]` and fits the highlighted subset once. `hits` (at most 12, best score first) are listed in a collapsible panel under the `summary` and a query chip with the hit count; a row click or Enter selects the node and opens its card. The same state is shown when the model calls `show_memory_graph(query)` without a prior browser message (search box pre-filled with `query`). "Zrusit hledani" / Esc restores the last generic dataset client-side (no server rebuild; if the panel was opened by a query, `show_memory_graph` is sent). Nothing is persisted.
| `file_card` | see "Files" - tile for a dropped document (summary, outline, tables, excerpt, download link, buttons) |
| `image_card` | `{url, summary, kind, people_count, objects: [{label, count}], text_found: string[], exif: {camera_make?, camera_model?, taken_at?, orientation?, lat?, lon?}, notes, scene?, location_hint?, rooms?: [{name, dimensions}], dimensions_hint?, confidence?}` - visual overview of an uploaded image; `kind` is `photo\|floorplan\|screenshot\|drawing\|document\|other`, `people_count` may be null |

## Images

Awareness from images (`backend/app/vision/`). The browser sends `{t:'image_upload', id?, name, mime, data_b64, analyze?}`
(raw WebSocket frames up to 20 MB are accepted by uvicorn `--ws-max-size`). The server checks the magic bytes against
the declared mime (jpeg, png, webp, gif only), decodes the image with Pillow (`MAX_IMAGE_PIXELS` 40 MP, decompression
bombs rejected), stores the untouched original as `<FRIDAY_DATA_DIR>/uploads/<uuid>.<ext>` plus a downscaled
analysis copy (max 1600 px, JPEG) and a metadata file, then answers `image_ready {id, client_id?, url, w, h, exif}`
(`client_id` echoes the message `id`; `w`/`h` are the upright size). A rejected upload answers `error {message, id?}`.
Unless `analyze` is `false` the server then analyses the image in the background and emits an `image_card` view
(panel id `image-<first 8 chars of the id>`) and a `notice`.

HTTP alternative: `POST /api/upload` (multipart field `file`) stores the image and returns the `image_ready` payload as
JSON (400 invalid, 413 too large); it does not start the analysis. `GET /api/uploads/<uuid>.<ext>` serves the original
with `Content-Disposition: inline`, `X-Content-Type-Options: nosniff` and a sandboxing CSP; any other name is 404.

EXIF is parsed to `{camera_make, camera_model, taken_at, orientation, lat, lon}` (GPS as decimal degrees; no
reverse geocoding). Raw EXIF blobs are never sent to the browser nor to a model.

Analysis uses the pinned `agent` model when it supports vision (Gemini models, LiteLLM models whose
`/model/info` says `supports_vision`), else `gemini-flash-latest`, through `agent.llm.chat` with OpenAI-style image
parts (`{type:'image_url', image_url:{url:'data:...'}}`; Gemini receives inline_data). The model must answer one strict
JSON object; an invalid reply is retried once, then the analysis fails with an error. Image content is untrusted data.

## Photo editing and house from sources

Package `backend/app/imaging/`. Tools (all registered per connection by `register_imaging_tools`):

- `image_edit {image_ids (1-6), instruction, operation?, full_res?}` (long, WHEN_IDLE): sends the stored photos (the 1600 px
  analysis copies unless `full_res`) plus an English prompt template (`merge_people`, `enhance`, `remove_background`,
  `outpaint`, `custom`; the user text is appended) to a Gemini image model via `generate_content` with
  `response_modalities ['IMAGE','TEXT']`. The model is `gemini-3.1-flash-image`, falling back to `gemini-2.5-flash-image`
  when the first errors or is not in the live list; the working one is cached; `FRIDAY_IMAGE_MODEL` (a Gemini image id) pins it.
  Images are never sent to any other model. The result (re-encoded, EXIF-free, <= 12 MB) is stored as a NEW upload with
  `derived: {derived_from: [ids], instruction, operation, model}` in its metadata and announced as
  `image_ready {..., derived}`; the originals are untouched. Empty instruction, more than 6 inputs, unknown ids and a
  `merge_people` with one image are refused; timeout 90 s; a blocked or text-only answer returns a readable `{error}`.
  The result is AI-generated and may not preserve faces exactly.
- `image_compare {a_id, b_id}`: two `image` views (`compare-before`, `compare-after`).
- `house_from_sources {file_ids?, image_ids?, notes?}` (long): up to 3 PDFs (files store, sent natively as
  `application/pdf`) and 8 images go into ONE Gemini analysis (pinned agent model when it is a Gemini model, else
  `gemini-flash-latest`) that must answer a strict JSON object (storeys, rooms with metre sizes, confidence and
  `dimension_candidates`, relative position, doors/windows per wall, exterior facts, interior facts, scale hints, conflicts,
  open questions); an invalid reply is retried once. `imaging/spec_merge.py` maps it onto the `building` pack: the most
  confident dimension wins and disagreements are reported, rooms are placed next to the room they name (else beside the
  others, with a question), doors and windows that do not fit a wall are dropped one by one and listed, a window grid fills
  the front facade, missing sizes become 3.5 x 4 m with a question (or the outside footprint when no size is stated at
  all), more floors outside than on the plans repeat the ground layout. It replaces the model `house` through
  `pack_generate` and frames the camera. Returns `{ok, model_id, summary, open_questions[], conflicts[], sources, parts}`.
- `house_refine {image_ids, notes?}` (long): reads a later inside photo against the rooms of `house` and stages a
  `model_propose` proposal (floor colour, missing furniture; stable ids, nothing regenerated); the user accepts or rejects.

The `building` pack spec gained an optional `wall_color` (`#rrggbb`).

## Files

Any file can be dropped or attached (`backend/app/files/`). The browser sends
`{t:'file_upload', id?, name, mime, data_b64, analyze?}` (`image_upload` still works and stays image-only; a
`file_upload` whose content is an image takes the image path). The type is decided from the content (magic bytes,
zip members) and the extension; the declared mime is ignored. Kinds: `image`, `pdf`, `docx`, `xlsx`, `epub`, `odt`,
`zip` (listing only, never unpacked), `csv` (also tsv), `text`, `markdown`, `code`, `json`, `yaml`, `toml`, `xml`,
`html`, `rtf`, `audio`, `video` (stored, "transcription not available yet"), `binary` (hex head and size).
A file whose name says pdf/docx/... but whose content is not that format is kept as `binary` with a `note`.

Limits: 25 MB decoded, 200 kB of extracted text (`truncated`), tables 200 rows x 30 columns, zip archives at most
5000 entries / 200 MB unpacked / a compression ratio of 200 (else the file is kept with a `note` and no text). XML goes
through defusedxml, HTML is reduced to text without scripts or styles, control characters are removed, nothing is
fetched and no macro is executed. Files are stored as `<uuid>.bin` (+ `.txt` text and `.file.json` metadata) in
`FRIDAY_DATA_DIR/uploads`; the original name is metadata only.

The server answers `file_ready {id, client_id?, kind, name, size, url, meta}` and, for non-images, emits a `file_card`
view `{id, name, kind, size, title, summary, meta, outline[], tables?: [{name, columns, rows}] (50 rows), text_excerpt
(6000 chars), truncated, download_url, note?}`. `GET /api/files/<id>` downloads the original with
`Content-Disposition: attachment`, `nosniff` and a sandbox CSP. `POST /api/upload` accepts any file (images behave as
before; others return the `file_ready` payload). With a Live session active the model also gets a context turn
"User attached <name> (<kind>, <n> pages); use read_file to read it" without being asked to answer.
The card buttons send chat messages ("Precti dalsi cast souboru <name>", "Shrn soubor <name>"). Extracted text is
untrusted data: tools wrap it in `<file-content>` and say so.

Model tools: `read_file(file_id, part?)` (20 kB per part), `list_files()`, `file_to_scene(file_id)` (emits the
`file_card` tile), `summarize_file(file_id)` (agent model, first ~30 kB, <= 600 chars). Run uvicorn with a
`--ws-max-size` of at least 36 MB (a 25 MB file is ~34 MB of base64).

## Web pages on the deck

A web page can be kept as a deck item and a desk entity (`backend/app/webpages/`). The browser sends `{t:'web_add', url}`
(the Deck top bar has a small "Pridat odkaz" input; Enter sends it); failures come back as `{t:'error', message}`. The model has
`web_add(url, place=true)` (long, WHEN_IDLE), `web_refresh(deck_id)` (long), `web_read(deck_id, part?)` (20 kB parts, text wrapped in
`<web-content>` with an `untrusted` note) and `web_compare(ids[2..6])` (stored texts trimmed to a 24 kB budget, `cut` flag, no
model call). Drag-and-drop of URLs and automatic fetching of links pasted into the chat are NOT implemented.

The server fetches on behalf of the user, so every fetch is guarded (SSRF): only http/https, ports 80/443 (8080/8443 when listed in
`FRIDAY_WEB_PORTS`), no user name or password, URLs up to 2048 characters, no decimal/octal/hex IP spellings, no `localhost`,
`.local`, `.internal` names. The name is resolved once, EVERY answer must be a public address (loopback, private, link-local,
carrier-grade NAT, multicast, reserved, and IPv6 forms that embed an IPv4 address are refused) and the socket is connected to that
checked address (the name is kept for TLS and the Host header), then the connected peer is checked again (DNS rebinding). Redirects
are followed by hand (at most 5) and every hop goes through the same checks. Limits: 10 s connect, 20 s total, 5 MB body (aborted
while streaming), no compression, types text/html, application/xhtml+xml, text/plain, application/pdf and jpeg/png/gif/webp only.
No cookies or credentials are sent; the User-Agent is `FridayBot/<version>`. Static HTML only: no JavaScript is run.
`FRIDAY_WEB_FETCH=0` switches the feature off; `FRIDAY_WEB_ALLOWLIST` / `FRIDAY_WEB_DENYLIST` are comma separated host patterns
(a name matches itself and its subdomains, `*` makes a glob; the deny list wins). A PDF or an image is handed to the existing
file or image pipeline and appears like a dropped file.

HTML becomes readable text with the standard library (headings, lists, tables, up to 50 links as `[text](url)`, 200 kB cap with
`truncated`) plus title, canonical URL, site, author, date, language and description. A snapshot is kept in
`FRIDAY_DATA_DIR/web/<id>/{meta.json,text.txt}` where `<id>` is the hash of the normalised URL (lower-case host, default port,
fragment and tracking parameters dropped), so the same URL again refreshes the same snapshot and raises `fetch_count`; raw HTML is
never stored or served. The deck item has type `web` (subtitle = host, `meta {url, fetched_at, bytes, lang, fetch_count}`, full
text search over the description and the first 4000 characters); the entity has `ref {type:'web', id}` and shape `doc`. Opening
it emits a `file_card` view with `kind:'web'`, `source_url` (the card shows [Otevrit original], `rel=noopener noreferrer`) and
`web_id` (the buttons [Obnovit] and [Shrnout] send chat messages). A page text is untrusted data.

## Model tools

Registered per browser connection by `backend/app/tools_friday/` (`register_all(registry, ctx)`; `ctx.scene` is the
`SceneStore`, `ctx.emit` sends JSON to that browser). Handlers return a JSON object; on failure `{"error": "..."}`
naming the bad field (e.g. `op #1: pos must be [x, y, z] numbers`) so the model can correct itself. A rejected
`scene_apply` changes nothing and emits nothing. The `scene_apply` description is generated from `scene_schema.py`
constants (kinds, props, ops), the `show_view` one from `views.VIEW_KINDS`.

| Tool | Args | Effect / result |
|---|---|---|
| `scene_apply` | `ops`: Op[] | validates and applies atomically, emits `scene {ops}`; `{ok, objects}` |
| `scene_get` | | `{scene}`: text tree from `scene.describe()` incl. selected ids (`*`) |
| `scene_clear` | | `clear` op; `{ok, objects: 0}` |
| `scene_camera` | `pos`, `look?` | `camera` op |
| `scene_explode` | `factor` | `explode` op (0 restores) |
| `selected_objects` | | `{ids, objects}`: what the user clicked in the 3D view |
| `show_view` | `kind`, `data`, `title?`, `id?` | emits `view` (see "View panels"); `{ok, id}` |
| `close_view` | `id` | emits `view_close`; `{ok}` |
| `recall` | `query`, `days?` | long tool (WHEN_IDLE): agentmemory hybrid search, deduplicated, ~1500 chars with ids; `{memory, notice}` |
| `today_digest` | | long tool: last 24 h of sessions by project with key observations; `{memory, notice}` |
| `remember` | `content`, `project?` | blocking; saves to agentmemory only when the user asks; `{ok, id}` |
| `show_memory_graph` | `query?`, `project?`, `days?` | long tool (WHEN_IDLE; a cold build takes 8-12 s): emits `view` kind `memory_graph`; with `query` it is the query-focused graph (use it for "co jsme resili o X"; tell the user the `summary` aloud), without it the generic overview; `{ok, id, nodes, links}` plus `{highlight_count, summary}` for a query |
| `analyze_image` | `image_id` (id or unique 8+ char prefix), `force?` | long tool (WHEN_IDLE); vision analysis, cached per image, emits the `image_card` view; `{ok, image_id, url, exif, analysis}` |
| `list_images` | | `{images: [{image_id, name, url, w, h, analysed, kind}]}` newest first |
| `show_in_scene` | `image_id`, `pos?`, `scale?` | adds scene object `img-<id8>` of kind `image` (3 units on the long side times `scale`, aspect kept) |

Memory tools live in `backend/app/memory/` (`register_memory_tools`, wired in `agent_wiring.py`). They reach agentmemory at
`AGENTMEMORY_URL` with `AGENTMEMORY_SECRET` (bearer); recalled text is returned inside `<memory-data>` with a notice that it
is reference data, not instructions. The voice session start adds a briefing (last 5 decisions plus a 24 h headline,
max 600 chars, `memory.briefing.startup_context()`) to the system prompt and silently skips it when memory is unreachable.

## Parametric models

`backend/app/model3d/` is a domain-agnostic assembly layer (no knowledge of houses, PCBs or enclosures). Tools are
registered by `register_model_tools(registry, ctx)` (wired in `agent_wiring.py`); errors come back as `{error}`.

- **Part**: `id`, `kind` (any scene kind), `name`, `parent`, `pos`, `rot`, `scale` (for unit primitives the size in
  model units), `color`, `opacity`, `layer`, `tags[]`, `props{}` (free metadata, never drawn), `geom{}` (kind props
  such as `pts`, `text`, `url`), `visible`. **Model**: `id`, `units` (mm default), `scale_to_scene`, `parts`,
  `layers{name: {visible, opacity, color, z_index}}`. Limits: 5000 parts, unique ids, existing parent, no cycles.
- **Storage**: `<FRIDAY_DATA_DIR>/models/<id>.json`, atomic write (temp + rename). Every change pushes an undo state
  (cap 50, in memory); named snapshots via `model_snapshot` / `model_restore`.
- **Scene mapping** (`compile.py`): root group `model:<id>` (scale = `scale_to_scene`, so model units become scene
  metres), part objects `m:<id>:<part>`. A redraw is `del model:<id>` plus re-adds, so nothing else in the scene is
  touched. Layer `color` overrides part colour, opacities multiply, hidden layers/parts are not emitted.
- **Explode** (`explode.py`): `set` ops with `ms` animation. `by=layer` stacks layers by `z_index` along `axis`;
  `group` stacks top-level parts; `radial` moves away from the centroid. `factor 0` animates back. The model is not
  modified (a later redraw resets the view).
- **Proposals** (`proposals.py`): `model_propose(changes)` with `changes = [{op: add|edit|remove, part|id, props}]`
  draws translucent ghosts `ghost:<proposal>:<part>` (green add, amber edit, red remove) and returns a diff;
  the model is untouched until `model_accept` (undoable); `model_reject` removes only the ghost.
- **Packs** (`packs/`): `register_pack(name, fn, example=, defaults=, units=, layers=)`; `pack_list` shows an example
  spec per pack. `pack_generate(pack, spec?, model?, dry_run?, frame?)` fills missing spec fields from the pack
  `defaults` (pcb 60x40 mm with 3 parts, enclosure 60x40x20 mm, building two rooms), then creates or replaces the model,
  draws it and frames the camera; `dry_run` returns only part dicts.
- **Ids**: model ids are normalised (lower case, other characters become `_`), so `PCB Model` and `pcb_model` are one
  model. `model_create` on an existing id returns `{error: "... exists ..."}`. `model_list` also returns `details`.
- **Visibility**: `Model.auto_fit` (default true) scales the root group so the longest side is 4 scene units when it
  would otherwise be under 1 or over 20; `scale_to_scene` stays the true scale and `model_measure` reports model units.
  Creating a model, `pack_generate`, `model_explode` and changes that grow/shrink the model by half emit one `camera` op
  (3/4 view from `bounds.py`); pass `frame: false` to suppress it.

| Tool | Args |
|---|---|
| `model_create` | `id`, `units?` |
| `model_add_part` / `model_edit_part` / `model_remove_part` | `part` / `id, props` / `id` (children go too) |
| `model_group` | `id`, `parts[]` |
| `model_layer_set` | `layer`, `visible?`, `opacity?`, `color?`, `z_index?` |
| `model_explode` | `factor`, `by?`, `axis?`, `spacing?` |
| `model_get` / `model_measure` / `model_annotate` | text tree / `a, b` / `part, text` |
| `model_undo` / `model_redo` / `model_snapshot` / `model_restore` | `name` for the last two |
| `model_list` / `model_clear` | `model_clear` is risky (needs approval) |
| `model_propose` / `model_accept` / `model_reject` | `changes` / `proposal` / `proposal` |
| `pack_list` / `pack_generate` | `pack, spec` |

All tools take an optional `model` id; the last used model is the default.

## MCP and search

**Voice search.** The Live session always carries Google's built-in `{'google_search': {}}` next to our function
declarations (`voice/session.py: live_tools`). It runs on Google's side; verified to coexist with NON_BLOCKING
declarations on `gemini-3.8-live`. The text/agent models get the function tool `web_search(query)`
(`tools_friday/search.py`, a `gemini-flash-latest` call with google_search grounding, `FRIDAY_SEARCH_MODEL` to
override) returning `{note, answer, sources[<=5]}`; the answer is capped at 1500 chars and wrapped in
`<web-search-result>` as untrusted data. It is not declared to Live (which has the built-in search).

**MCP client** (`backend/app/mcp/`). Servers come from `mcp_servers.json`: `$FRIDAY_MCP_CONFIG` (empty disables),
else `/srv/data/mcp_servers.json`, else the file shipped in `backend/`. Connections are created lazily once per
process (`hub.discover()`, shared by all browser connections) and each `AgentSession` registers the same tools in
its own registry (`register_mcp_tools`, one line in `agent_wiring.py`). Tools appear in the registry as soon as
discovery finishes; a server that is down only logs a warning (`continue_on_error`).

Rules enforced by the router (`mcp/router.py`):

- Tool name `<server>__<tool>`; description from MCP; `inputSchema` sanitised for Gemini (`mcp/schema.py`: drops
  `$schema`, `additionalProperties`, `default`, `title`, `$defs`; collapses `anyOf` / type lists to one type plus
  `nullable`). Verified against the real Live API.
- Only tools in `allowed_tools` are exposed. Empty or missing allowlist: tools are discovered, none is exposed, a
  warning is logged.
- Every exposed tool is `risky=True` (approval dialog, see above) unless `tool_policies.<tool>.risky` is `false`.
  `"long": true` makes it NON_BLOCKING. `allowed_names` restricts the `name` argument (Home Assistant entities).
- Results: max 6000 chars, wrapped in `<mcp-result server= tool=>` with a note that it is untrusted data.
- Errors, timeouts (`connect_timeout` 15 s, `call_timeout` 60 s) and one reconnect become `{error}` payloads.

`GET /api/mcp/status` returns per server: `enabled`, `connected`, `error`, `discovered`, `exposed`, `blocked`
(names only, no URLs with secrets, no tokens).

**Add a server.** Edit `/srv/data/mcp_servers.json` (it overrides the shipped file) and restart:

```json
{"mcpServers": {"notes": {
  "transport": "streamable-http",
  "url_env": "NOTES_URL", "path": "/mcp",
  "token_env": "NOTES_TOKEN",
  "allowed_tools": ["search_notes", "add_note"],
  "tool_policies": {"search_notes": {"risky": false}, "add_note": {"long": true}}
}}}
```

`url` may be given directly instead of `url_env`; `headers_env` maps extra header names to env var names; `sse`
is the other transport. Secrets are only ever referenced by env var NAME. Environment variable names used by the
shipped config: `MCP_HUB_URL` (URL of an MCP hub, e.g. `https://mcp.example.com`; the shipped `hub` entry stays disabled until it is set; from Docker use
`http://host.docker.internal:<port>` for a hub on the host, the compose file maps it), `MCP_HUB_TOKEN` (full header value or bare
token; a hub usually needs `Authorization: Bearer ...`), `HA_URL` and `HA_TOKEN` (Home Assistant, disabled until `HA_URL`
is set). The shipped `hub` entry exposes only read-only documentation and search tools.
