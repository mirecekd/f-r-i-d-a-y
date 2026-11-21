# Changelog

Versions are `YYYYMMDD.X` (build day and the counter of that day).

## [20261121.1] - 2026-11-21 - first public release

### New
- Voice assistant on Gemini Live with non-blocking tools and session resumption.
- 3D scene DSL, parametric models with undo/redo and the `pcb`, `enclosure` and `building` packs.
- Rich view panels, image awareness, memory orbs, MCP client, web search, approval flow.
- Touch/tablet gestures and zoom by drawing.
- Release tooling: `scripts/release.py`, privacy pre-commit hook, CI tests and a multi-arch Docker release.

### Changed
- Optional integrations (memory, MCP hub, LiteLLM, Hermes) are configured only through environment variables;
  the hub variables are `MCP_HUB_URL` / `MCP_HUB_TOKEN`, the Home Assistant token is `HA_TOKEN`.

### Fixed
- Nothing yet.

### Security
- No authentication is built in; run it behind an authenticating reverse proxy.
