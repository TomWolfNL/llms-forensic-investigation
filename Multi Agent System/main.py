import asyncio
import logging
import argparse
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

async def run(dataset_name: str):
    # Dynamic paths based on the dataset argument
    input_file = BASE_DIR.parent / "Datasets" / dataset_name / "anonymized_story.json"
    mas_output = BASE_DIR / "results" / "final_report.json"
    baseline_output = BASE_DIR / "results" / "baseline_results.json"

    # Ensure results directory exists
    (BASE_DIR / "results").mkdir(exist_ok=True)

    logging.info(f"Loading story from: {input_file}")
    raw_story = load_json(input_file)
    
    witnesses = raw_story.get("witnesses", [])
    logging.info(f"Story loaded — {len(witnesses)} witnesses found")

    # 1. RUN MAS PIPELINE
    logging.info("Starting Multi-Agent System (MAS) Pipeline...")
    graph = build_graph()
    mas_result = await graph.ainvoke({"raw_story": raw_story})
    
    # Save MAS output
    dump_json(mas_result["final_report"], mas_output)
    logging.info(f"MAS Report saved to: {mas_output}")

    # 2. RUN BASELINE AGENT
    logging.info("Starting Holistic Baseline Agent...")
    baseline_agent = BaselineAgent()
    
    # We await the baseline agent here
    baseline_result = await baseline_agent.run(raw_story)
    
    # Save Baseline output
    # Note: Ensure baseline_result is dictionary-serializable
    with open(baseline_output, "w", encoding="utf-8") as f:
        json.dump(baseline_result.model_dump() if hasattr(baseline_result, "model_dump") else baseline_result, f, indent=2)
    
    logging.info(f"Baseline Report saved to: {baseline_output}")
    logging.info("Pipeline complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Forensic MAS and Baseline comparison.")
    parser.add_argument(
        "--dataset", 
        default="The Leavenworth Case", 
        help="The folder name in Datasets/ containing the story"
    )
    
    args = parser.parse_args()
    
    asyncio.run(run(args.dataset))