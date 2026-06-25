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

        result = await self.agent.invoke(payload)

        self._validate_output(result)

        return result

    def _normalize(self, obj: Any) -> Any:

        if hasattr(obj, "model_dump"):
            return obj.model_dump()

        if isinstance(obj, dict):
            return obj

        return dict(obj)

    def _validate_output(self, result):

        metrics = result.metrics

        values = [
            metrics.internal_consistency,
            metrics.cross_confirmation,
            metrics.detail_quality,
            metrics.observation_quality,
            metrics.contextual_alignment
        ]

        if all(v == 0.0 for v in values):
            raise ValueError(
                "CredibilityOfInformationAgent produced ALL ZERO METRICS — likely parsing or prompt failure"
            )

        if len(set(values)) == 1 and values[0] in (0.0, 1.0):
            raise ValueError(
                "Suspicious uniform metric distribution detected"
            )

        for v in values:
            if v < 0.0 or v > 1.0:
                raise ValueError(f"Invalid metric out of range: {v}")

        if result.credibility_grade not in (1, 2, 3, 4, 5, 6):
            raise ValueError(
                f"Invalid credibility_grade: {result.credibility_grade}. Must be integer 1–6."
            )
