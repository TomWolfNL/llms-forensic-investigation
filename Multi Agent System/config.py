from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):

    vllm_url: str
    vllm_api_key: str
    model_name: str

    temperature: float = 0.0


settings = Settings(
    vllm_url=os.getenv(
        "VLLM_URL",
        "http://grading-llm.eemcs.utwente.nl:4000/v1/"
    ),

    vllm_api_key=os.getenv(
        "VLLM_API_KEY",
        "sk-126ecbcfb8e54eef8a708eded7d7f5bf"
    ),

    model_name=os.getenv(
        "VLLM_MODEL_NAME",
        "UTM"
    ),

    temperature=float(
        os.getenv(
            "TEMPERATURE",
            "0.0"
        )
    )
)