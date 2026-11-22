# backend/app/agent/fallback.py
"""Per-role model fallback: a pinned model that is rate limited or down is replaced by a same-role alternate.

`ladder(role, pinned)` = pinned model, then up to 3 catalog models that have the role (another provider first, then
another group, then cheaper-looking names, then id). `call_with_fallback` walks it, retrying only on retryable errors; a model that failed
that way sits out a cooldown (60 s, doubling per repeat up to 5 min), and every switch is announced once as a notice.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.agent.catalog import catalog

log = logging.getLogger("friday.agent.fallback")

MAX_ALTERNATES = 3
COOLDOWN_BASE_S = 60.0
COOLDOWN_MAX_S = 300.0
RETRYABLE_STATUS = {408, 429}
RETRYABLE_TEXT = ("overloaded", "quota", "rate limit", "rate_limit", "resource exhausted", "resource_exhausted", "too many requests", "timed out", "timeout", "connection reset")
CHEAP_NAME_PARTS = ("flash", "mini", "haiku", "lite", "small", "nano")
Notice = Callable[[str], Awaitable[None]]


def status_of(error: BaseException) -> int | None:
    """HTTP status carried by an SDK error (`code` / `status_code`) or written as `litellm 429: ...`."""
    for attr in ("status_code", "code"):
        value = getattr(error, attr, None)
        if isinstance(value, int):
            return value
    parts = str(error).split()
    if len(parts) > 1 and parts[0] == "litellm" and parts[1].rstrip(":").isdigit():
        return int(parts[1].rstrip(":"))
    return None


def is_retryable(error: BaseException) -> bool:
    """429, 408, 5xx, timeouts, connection resets and 'overloaded'/'quota'/'rate limit' text; never 400/401/403."""
    status = status_of(error)
    if status is not None:
        return status in RETRYABLE_STATUS or status >= 500
    if isinstance(error, (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.TransportError)):
        return True
    text = str(error).lower()
    return any(part in text for part in RETRYABLE_TEXT)


def is_rate_limit(error: BaseException) -> bool:
    text = str(error).lower()
    return status_of(error) == 429 or any(p in text for p in ("quota", "rate limit", "rate_limit", "too many requests", "resource exhausted", "resource_exhausted"))


def candidates(role: str) -> list[dict[str, Any]]:
    entries = catalog.entries_for("gemini") + catalog.entries_for("litellm")
    return [e for e in entries if role in e["roles"] and e.get("caps", {}).get("tools", True)]


def ladder(role: str, pinned: str) -> list[str]:
    """`pinned` first, then up to 3 alternates that have `role`: other provider first, then other group, then cheaper names, then id."""
    entries = candidates(role)
    home = next((e for e in entries if e["id"] == pinned), None)

    def rank(e: dict[str, Any]) -> tuple[bool, bool, bool, str]:
        cheap = any(part in e["id"].lower() for part in CHEAP_NAME_PARTS)
        same_provider = home is not None and e["provider"] == home["provider"]
        same_group = home is not None and e["group"] == home["group"]
        return (same_provider, same_group, not cheap, e["id"])

    others = sorted((e for e in entries if e["id"] != pinned), key=rank)
    return [pinned] + [e["id"] for e in others[:MAX_ALTERNATES]]


class Cooldowns:
    """In-memory cooldown per model; the clock is injectable."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._until: dict[str, float] = {}
        self._strikes: dict[str, int] = {}

    def active(self, model: str) -> bool:
        return self._until.get(model, 0.0) > self.clock()

    def fail(self, model: str) -> None:
        strikes = self._strikes.get(model, 0)
        self._strikes[model] = strikes + 1
        self._until[model] = self.clock() + min(COOLDOWN_BASE_S * 2**strikes, COOLDOWN_MAX_S)

    def succeed(self, model: str) -> None:
        self._strikes.pop(model, None)


class Fallback:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.cooldowns = Cooldowns(clock)
        self._announced: dict[str, tuple[str, str]] = {}  # role -> (pinned, used) last announced

    async def call(
        self,
        role: str,
        pinned: str,
        do: Callable[[str], Awaitable[Any]],
        on_notice: Notice | None = None,
        can_retry: Callable[[], bool] = lambda: True,
    ) -> Any:
        """Run `do(model)` on the ladder; `can_retry()` False (e.g. text already streamed) stops falling back."""
        models = ladder(role, pinned)
        ready = [m for m in models if not self.cooldowns.active(m)] or models[:1]
        last: Exception | None = None
        why = "unavailable"
        for model in ready:
            try:
                result = await do(model)
            except Exception as e:
                if not is_retryable(e) or not can_retry():
                    raise
                log.warning("model %s failed (%s: %s), trying the next", model, type(e).__name__, str(e)[:200])
                self.cooldowns.fail(model)
                last, why = e, "rate limited" if is_rate_limit(e) else "unavailable"
                continue
            self.cooldowns.succeed(model)
            await self._announce(role, pinned, model, why if last else "rate limited", on_notice)
            return result
        if last is None:
            raise RuntimeError(f"no model available for role {role}")
        raise last

    async def _announce(self, role: str, pinned: str, used: str, why: str, on_notice: Notice | None) -> None:
        if used == pinned:
            self._announced.pop(role, None)
            return
        if self._announced.get(role) == (pinned, used):
            return
        self._announced[role] = (pinned, used)
        if on_notice:
            await on_notice(f"Model {pinned} is {why}, using {used}")


fallback = Fallback()


async def call_with_fallback(
    role: str,
    pinned: str,
    do: Callable[[str], Awaitable[Any]],
    on_notice: Notice | None = None,
    can_retry: Callable[[], bool] = lambda: True,
) -> Any:
    return await fallback.call(role, pinned, do, on_notice, can_retry)
