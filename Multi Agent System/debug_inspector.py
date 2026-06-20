import json
from datetime import datetime


class GraphDebugInspector:

    def __init__(self):
        self.logs = []

    # -----------------------------
    # CORE TRACE FUNCTION
    # -----------------------------
    def trace(self, node_name: str, input_data, output_data, error=None):

        self.logs.append({
            "node": node_name,
            "timestamp": datetime.utcnow().isoformat(),

            "input_type": str(type(input_data)),
            "output_type": str(type(output_data)),

            "input_preview": self._safe_preview(input_data),
            "output_preview": self._safe_preview(output_data),

            "error": str(error) if error else None
        })

    # -----------------------------
    # SAFE PREVIEW (prevents memory spam)
    # -----------------------------
    def _safe_preview(self, obj, max_len=800):

        try:
            if hasattr(obj, "model_dump"):
                obj = obj.model_dump()

            text = json.dumps(obj, default=str, indent=2)
            return text[:max_len]

        except Exception:
            return str(obj)[:max_len]

    # -----------------------------
    # EXPORT DEBUG REPORT
    # -----------------------------
    def export(self, path="graph_debug.json"):

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2)

        return path