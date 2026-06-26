import logging

from agents.base import StructuredAgent
from prompts.extraction_prompt import STATEMENT_EXTRACTION_PROMPT
from models.extraction_models import ExtractionResult

log = logging.getLogger("pipeline")

BATCH_SIZE = 10
MAX_STATEMENTS_PER_WITNESS = 10
MAX_STATEMENTS_PER_BATCH = 75


class StatementExtractionAgent:
    def __init__(self):
        self.agent = StructuredAgent(
            prompt=STATEMENT_EXTRACTION_PROMPT,
            output_schema=ExtractionResult
        )

    async def run(self, raw_story: dict) -> tuple[list[dict], list[dict]]:
        summary = raw_story.get("summary", "")
        witnesses = raw_story.get("witnesses", [])

        all_statements: list[dict] = []
        all_telemetry: list[dict] = []
        seen_ids: set[str] = set()
        global_counter = 1

        batches = [
            witnesses[i:i + BATCH_SIZE]
            for i in range(0, len(witnesses), BATCH_SIZE)
        ]

        for batch_num, batch in enumerate(batches, 1):
            log.info(
                f"[extraction] Batch {batch_num}/{len(batches)} "
                f"— {len(batch)} witnesses "
                f"({batch[0]['name']} … {batch[-1]['name']})"
            )

            payload = {
                "summary": summary,
                "witnesses": batch
            }

            try:
                result, telemetry = await self.agent.invoke(payload, "StatementExtractionAgent")
                
                # Append telemetry for this batch
                all_telemetry.append(telemetry)
                
                batch_statements = self._validate_and_normalize(
                    result, seen_ids, global_counter
                )

                if len(batch_statements) > MAX_STATEMENTS_PER_BATCH:
                    log.warning(
                        f"[extraction] Batch {batch_num}/{len(batches)} "
                        f"capped from {len(batch_statements)} to {MAX_STATEMENTS_PER_BATCH}"
                    )
                    batch_statements = batch_statements[:MAX_STATEMENTS_PER_BATCH]

                global_counter += len(batch_statements)
                all_statements.extend(batch_statements)
                for s in batch_statements:
                    seen_ids.add(s["statement_id"])

                log.info(
                    f"[extraction] Batch {batch_num}/{len(batches)} done "
                    f"— {len(batch_statements)} statements"
                )

            except Exception as e:
                log.warning(
                    f"[extraction] Batch {batch_num}/{len(batches)} FAILED: {e}"
                )

        return all_statements, all_telemetry

    def _validate_and_normalize(
        self,
        result: ExtractionResult,
        seen_ids: set,
        start_counter: int
    ) -> list[dict]:

        normalized = []
        counter = start_counter
        per_witness_counts: dict[str, int] = {}

        for s in result.statements:
            if not s.witness or not s.raw_text:
                continue

            witness_count = per_witness_counts.get(s.witness, 0)
            if witness_count >= MAX_STATEMENTS_PER_WITNESS:
                continue
            per_witness_counts[s.witness] = witness_count + 1

            sid = s.statement_id
            if not sid or sid in seen_ids:
                sid = f"S{counter:03d}"
                while sid in seen_ids:
                    counter += 1
                    sid = f"S{counter:03d}"

            seen_ids.add(sid)
            counter += 1

            normalized.append({
                "statement_id": sid,
                "witness": s.witness,
                "subject": s.subject,
                "time": s.time,
                "location": s.location,
                "action": s.action,
                "context": s.context,
                "raw_text": s.raw_text,
            })

        return normalized