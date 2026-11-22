# Changelog

Versions are `YYYYMMDD.X` (build day and the counter of that day).

## [20261122.2] - 2026-11-22

### New
- Voice picker lists only female voices. `FRIDAY_SHOW_MALE_VOICES=1` (env / `.env`, for example in Docker) shows the male voices too; a pinned or `GEMINI_VOICE` male voice falls back to the default (`Kore`) while they are hidden.

### Changed
- The version is now the same everywhere: the image, `/health` and the changelog carry the number the release pipeline tags (a local build passes it with `FRIDAY_VERSION`).
- README: the default voice is `Kore` (it said `Algieba`).

## [20261122.1] - 2026-11-22

### New
- 3D asset catalog (`backend/app/assets`): a curated index of 271 CC0 models (furniture, plants, trees, animals, people, vehicles, buildings,
  street items, props from Quaternius and Kenney packs). Tools `asset_find` (offline search, Czech and English words), `asset_place` (downloads
  on first use, adds a labelled `gltf` object) and `asset_credits`; the settings gear has a collapsible "Zdroje modelu" list. Models are
  never committed: they are fetched into `<FRIDAY_DATA_DIR>/assets` through the SSRF-guarded fetcher. `scripts/build_asset_index.py`
  regenerates the index from `scripts/asset_packs.json`. See docs/protocol.md.
- Model fallback ladder (`backend/app/agent/fallback.py`): the agent role retries a rate limited or failing model on up to 3 same-role
  alternates (other provider first, cheaper names first); only 429, 408, 5xx, timeouts, connection resets and overloaded / quota / rate
  limit text fall back, never 400, 401, 403 or content errors. A failed model cools down 60 s (doubling to 5 min) and each switch sends one
  `notice` ("Model X is rate limited, using Y"). See docs/protocol.md.
- Spoken progress (`backend/app/voice/progress.py`): while a long tool runs the Live model says a short line at the start and once more
  after 10 s (max 3 per call, 1 per 6 s, never over speech). Switch: `FRIDAY_SPOKEN_PROGRESS` (default on). See docs/protocol.md.
- Shared undo: `undo(steps?)` / `redo()` voice tools and `{t:'undo'|'redo'}` messages undo scene edits made by tools (add, move, delete with
  children, clear, links, deck placement), up to 30 steps; model3d and workshop changes are delegated to their own history. Approval-gated
  destructive actions are not undoable. See docs/protocol.md.
- Task-state line in the HUD: plain-word label (Hledam, Vzpominam, Stavim, ...) by tool category, minimum 600 ms, fades 1.5 s after the last tool.

## [20261121.4] - 2026-11-21

### New
- Workshop sources: deck items (images, files, models, pages) as reference tiles around the table; `workshop_sources` tool, `sources` in
  the `enter` message, at most 12 per workshop, forgotten items are dropped with a note. See docs/protocol.md.
- Web pages on the deck: `web_add` (browser message, model tool and the "Pridat odkaz" input of the Deck), `web_refresh`, `web_read`,
  `web_compare`. A guarded fetcher (public addresses only, pinned connection, checked redirects, size and type limits), readable text
  extraction, an offline snapshot per URL, deck type `web`, entity ref `web` and a card with [Otevrit original]. See docs/protocol.md.
- Workshop part tree engine (`backend/app/workshop`): a data-only spec (primitives, extrude, polyline, groups, `mirror`, `array`, parameters and
  safe `=expressions`) is validated and expanded into model3d parts with stable ids; `with_params` clamps; `SPEC_DOC` for the model. See docs/protocol.md.
- Scene kind `lathe` (surface of revolution from a `[r, y]` profile, `segments`, `cap`) and the workshop part kind `lathe` for vases, bottles, bowls and hubs. See docs/protocol.md.
- Workshop frontend (Dilna): camera glide into and out of the table, side panel with parameter sliders (12 msgs/s), sources, undo / redo and a question field,
  key W / Esc, `Nova dilna` and `Otevrit dilnu` in the Deck, drops onto the canvas go to the workshop, JPEG snapshots on request (`Stage.snapshot`).
  The entity shape and ref type `workshop` are accepted by the scene schema. See docs/desk.md.
- Workshop tool `workshop_look(question?)`: the browser renders the work table once (`workshop_snapshot_request` / `workshop_snapshot`, validated by `SnapshotBroker`) and
  the vision model critiques it with part ids; replies are hostile-input safe and waiting requests are cancelled on close. See docs/protocol.md.
- Entity desk UX: a dropped file or photo is selected on the desk with a toast (Otevrit / Zeptat se, 8 s) instead of opening its 2D card;
  a floating action bar next to the selected entity (Zavrit x, Otevrit, Spojit, Zeptat se; Delete, Esc, Enter keys); a Deck window
  (dock button, key D) with filter chips, search, sort, paging, pin, tags, two-step Forget, and drag-from-tile onto the desk or the chat.
  See docs/desk.md.
- Hand gestures (client only, MediaPipe in the browser): dock button + draggable preview; two hands scale/dolly, pinch grabs and moves,
  crossed arms close the topmost panel or cancel a drag, fist releases, flat spread hands explode the scene, optional open-palm Stop
  (off by default). `scripts/fetch-gesture-model.sh` downloads the model; `?gesturedemo` drives it from the mouse. See docs/ui-gestures.md.
- Files and images are entities in the 3D scene: scene kinds `entity` (holographic tile with thumbnail or glyph, title, link port) and `link`
  (glowing curve with flowing particles), common prop `ref`, auto-layout, double-click opens the card, context menu (open, link, remove from the deck).
- Tools `entity_link`, `entity_unlink`, `entity_list`, `entity_open`, `entity_arrange`, `entity_run`; `read_file`, `summarize_file`, `analyze_image` accept `ref`.
- Messages `entity_open`, `entity_link`, `entity_remove`. Shared glyph drawing moved to `frontend/src/core/glyphs.ts` (new audio, archive, tool, model, note glyphs).
- Photo editing: `image_edit` (merge people from several photos, enhance, remove background, outpaint, custom) with Gemini image models, stored as a new derived image with provenance, plus `image_compare`.
- `house_from_sources` builds a 3D `building` model from PDF plans and photos in one analysis (conflicts and open questions reported); `house_refine` proposes updates from a later inside photo. The building pack accepts `wall_color`.
- Thinking setting "Premysleni" has a fifth level `max` ("Maximalni"): the strongest reasoning each agent model supports
  (LiteLLM models: the highest effort the catalog advertises or the proxy lists in a 400; Gemini agent models: high); the
  voice model stays at high.
- LiteLLM reasoning models that support max effort are labelled "(max thinking)".
- Memory graph: server-side search from the toolbar (Enter or magnifier sends `memory_search`), highlighted result orbs with the rest dimmed, camera fly-to and fit, a collapsible hits panel (kind glyph, score bar, relative time, project, snippet, summary, keyboard and touch friendly), and "Zrusit hledani" restoring the generic graph without a server rebuild. Query graphs opened by the model via `show_memory_graph(query)` show the same state.
- Views: a second view of the same kind updates the open panel in place when its renderer supports it.
- Tests: `frontend/tests/memhits.mjs` (pure logic, `node --experimental-strip-types`) and `memhits_dom.mjs` (hits panel DOM, no WebGL).

### Changed
- `file_to_scene` and `show_in_scene` place an entity tile instead of a floating card or `image` plane; the file card opens on double-click. Wheel over a card scrolls it and no longer zooms the scene.
- The agent model list offers only Gemini 3.x and newer (no 2.x, 1.5 or `*-latest` aliases); the default agent model is
  the newest `gemini-3*-flash` in the live catalog, and a pin that vanished falls back to it with a notice.

## [20261121.3] - 2026-11-21

### New
- Any file can be dropped or attached (pdf, docx, xlsx, csv, epub, zip, text, code, html, json, audio/video as stored files): content-based type detection, bounded extraction, a `file_card` tile on the desktop, `file_upload`/`file_ready` messages, `GET /api/files/<id>` downloads and the `read_file`, `list_files`, `file_to_scene` and `summarize_file` model tools.
- "Nova konverzace" button (and Ctrl+Shift+N) in the chat header: stops everything, forgets the chat and voice context and starts fresh while memory, MCP, settings and the scene stay (`new_conversation`, optional `clear_scene`).
- Echo protection for phones: playback through a media element (browser echo cancellation reference), richer mic constraints, a half-duplex echo gate with a "Zvuk" settings section (headphones / speaker / automatic), `audio_profile` turn-detection tuning and a self-echo turn filter; see `docs/audio-echo.md` (needs a test on a real phone).
- Conversation language (default Czech) and per-model Live voice selection, with `set_language` / `set_voice` and a "Hlas a jazyk" settings section.
- One "Premysleni" (thinking level) setting, default high, for the Live voice model and the agent models (`set_thinking`, `FRIDAY_THINKING`).
- A Live connection that the model rejects now ends with a readable `error` instead of a stuck thinking state.
- Czech-tuned turn detection (`FRIDAY_VAD_*`) and an input transcription language hint.

### Changed
- Mic downsampling uses a windowed-sinc low-pass instead of box averaging (no aliasing).
- Persona: Friday is a woman and addresses the user as "Šéfe" sparingly, only in Czech.
- Default language is `cs-CZ` everywhere (`.env.example` said `en-US`); default voice is Kore.

## [20261121.1] - 2026-11-21 - first public release

### New
- Voice assistant on Gemini Live with non-blocking tools and session resumption.
- 3D scene DSL, parametric models with undo/redo and the `pcb`, `enclosure` and `building` packs.
- Rich view panels, image awareness, memory orbs, MCP client, web search, approval flow.
- Touch/tablet gestures and zoom by drawing.
- STOP button (and Esc): cancels playback, mic, capture, running tools, agent turns and approvals.
- Release tooling: `scripts/release.py`, privacy pre-commit hook, CI tests and a multi-arch Docker release.

### Changed
- Optional integrations (memory, MCP hub, LiteLLM, Hermes) are configured only through environment variables;
  the hub variables are `MCP_HUB_URL` / `MCP_HUB_TOKEN`, the Home Assistant token is `HA_TOKEN`.

### Fixed
- Nothing yet.

### Security
- No authentication is built in; run it behind an authenticating reverse proxy.
