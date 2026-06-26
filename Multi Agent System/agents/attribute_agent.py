import logging
from agents.base import StructuredAgent

from prompts.attribute_prompt import (
    ATTRIBUTE_PROMPT
)

from models.attribute_models import (
    AttributeResult
)

log = logging.getLogger("pipeline")

ATTRIBUTE_BATCH_SIZE = 10
MAX_ATTRIBUTES_PER_PERSON = 15


class AttributeAgent:
    def __init__(self):
        self.agent = StructuredAgent(
            prompt=ATTRIBUTE_PROMPT,
            output_schema=AttributeResult
        )

    async def run(
        self,
        statements: list
    ):
        batches = [
            statements[i:i + ATTRIBUTE_BATCH_SIZE]
            for i in range(0, len(statements), ATTRIBUTE_BATCH_SIZE)
        ]

        merged: dict[str, list] = {}
        
        # --- NEW: List to hold telemetry for all batches ---
        all_telemetry = []

        for batch_num, batch in enumerate(batches, 1):
            log.info(
                f"[attribute] Batch {batch_num}/{len(batches)} "
                f"— {len(batch)} statements"
            )

            try:
                # --- NEW: Unpack the tuple and pass the agent name ---
                result, telemetry = await self.agent.invoke(batch, "AttributeAgent")
                
                # --- NEW: Save the telemetry for this batch ---
                all_telemetry.append(telemetry)
                
                self._merge(result.people, merged)
                
                log.info(
                    f"[attribute] Batch {batch_num}/{len(batches)} done "
                    f"— {len(result.people)} people"
                )

            except Exception as e:
                log.warning(
                    f"[attribute] Batch {batch_num}/{len(batches)} FAILED: {e}"
                )

        # --- NEW: Return the parsed result AND the accumulated telemetry list ---
        return self._to_list(merged), all_telemetry

    def _merge(self, people, merged: dict):
        for person in people:
            name = person.person if hasattr(person, "person") else person.get("person", "")
            attrs = person.attributes if hasattr(person, "attributes") else person.get("attributes", [])

            if not name:
                continue

            if name not in merged:
                merged[name] = []

            existing = merged[name]
            for attr in attrs:
                # Python-side cap per person
                if len(existing) >= MAX_ATTRIBUTES_PER_PERSON:
                    break
                existing.append(attr)

    def _to_list(self, merged: dict) -> list:
        result = []
        for person, attrs in merged.items():
            result.append({
                "person": person,
                "attributes": [
                    a.model_dump() if hasattr(a, "model_dump") else a
                    for a in attrs
                ]
            })
        return result