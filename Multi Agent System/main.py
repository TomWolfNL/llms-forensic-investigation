import asyncio

from utils.loader import (
    load_statements
)

from utils.json_utils import (
    dump_json
)

from graph.workflow import (
    build_graph
)

from pathlib import Path

BASE_DIR = Path(__file__).parent

INPUT_FILE = (
    BASE_DIR
    / "samples"
    / "witness_input.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "final_report.json"
)

async def run():

    statements = (
        load_statements(
            INPUT_FILE
        )
    )

    graph = (
        build_graph()
    )

    result = (
        await graph.ainvoke(
            {
                "statements":
                    statements
            }
        )
    )

    dump_json(
        result[
            "final_report"
        ],
        OUTPUT_FILE
    )

    print()

    print(
        "Report saved:"
    )

    print(
        OUTPUT_FILE
    )

    print()


if __name__ == "__main__":

    asyncio.run(
        run()
    )