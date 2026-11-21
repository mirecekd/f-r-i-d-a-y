# Changelog

Versions are `YYYYMMDD.X` (build day and the counter of that day).

## Unreleased

### New
- Nothing yet.

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
