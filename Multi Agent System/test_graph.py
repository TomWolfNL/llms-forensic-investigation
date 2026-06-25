import asyncio

from graph.workflow import build_graph
from utils.loader import load_statements


async def main():

    statements = load_statements(
        "Multi Agent System/samples/witness_input.json"
    )

    graph = build_graph()

    result = await graph.ainvoke({
        "statements": statements
    })

    print("\nFINAL REPORT:\n")
    print(result["final_report"])


if __name__ == "__main__":
    asyncio.run(main())