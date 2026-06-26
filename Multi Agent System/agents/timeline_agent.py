from agents.base import StructuredAgent
from prompts.timeline_prompt import TIMELINE_PROMPT
from models.timeline_models import TimelineResult

class TimelineAgent:
    def __init__(self):
        self.agent = StructuredAgent(
            prompt=TIMELINE_PROMPT,
            output_schema=TimelineResult
        )

    async def run(
        self,
        statements: list
    ):
        result, telemetry = await self.agent.invoke(
            statements, "TimelineAgent"
        )

        return result.events, telemetry