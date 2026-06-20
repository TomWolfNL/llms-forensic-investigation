import asyncio

from utils.loader import (
    load_statements
)

from agents.timeline_agent import (
    TimelineAgent
)

from agents.attribute_agent import (
    AttributeAgent
)


async def main():

    data = load_statements(
        "samples/witness_input.json"
    )

    timeline = await TimelineAgent().run(
        data
    )

    attrs = await AttributeAgent().run(
        data
    )

    print()

    print("TIMELINE")
    print(timeline)

    print()

    print("ATTRIBUTES")
    print(attrs)


if __name__ == "__main__":

    asyncio.run(main())