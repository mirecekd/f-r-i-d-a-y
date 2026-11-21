# Changelog

Versions are `YYYYMMDD.X` (build day and the counter of that day).

## Unreleased

### New
- Conversation language (default Czech) and per-model Live voice selection, with `set_language` / `set_voice` and a "Hlas a jazyk" settings section.
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
