# backend/app/agent_settings.py
"""Settings messages of one browser connection (models, language, voice, thinking), mixed into AgentSession."""

from typing import Any

from app.agent import prefs
from app.agent.agent_model import resolve
from app.agent.catalog import catalog
from app.agent.loop import Emit
from app.agent.prompt import chat_prompt
from app.agent.voice_settings import NEXT_SESSION_NOTICE, apply_language, apply_thinking, apply_voice, models_fields
from app.voice.language import current_language
from app.voice.session import live_model


def pinned_model(role: str) -> str:
    """The model the given role (`chat` = Live voice/text, `agent` = executing agent) currently uses."""
    if role == "chat":
        return live_model()
    return resolve()[0]


class SettingsMixin:
    """Needs `self.emit` (async JSON sender) and `self.history` (chat messages) from AgentSession."""

    emit: Emit
    history: list[dict[str, Any]]

    async def send_models(self) -> None:
        catalog_entries = await catalog.get()
        stale = resolve()[1]
        if stale:
            await self.emit({"t": "notice", "text": f"Pinned agent model {stale} is gone, using {pinned_model('agent')}"})
        await self.emit(
            {
                "t": "models",
                "catalog": catalog_entries,
                "pinned": {"agent_model": pinned_model("agent"), "chat_model": pinned_model("chat")},
                **models_fields(pinned_model("chat")),
            }
        )

    async def set_language(self, msg: dict, voice_active: bool = False) -> None:
        error = apply_language(msg)
        if error:
            return await self.emit({"t": "error", "message": error})
        self.history[0] = {"role": "system", "content": chat_prompt(current_language())}
        await self._changed(voice_active)

    async def set_voice(self, msg: dict, voice_active: bool = False) -> None:
        error = apply_voice(pinned_model("chat"), msg)
        if error:
            return await self.emit({"t": "error", "message": error})
        await self._changed(voice_active)

    async def set_thinking(self, msg: dict, voice_active: bool = False) -> None:
        error = apply_thinking(msg)
        if error:
            return await self.emit({"t": "error", "message": error})
        await self._changed(voice_active)

    async def _changed(self, voice_active: bool) -> None:
        await self.send_models()
        if voice_active:
            await self.emit({"t": "notice", "text": NEXT_SESSION_NOTICE})

    async def set_model(self, msg: dict, voice_active: bool = False) -> None:
        role, model = msg.get("role"), str(msg.get("model", ""))
        await catalog.get()
        if role not in prefs.ROLES:
            await self.emit({"t": "error", "message": f"set_model: unknown role {role}"})
        elif catalog.provider_of(model) is None:
            await self.emit({"t": "error", "message": f"set_model: unknown model {model}"})
        elif not catalog.has_role(model, role):
            await self.emit({"t": "error", "message": f"set_model: model {model} is not available for role {role}"})
        else:
            prefs.save_model(role, model)
            await self._changed(voice_active and role == "chat")
