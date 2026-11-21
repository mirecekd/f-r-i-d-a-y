<div align="center">

# F.R.I.D.A.Y.

**A voice-first assistant with a 3D holographic workspace.**

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/mirecekd) [![PayPal.me](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?business=LJ5ZF7Q9KMTRW&no_recurring=0&currency_code=USD)

</div>

## What is it?

F.R.I.D.A.Y. is a self-hosted web app: you talk to it (Gemini Live), and it answers by voice while drawing on a 3D scene,
building parametric models, showing rich panels (charts, maps, diagrams, code, images) and, optionally, tapping into
your memory service, MCP tools and an agent backend. It runs in the browser, on a desktop or a tablet.

## Features

- **Voice** through Gemini Live: barge-in, long-running tools that do not block the conversation, session resumption.
- **3D scene DSL**: the model draws primitives, groups, CSG and glTF objects, and the scene is streamed to the browser.
- **Parametric models** with undo/redo, bounds and measurements, plus packs: `pcb`, `enclosure`, `building`.
- **Rich view panels**: markdown, code, JSON, charts, diagrams, maps, images with EXIF.
- **Image awareness**: drop or paste an image, the model can look at it and talk about it.
- **Memory orbs**: an optional memory service is shown as a graph of orbs you can filter and open.
- **MCP client**: connect streamable-HTTP/SSE MCP servers with an allow-list and per-tool policies.
- **Web search** through Gemini grounding.
- **Approval flow**: risky tools (writes, remote agents) wait for your confirmation.
- **Touch and tablet** friendly, with **zoom by drawing** a rectangle on the scene.

Only `GEMINI_API_KEY` is required. The memory service, LiteLLM, MCP servers and the Hermes agent are **optional**:
each is switched on by its environment variables and is simply absent when they are not set.

## Architecture

```mermaid
flowchart LR
  B[Browser<br/>Vite + TypeScript + three.js] <-- WebSocket /ws --> S[FastAPI backend]
  S <-- Live API --> G[Gemini Live]
  S -. optional .-> M[Memory service REST]
  S -. optional .-> H[MCP hub / servers]
  S -. optional .-> L[LiteLLM proxy]
  S -. optional .-> A[Hermes agent API]
  S --- D[(data dir: uploads, models, prefs)]
```

```
Browser  <--ws-->  backend (FastAPI)  <--->  Gemini Live
                        |-- tools: scene, models, views, search, vision
                        |-- optional: memory | MCP | LiteLLM | Hermes
```

The wire protocol is documented in [docs/protocol.md](docs/protocol.md), the gestures in
[docs/ui-gestures.md](docs/ui-gestures.md).

## Quickstart

```sh
cp .env.example .env        # set GEMINI_API_KEY
docker compose up -d --build
# open http://127.0.0.1:8670
```

More in [QUICKSTART.md](QUICKSTART.md). The prebuilt multi-arch image (amd64, arm64) is
`ghcr.io/mirecekd/f-r-i-d-a-y:latest`.

## Configuration

All settings are environment variables, see [.env.example](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | - | Required. Google AI Studio key |
| `GEMINI_LIVE_MODEL` | `gemini-3.8-live` | Live model for voice |
| `GEMINI_VOICE`, `GEMINI_LANGUAGE` | `Algieba`, `cs-CZ` | Voice and spoken language |
| `FRIDAY_SEARCH_MODEL` | `gemini-flash-latest` | Model for web search |
| `FRIDAY_AGENT_MODEL`, `FRIDAY_CHAT_MODEL` | `gemini-flash-latest` | Default models of the agent/chat roles |
| `LITELLM_BASE_URL`, `LITELLM_API_KEY` | unset | Optional extra model provider (OpenAI-compatible proxy) |
| `AGENTMEMORY_URL`, `AGENTMEMORY_SECRET` | unset | Optional memory service (orbs, recall, remember) |
| `MCP_HUB_URL`, `MCP_HUB_TOKEN` | unset | Optional MCP hub, see `backend/mcp_servers.json` |
| `HA_URL`, `HA_TOKEN` | unset | Optional Home Assistant MCP endpoint |
| `FRIDAY_MCP_CONFIG` | unset | Alternative MCP config file (empty = no MCP) |
| `HERMES_URL`, `HERMES_KEY`, `HERMES_MODEL`, `HERMES_TIMEOUT` | unset | Optional agent API for `ask_hermes` |
| `FRIDAY_DATA_DIR` | `/srv/data` | Uploads, models, preferences, optional `mcp_servers.json` |
| `STATIC_DIR` | `<backend>/static` | Built frontend |
| `FRIDAY_DEMO` | `0` | `1` enables demo scenes (development) |
| `FRIDAY_VERSION` | `__version__` | Version override, set by the Docker build |

## Security

- **There is no authentication built in.** Anyone who can reach the port can use your Gemini key and every enabled tool.
- Put it behind a reverse proxy with SSO or at least basic auth and TLS. The compose file binds to `127.0.0.1` only.
- Keep secrets in `.env` (git-ignored), never in `mcp_servers.json`: it references environment variable names only.
- Risky tools need an explicit approval click; MCP tools are allow-listed one by one.
- `scripts/pre-commit` refuses commits with private files or key-like strings (see Development).

## Versioning and releases

Versions look like `YYYYMMDD.X` (build day and the counter of that day). `backend/app/__init__.py` holds
`__version__`; `/health` and the WebSocket `hello` message report it (`FRIDAY_VERSION` overrides it in the container).

```sh
python scripts/release.py          # prints the next free version from the git tags
python scripts/release.py --write  # also writes it into backend/app/__init__.py
```

Every push to `main` runs the tests; when they pass, the `Release` workflow computes the next version, creates the tag
and a GitHub Release with generated notes, and pushes `ghcr.io/mirecekd/f-r-i-d-a-y:<version>` and `:latest`
(linux/amd64 and linux/arm64). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Development

```sh
sh scripts/install-hooks.sh                         # privacy pre-commit hook
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                       # tests
.venv/bin/ruff check app tests ../scripts           # lint (line length 120)
cd ../frontend && npm ci && npm run dev             # Vite dev server, proxies /ws to :8670
npm run build                                       # type check + production build
python scripts/privacy_scan.py --tree               # the CI privacy check
```

Run the backend alone with `uvicorn app.main:app --port 8670` from `backend/`.

## Support

<div align="center">

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/mirecekd) [![PayPal.me](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?business=LJ5ZF7Q9KMTRW&no_recurring=0&currency_code=USD)

</div>

## License

MIT, see [LICENSE](LICENSE). (c) 2026 Miroslav Dvorak.
