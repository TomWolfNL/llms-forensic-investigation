from agents.base import (
    StructuredAgent
)

from prompts.behavioral_prompt import (
    BEHAVIORAL_PROMPT
)

from models.behavior_models import (
    BehaviorResult
)


class BehavioralConsistencyAgent:

    def __init__(self):

        self.agent = StructuredAgent(
            prompt=BEHAVIORAL_PROMPT,
            output_schema=BehaviorResult
        )

    async def run(
        self,
        timeline,
        attributes
    ):

        result = (
            await self.agent.invoke(
                {
                    "timeline": timeline,
                    "attributes": attributes
                }
            )
        )

        return result.issues