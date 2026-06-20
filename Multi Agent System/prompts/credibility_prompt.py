CREDIBILITY_PROMPT = """
You are a strict JSON API.

Input:
{
  "reliability": {
      "witness": str,
      "evidence": list,
      "metrics": {
          "internal_consistency": float,
          "cross_confirmation": float,
          "detail_quality": float,
          "observation_quality": float,
          "contextual_alignment": float
      },
      "total_score": float
  }
}

Return EXACTLY:

{
  "witness": "string",
  "grade": "A|B|C|D|F",
  "score": 0.0,
  "explanation": "string",
  "evidence_used": ["string"]
}

Rules:

- witness MUST equal reliability.witness
- score MUST equal reliability.total_score
- explanation MUST reference only supplied evidence
- evidence_used MUST summarize supplied metrics
- Do NOT invent facts
- Output JSON only
"""