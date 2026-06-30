import asyncio
import logging
import json
from pathlib import Path

# Agents & Utils
from agents.baseline_agent import BaselineAgent
from utils.json_utils import load_json, dump_json
from graph.workflow import build_graph

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S"
)

BASE_DIR = Path(__file__).parent

DATASETS = [
    "The Leavenworth Case",
    "The Murder of Roger Ackroyd",
    "The Mystery of the Blue Train",
    "The Mystery of the Yellow Room",
    "Whose Body"
]

async def run_story(dataset_name: str):
    safe_name = dataset_name.replace(" ", "_")
    input_file = BASE_DIR.parent / "Datasets" / dataset_name / "anonymized_story.json"
    
    # Save with dataset-specific names so they don't overwrite
    mas_output = BASE_DIR / "results" / f"{safe_name}_final_report.json"
    baseline_output = BASE_DIR / "results" / f"{safe_name}_baseline_results.json"

    if not input_file.exists():
        logging.warning(f"Skipping {dataset_name}: {input_file} not found.")
        return

    logging.info(f"========== PROCESSING: {dataset_name} ==========")
    raw_story = load_json(input_file)
    witnesses = raw_story.get("witnesses", [])
    logging.info(f"Story loaded — {len(witnesses)} witnesses found")

    # 1. RUN MAS PIPELINE
    logging.info("Starting Multi-Agent System (MAS) Pipeline...")
    graph = build_graph()
    mas_result = await graph.ainvoke({"raw_story": raw_story})
    
    dump_json(mas_result["final_report"], mas_output)
    logging.info(f"MAS Report saved to: {mas_output.name}")

    # 2. RUN BASELINE AGENT
    logging.info("Starting Holistic Baseline Agent...")
    baseline_agent = BaselineAgent()
    baseline_result = await baseline_agent.run(raw_story)
    
    with open(baseline_output, "w", encoding="utf-8") as f:
        json.dump(baseline_result.model_dump() if hasattr(baseline_result, "model_dump") else baseline_result, f, indent=2)
    
    logging.info(f"Baseline Report saved to: {baseline_output.name}")
    logging.info(f"========== FINISHED: {dataset_name} ==========\n")


async def main():
    # Ensure results directory exists
    (BASE_DIR / "results").mkdir(exist_ok=True)
    
    for dataset in DATASETS:
        await run_story(dataset)
        
    logging.info("ALL DATASETS PROCESSED SUCCESSFULLY.")

if __name__ == "__main__":
    asyncio.run(main())