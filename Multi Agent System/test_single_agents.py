import asyncio

from utils.loader import load_statements
from agents.timeline_agent import TimelineAgent
from agents.attribute_agent import AttributeAgent


async def main():

    # test_single_agents.py
    data = load_statements("Multi Agent System/samples/witness_input.json")

    timeline = await TimelineAgent().run(data)
    print("\nTIMELINE:\n", timeline)

    attrs = await AttributeAgent().run(data)
    print("\nATTRIBUTES:\n", attrs)


if __name__ == "__main__":
    asyncio.run(main())