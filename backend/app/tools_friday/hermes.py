# backend/app/tools_friday/hermes.py
"""`ask_hermes`: hand a task to the Hermes agent (memory, Notion, messages, files, shell).

Gemini Live stays the voice; Hermes is the hands. The key lives only in this server's environment.
The tool is long (NON_BLOCKING) and risky: the user approves every request before it leaves.
Registered only when HERMES_URL and HERMES_KEY are set; HERMES_MODEL defaults to `hermes-agent`.
"""

import logging
import os
from typing import Any

import httpx

from app.voice.tools import Tool, ToolRegistry

log = logging.getLogger("friday.hermes")

HERMES_SESSION = "friday"  # one stable session so Hermes remembers the whole conversation
TIMEOUT_S = float(os.getenv("HERMES_TIMEOUT", "120"))
SUMMARY_CHARS = 160

# Prepended to every request: the text comes from speech recognition at a desk.
PREFIX = (
    "[Hlasovy vstup z tabletu u stolu, muze obsahovat chyby rozpoznani. Odpovez cesky, "
    "maximalne dvema kratkymi vetami, bez markdownu, odrazek a URL - bude se cist nahlas. "
    "Pri nevratne nebo nejednoznacne akci se nejdriv zeptej.]\n"
)

PARAMETERS = {
    "type": "object",
    "properties": {"request": {"type": "string", "description": "The whole task in one or two sentences, in Czech"}},
    "required": ["request"],
}

DESCRIPTION = (
    "Hand a task to the Hermes agent, which has memory, Notion, messages, files and a terminal and can act: "
    "send a message, write a note or task, search memory, check a project, do something on the computer. "
    "Use it for anything you cannot do yourself. The user is asked to approve each request. "
    "Hermes returns a short answer to read aloud."
)


def enabled() -> bool:
    return bool(os.getenv("HERMES_URL") and os.getenv("HERMES_KEY"))


def confirm_summary(args: dict[str, Any]) -> str:
    request = str(args.get("request", "")).strip()
    return "Ask Hermes: " + (request if len(request) <= SUMMARY_CHARS else request[:SUMMARY_CHARS] + "...")


async def ask_hermes(args: dict[str, Any]) -> dict[str, Any]:
    """Run one Hermes turn; failures become payloads the model can read out."""
    request = str(args.get("request", "")).strip()
    if not request:
        return {"error": "empty request"}
    url = os.getenv("HERMES_URL", "").rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {os.getenv('HERMES_KEY', '')}",
                    "X-Hermes-Session-Id": HERMES_SESSION,
                },
                json={
                    "model": os.getenv("HERMES_MODEL") or "hermes-agent",
                    "messages": [{"role": "user", "content": PREFIX + request}],
                },
            )
        r.raise_for_status()
        return {"result": r.json()["choices"][0]["message"]["content"]}
    except httpx.TimeoutException:
        return {"error": f"Hermes did not answer within {TIMEOUT_S:.0f} seconds"}
    except Exception as e:
        log.warning("ask_hermes failed: %s", type(e).__name__)
        return {"error": f"Hermes is unavailable ({type(e).__name__})"}


def register_hermes_tool(registry: ToolRegistry) -> None:
    if enabled():
        registry.register(
            Tool(
                name="ask_hermes",
                description=DESCRIPTION,
                parameters=PARAMETERS,
                handler=ask_hermes,
                long=True,
                risky=True,
                confirm_summary=confirm_summary,
            )
        )
