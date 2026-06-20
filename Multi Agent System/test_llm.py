from utils.llm import create_llm

llm = create_llm()

resp = llm.invoke("Say 'LLM OK' in one line.")

print(resp.content)