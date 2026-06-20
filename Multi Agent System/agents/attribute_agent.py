from agents.base import StructuredAgent

from prompts.attribute_prompt import (
    ATTRIBUTE_PROMPT
)

from models.attribute_models import (
    AttributeResult
)


class AttributeAgent:

    def __init__(self):

        self.agent = StructuredAgent(
            prompt=ATTRIBUTE_PROMPT,
            output_schema=AttributeResult
        )

    async def run(
        self,
        statements: list
    ):

        result = await self.agent.invoke(
            statements
        )

        return result.people