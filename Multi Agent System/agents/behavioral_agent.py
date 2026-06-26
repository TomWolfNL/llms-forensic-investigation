from agents.base import StructuredAgent
from prompts.behavioral_prompt import BEHAVIORAL_PROMPT
from models.behavior_models import BehaviorResult

class BehavioralConsistencyAgent:
    def __init__(self):
        self.agent = StructuredAgent(
            prompt=BEHAVIORAL_PROMPT,
            output_schema=BehaviorResult
        )

    async def run(
        self,
        statements,
        attributes
    ):
        result, telemetry = await self.agent.invoke(
            {
                "statements": statements,
                "attributes": attributes
            },
            "BehavioralConsistencyAgent"
        )

        return result.issues, telemetry