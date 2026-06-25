from agents.base import StructuredAgent
from prompts.reliability_prompt import RELIABILITY_OF_SOURCE_PROMPT
from models.credibility_models import ReliabilityResult


class ReliabilityOfSourceAgent:

    def __init__(self):
        self.agent = StructuredAgent(
            prompt=RELIABILITY_OF_SOURCE_PROMPT,
            output_schema=ReliabilityResult
        )

    async def run(self, payload: dict):
        """
        payload must contain:
          {
            "witness": str,
            "statements": list,
            "contradictions": list,
            "behavior": list
          }
        """
        return await self.agent.invoke(payload)
