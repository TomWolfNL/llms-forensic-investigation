from langchain_openai import ChatOpenAI

from config import settings


def create_llm():

    return ChatOpenAI(
        base_url=settings.vllm_url,

        api_key=settings.vllm_api_key,

        model=settings.model_name,

        temperature=settings.temperature,
    )
