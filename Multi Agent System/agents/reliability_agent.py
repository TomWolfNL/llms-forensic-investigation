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
        result, telemetry = await self.agent.invoke(payload, "ReliabilityOfSourceAgent")
        return result, telemetry