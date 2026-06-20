from agents.base import StructuredAgent
from prompts.contradiction_prompt import CONTRADICTION_PROMPT
from models.contradiction_models import ContradictionResult

from typing import Any


class TimelineContradictionAgent:

    def __init__(self):
        self.agent = StructuredAgent(
            prompt=CONTRADICTION_PROMPT,
            output_schema=ContradictionResult
        )

    # -------------------------------------------------
    # FIX 2 — CLEAN SERIALIZATION LAYER
    # -------------------------------------------------
    def _normalize(self, obj: Any):

        # Pydantic v2
        if hasattr(obj, "model_dump"):
            return obj.model_dump()

        # dict safe
        if isinstance(obj, dict):
            return obj

        # list/tuple recursive safety
        if isinstance(obj, (list, tuple)):
            return [self._normalize(x) for x in obj]

        # fallback
        return dict(obj)

    async def run(self, timeline):

        # -------------------------------------------------
        # FORCE CLEAN INPUT CONTRACT
        # -------------------------------------------------
        clean_timeline = self._normalize(timeline)

        payload = {
            "timeline": clean_timeline
        }

        result = await self.agent.invoke(payload)

        return result.contradictions