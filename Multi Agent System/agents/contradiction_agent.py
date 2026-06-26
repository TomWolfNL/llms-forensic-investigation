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

    def _normalize(self, obj: Any):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._normalize(x) for x in obj]
        return dict(obj)

    async def run(self, timeline):
        clean_timeline = self._normalize(timeline)

        payload = {
            "timeline": clean_timeline
        }

        result, telemetry = await self.agent.invoke(payload, "TimelineContradictionAgent")

        return result.contradictions, telemetry