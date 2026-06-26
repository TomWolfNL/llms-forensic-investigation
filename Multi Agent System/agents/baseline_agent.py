from agents.base import StructuredAgent
from models.baseline_models import BaselineResult
from prompts.baseline_prompt import BASELINE_PROMPT

class BaselineAgent:
    
    def __init__(self):
        self._agent = StructuredAgent(
            prompt=BASELINE_PROMPT, 
            output_schema=BaselineResult
        )

    async def run(self, full_story_json: dict) -> dict:
        # 1. Unpack the tuple from the base agent execution
        result, telemetry = await self._agent.invoke(full_story_json, "BaselineAgent")
        
        # 2. Convert the Pydantic result to a dictionary
        result_dict = result.model_dump()
        
        # 3. Append the telemetry log so it saves properly into baseline_results.json
        result_dict["telemetry_log"] = [telemetry]
        
        return result_dict