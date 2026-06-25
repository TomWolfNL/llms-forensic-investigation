---
name: Wave 1 Improvements
overview: "Two targeted improvements: an automated evaluation harness for instant scoring, and anti-centrism prompt hardening for both grading scales. The reliability/credibility coupling was dropped — the NATO scales are intentionally independent (an unreliable source can still report true facts)."
todos:
  - id: eval-harness
    content: Create Multi Agent System/evaluate.py with CLI args, ID-based name mapping, fuzzy matching fallback, and printed scorecard
    status: completed
  - id: consistency-node
    content: Add RELIABILITY_FACTORS table, weighted score helper, and consistency_check_node to graph/nodes.py
    status: cancelled
  - id: rewire-workflow
    content: "Add consistency_check node to workflow.py and rewire edges: credibility/reliability → consistency_check → report"
    status: cancelled
  - id: centrism-credibility
    content: Add GRADE GATE section and anti-clustering rule to CREDIBILITY_OF_INFORMATION_PROMPT in prompts/reliability_prompt.py
    status: completed
  - id: centrism-reliability
    content: Replace GRADING GUIDANCE section in RELIABILITY_OF_SOURCE_PROMPT in prompts/credibility_prompt.py to remove 'start at C' baseline
    status: completed
isProject: false
---

# Wave 1 System Improvements

## 1. Evaluation Harness (`evaluate.py`)

### Key insight: shared witness IDs
Both `anonymized_story.json` and `original_story.json` already use the same `id` field (`W01`, `W02`, …). The harness joins them on this ID to build the ground truth map without any manual name lookup table.

### New file: `Multi Agent System/evaluate.py`

```
python evaluate.py
  --report   "Multi Agent System/final_report.json"
  --anon     "Datasets/The Murder of Roger Ackroyd/anonymized_story.json"
  --original "Datasets/The Murder of Roger Ackroyd/original_story.json"
```

Logic:
1. Load all three files.
2. Build `{anon_name: (true_reliability, true_credibility)}` by joining anonymized and original witnesses on shared `W##` IDs.
3. Match each witness in `final_report["reliability_grades"]` and `final_report["credibility_metrics"]` to the ground truth using exact name match first, then `difflib.get_close_matches` fallback (handles minor LLM name drift like `"Tobin Rusk"` → `"Toby Rusk"`).
4. Compute and print:
   - Per-witness comparison table (predicted vs. ground truth for both grades)
   - Exact match % for reliability
   - Exact match % for credibility
   - Within-±1 match % for both
   - List of witnesses present in ground truth but missing from the report

---

## 2. Anti-Centrism Prompt Hardening

### File naming reminder
The file names are swapped from what you'd expect:
- [`prompts/reliability_prompt.py`](Multi%20Agent%20System/prompts/reliability_prompt.py) contains `CREDIBILITY_OF_INFORMATION_PROMPT` (grades 1–6)
- [`prompts/credibility_prompt.py`](Multi%20Agent%20System/prompts/credibility_prompt.py) contains `RELIABILITY_OF_SOURCE_PROMPT` (grades A–F)

### A. Credibility of Information (`prompts/reliability_prompt.py`)

Remove the implicit "default to 3" tendency by replacing the vague metric guidance with explicit gate conditions:

Add a new **GRADE GATE** section just before the grade-mapping table:

```
GRADE 1 — Only when:
  - One or more independent witnesses confirm the same fact, OR
  - The claim is backed by a physical artefact or official record referenced in the input.
  Do NOT assign 1 because the information sounds plausible.

GRADE 2 — When:
  - No contradiction exists and contextual fit is strong.
  - Multiple statements from this witness reinforce the same claim.

GRADE 3 — Reserve for genuine uncertainty only.
  Do NOT use grade 3 as a default. If you lack strong evidence either way,
  examine whether a 4 is more defensible given missing corroboration.

GRADE 4 — When:
  - Corroboration is absent AND behavioral flags exist, OR
  - The witness account contains unexplained gaps.

GRADE 5 — When:
  - The information is directly contradicted by physical evidence or by
    two or more independent sources, OR
  - The source is confirmed to have lied in another part of their account.

GRADE 6 — Only when statements list is empty.
```

Also add at the bottom of the metric scoring section:
```
ANTI-CLUSTERING RULE:
After computing the weighted score, verify:
- If cross_confirmation > 0.65, the grade MUST be 1 or 2.
- If cross_confirmation < 0.30 AND internal_consistency < 0.40, the grade MUST be 4 or 5.
- Assigning grade 3 to more than 60% of witnesses in a case is a signal of under-differentiation.
```

### B. Reliability of Source (`prompts/credibility_prompt.py`)

The current prompt contains:
```
Start at C (fairly reliable) as the neutral baseline.
```
This single line is the primary cause of centrism.

Replace the entire **GRADING GUIDANCE** section with:

```
GRADING GUIDANCE

Do NOT start at C. Start at the grade the evidence most directly supports.

Assign A when ALL of these are true:
  - All statements are first-hand and direct.
  - No behavioral red flags of any kind.
  - No personal stake or bias.
  - No self-contradictions or retractions.

Assign B when:
  - Testimony is mostly direct with only minor reservations.
  - Any issues are individually minor and do not compound.

Assign C when:
  - Mixed evidence: some direct, some hearsay, or minor bias alongside direct observation.
  - Issues are present but none are disqualifying on their own.

Assign D when:
  - Hearsay or inference is the dominant mode.
  - Behavioral flag (evasion, concealment, retraction) is documented.
  - Strong personal interest is combined with unverifiable claims.

Assign E when:
  - The witness has admitted a lie in any part of their account, OR
  - A documented retraction undermines a key claim, OR
  - Behavioral record contains confirmed deception.
  A single admitted lie or major retraction is sufficient for E.

Assign F only when:
  - statements list is empty, OR
  - All statements are too vague to evaluate source quality.

ANTI-CENTRISM RULE:
Do NOT assign C by default. If the evidence clearly supports B or D, use it.
Assigning C to more than half of all witnesses signals under-differentiation.
```

---

## Affected Files Summary

| File | Change |
|---|---|
| `Multi Agent System/evaluate.py` | NEW — evaluation harness script |
| `prompts/reliability_prompt.py` | Add GRADE GATE section + anti-clustering rule to `CREDIBILITY_OF_INFORMATION_PROMPT` |
| `prompts/credibility_prompt.py` | Replace GRADING GUIDANCE section in `RELIABILITY_OF_SOURCE_PROMPT` |
