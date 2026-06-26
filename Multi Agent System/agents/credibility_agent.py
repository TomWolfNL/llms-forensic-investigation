from agents.base import StructuredAgent
from prompts.credibility_prompt import CREDIBILITY_OF_INFORMATION_PROMPT
from models.reliability_models import CredibilityResult 

from typing import Any

class CredibilityOfInformationAgent:
    def __init__(self):
        self.agent = StructuredAgent(
            prompt=CREDIBILITY_OF_INFORMATION_PROMPT,
            output_schema=CredibilityResult
        )

    async def run(self, payload: dict):
        payload = self._normalize(payload)

        result, telemetry = await self.agent.invoke(payload, "CredibilityOfInformationAgent")

        self._validate_output(result)

        return result, telemetry

    def _normalize(self, obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        return dict(obj)

    def _validate_output(self, result):
        if result.metrics is None:
            return 

        metrics = result.metrics
        values = [
            metrics.internal_consistency,
            metrics.physical_impossibility,
            metrics.orchestration_marker,
            metrics.detail_quality,
        ]

        for v in values:
            if v < 0.0 or v > 1.0:
                raise ValueError(f"Invalid metric out of range: {v}")