from agents.base import (
    StructuredAgent
)

from prompts.credibility_prompt import (
    CREDIBILITY_PROMPT
)

from models.credibility_models import (
    CredibilityResult
)


class CredibilityAgent:

    def __init__(self):

        self.agent = StructuredAgent(
            prompt=CREDIBILITY_PROMPT,
            output_schema=CredibilityResult
        )

    async def run(
        self,
        reliability
    ):

        return await self.agent.invoke(
            {
                "reliability": reliability
            }
        )

        return result