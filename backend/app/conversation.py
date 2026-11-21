# backend/app/conversation.py
"""NEW CONVERSATION: stop everything, then forget the chat context but keep scene, settings, memory and tools."""

from app.agent.loop import Emit
from app.agent_wiring import AgentSession
from app.scene import SceneStore
from app.stop import StopController
from app.voice import VoiceBridge

NOTICE = "Nova konverzace"


async def new_conversation(
    msg: dict, emit: Emit, scene: SceneStore, agent: AgentSession, voice: VoiceBridge, stopper: StopController
) -> None:
    """Handle `{t:'new_conversation', clear_scene?}`; safe when idle, while voice is active and when repeated."""
    clear_scene = msg.get("clear_scene") is True
    await stopper.stop()  # cancels long tools, agent turns, approvals and the voice session
    del agent.history[1:]  # keep the system prompt only
    agent.approvals.reset_grants()
    await voice.reset_context()  # the next voice_start opens a fresh Live session and fetches the briefing again
    await agent.models.reset_transient()
    if clear_scene:
        ops = [{"op": "clear"}]
        scene.apply(ops)
        await emit({"t": "scene", "ops": ops})
    await emit({"t": "conversation_reset", "clear_scene": clear_scene})
    await emit({"t": "notice", "text": NOTICE})
