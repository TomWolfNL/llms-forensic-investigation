import asyncio
import logging

from utils.json_utils import (
    load_json,
    dump_json
)

from graph.workflow import (
    build_graph
)

from pathlib import Path

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S"
)

BASE_DIR = Path(__file__).parent

# Set this to any anonymized_story.json from the Datasets folder
INPUT_FILE = (
    BASE_DIR.parent
    / "Datasets"
    / "The Murder of Roger Ackroyd"
    / "anonymized_story.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "results"
    / "final_report.json"
)

async def run():

    logging.info(f"Loading story: {INPUT_FILE.name}")

    raw_story = (
        load_json(
            INPUT_FILE
        )
    )

    witnesses = raw_story.get("witnesses", [])
    logging.info(f"Story loaded — {len(witnesses)} witnesses found")

    graph = (
        build_graph()
    )

    logging.info("Pipeline starting...")

    result = (
        await graph.ainvoke(
            {
                "raw_story":
                    raw_story
            }
        )
    )

    dump_json(
        result[
            "final_report"
        ],
        OUTPUT_FILE
    )

    logging.info(f"Report saved: {OUTPUT_FILE}")


if __name__ == "__main__":

    asyncio.run(
        run()
    )
