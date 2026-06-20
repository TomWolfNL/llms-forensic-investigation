from agents.base import StructuredAgent
from prompts.reliability_prompt import RELIABILITY_PROMPT
from models.reliability_models import ReliabilityResult

from typing import Any


class ReliabilityEvidenceAgent:

    def __init__(self):
        self.agent = StructuredAgent(
            prompt=RELIABILITY_PROMPT,
            output_schema=ReliabilityResult
        )

    async def run(self, payload: dict):

        # -------------------------------------------------
        # INPUT NORMALIZATION LAYER (SAFE)
        # -------------------------------------------------
        payload = self._normalize(payload)

        # -------------------------------------------------
        # DEBUG HOOK (OPTIONAL)
        # -------------------------------------------------
        # import json
        # print("RELIABILITY PAYLOAD:", json.dumps(payload, indent=2))

        result = await self.agent.invoke(payload)

        # -------------------------------------------------
        # OUTPUT VALIDATION
        # -------------------------------------------------
        self._validate_output(result)

        return result

    # -------------------------------------------------
    # NORMALIZATION
    # -------------------------------------------------
    def _normalize(self, obj: Any) -> Any:

        if hasattr(obj, "model_dump"):
            return obj.model_dump()

        if isinstance(obj, dict):
            return obj

        return dict(obj)

    # -------------------------------------------------
    # OUTPUT VALIDATION
    # -------------------------------------------------
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
                "ReliabilityAgent produced ALL ZERO METRICS — likely parsing or prompt failure"
            )

        if len(set(values)) == 1 and values[0] in (0.0, 1.0):
            raise ValueError(
                "Suspicious uniform metric distribution detected"
            )

        for v in values:
            if v < 0.0 or v > 1.0:
                raise ValueError(f"Invalid metric out of range: {v}")