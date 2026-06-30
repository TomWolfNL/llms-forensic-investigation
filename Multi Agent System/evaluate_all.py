"""
Evaluation harness for the forensic multi-agent system.
Runs across all datasets and aggregates metrics into an Excel file.
"""

import difflib
import json
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

RELIABILITY_ORDER = ["A", "B", "C", "D", "E", "F"]
CREDIBILITY_ORDER = [1, 2, 3, 4, 5, 6]

DATASETS = [
    "The Leavenworth Case",
    "The Murder of Roger Ackroyd",
    "The Mystery of the Blue Train",
    "The Mystery of the Yellow Room",
    "Whose Body"
]

def reliability_distance(a: str, b: str) -> int:
    try: return abs(RELIABILITY_ORDER.index(a) - RELIABILITY_ORDER.index(b))
    except ValueError: return 99

def credibility_distance(a: int, b: int) -> int:
    try: return abs(int(a) - int(b))
    except (TypeError, ValueError): return 99

def fuzzy_match(name: str, candidates: list[str], cutoff: float = 0.75) -> str | None:
    matches = difflib.get_close_matches(name.lower(), [c.lower() for c in candidates], n=1, cutoff=cutoff)
    if not matches: return None
    matched_lower = matches[0]
    for c in candidates:
        if c.lower() == matched_lower: return c
    return None

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def build_ground_truth(anon_path: Path, original_path: Path) -> dict[str, dict]:
    anon = load_json(anon_path)
    orig = load_json(original_path)
    orig_by_id = {w["id"]: w for w in orig.get("witnesses", [])}

    ground_truth = {}
    for w in anon.get("witnesses", []):
        wid = w.get("id")
        orig_w = orig_by_id.get(wid)
        if orig_w and "source_reliability" in orig_w and "information_credibility" in orig_w:
            ground_truth[w["name"]] = {
                "reliability": orig_w["source_reliability"],
                "credibility": int(orig_w["information_credibility"]),
                "original_name": orig_w["name"],
                "is_adversary": orig_w.get("is_adversary", False),
                "adversary_role": orig_w.get("adversary_role", "unknown")
            }
    return ground_truth

def match_name(name: str, ground_truth: dict) -> tuple[str | None, dict | None]:
    if name in ground_truth: return name, ground_truth[name]
    matched = fuzzy_match(name, list(ground_truth.keys()))
    if matched: return matched, ground_truth[matched]
    return None, None

def extract_grades(report: dict) -> tuple[dict, dict]:
    rel_grades = {}
    cred_grades = {}
    if "reliability_grades" in report:
        rel_grades = {r["witness"]: r["grade"] for r in report.get("reliability_grades", [])}
        cred_grades = {c["witness"]: c["credibility_grade"] for c in report.get("credibility_metrics", [])}
    elif "evaluations" in report:
        rel_grades = {e["witness"]: e["reliability_grade"] for e in report.get("evaluations", [])}
        cred_grades = {e["witness"]: e["credibility_grade"] for e in report.get("evaluations", [])}
    return rel_grades, cred_grades

# ---------------------------------------------------------------------------
# Data Aggregation Lists (For Excel Export)
# ---------------------------------------------------------------------------
excel_accuracy = []
excel_macro_telemetry = []
excel_micro_telemetry = []
excel_adversarial = []

# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate(dataset_name: str, report_path: Path, anon_path: Path, original_path: Path, model_type: str) -> None:
    if not report_path.exists():
        return

    report = load_json(report_path)
    ground_truth = build_ground_truth(anon_path, original_path)

    reliability_grades, credibility_grades = extract_grades(report)
    all_report_witnesses = sorted(set(reliability_grades) | set(credibility_grades))

    rows = []
    for witness in all_report_witnesses:
        matched_name, gt = match_name(witness, ground_truth)
        pred_r = reliability_grades.get(witness, "?")
        pred_c = credibility_grades.get(witness, "?")

        if gt:
            true_r = gt["reliability"]
            true_c = gt["credibility"]
            dist_r = reliability_distance(pred_r, true_r)
            dist_c = credibility_distance(pred_c, true_c)
        else:
            true_r = "?"
            true_c = "?"
            dist_r = dist_c = 99

        rows.append({"true_r": true_r, "dist_r": dist_r, "dist_c": dist_c})

    graded = [r for r in rows if r["true_r"] != "?"]
    n = len(graded)

    if n > 0:
        r_exact   = sum(1 for r in graded if r["dist_r"] == 0)
        r_within1 = sum(1 for r in graded if r["dist_r"] <= 1)
        c_exact   = sum(1 for r in graded if r["dist_c"] == 0)
        c_within1 = sum(1 for r in graded if r["dist_c"] <= 1)

        # Print to Terminal
        print(f"\n[{dataset_name}] - {model_type} ACCURACY")
        print(f"Matched Witnesses: {n}")
        print(f"Rel Exact: {r_exact}/{n} | Rel +/-1: {r_within1}/{n}")
        print(f"Cred Exact: {c_exact}/{n} | Cred +/-1: {c_within1}/{n}")

        # Append to Excel List
        excel_accuracy.append({
            "Dataset": dataset_name,
            "Model": model_type,
            "Witnesses_Graded": n,
            "Rel_Exact_Match_%": round((r_exact/n)*100, 1),
            "Rel_Within_1_%": round((r_within1/n)*100, 1),
            "Cred_Exact_Match_%": round((c_exact/n)*100, 1),
            "Cred_Within_1_%": round((c_within1/n)*100, 1)
        })

# ---------------------------------------------------------------------------
# Telemetry Dashboard
# ---------------------------------------------------------------------------

def parse_telemetry(log_list: list) -> tuple:
    in_tokens = out_tokens = 0
    exec_time = 0.0
    success_calls = total_calls = 0

    for log in log_list:
        in_tokens += log.get("input_tokens", 0)
        out_tokens += log.get("output_tokens", 0)
        exec_time += log.get("execution_time_seconds", 0.0)
        ratio_str = log.get("llm_success_ratio", "1/1")
        try:
            s, t = map(int, ratio_str.split('/'))
            success_calls += s
            total_calls += t
        except: pass
    return in_tokens, out_tokens, exec_time, success_calls, total_calls

def parse_telemetry_by_node(log_list: list) -> dict:
    nodes = {}
    for log in log_list:
        name = log.get("agent_name", "UnknownAgent")
        if name not in nodes:
            nodes[name] = {"in_tokens": 0, "out_tokens": 0, "exec_time": 0.0, "success_calls": 0, "total_calls": 0}
        nodes[name]["in_tokens"] += log.get("input_tokens", 0)
        nodes[name]["out_tokens"] += log.get("output_tokens", 0)
        nodes[name]["exec_time"] += log.get("execution_time_seconds", 0.0)
        ratio_str = log.get("llm_success_ratio", "1/1")
        try:
            s, t = map(int, ratio_str.split('/'))
            nodes[name]["success_calls"] += s
            nodes[name]["total_calls"] += t
        except: pass
    return nodes

def process_telemetry(dataset_name: str, mas_path: Path, base_path: Path):
    if not mas_path.exists() or not base_path.exists():
        return

    mas = load_json(mas_path)
    base = load_json(base_path)

    mas_logs = mas.get("telemetry_log", [])
    base_logs = base.get("telemetry_log", [])

    m_in, m_out, m_time, m_succ, m_tot = parse_telemetry(mas_logs)
    b_in, b_out, b_time, b_succ, b_tot = parse_telemetry(base_logs)

    m_total_tok = m_in + m_out
    b_total_tok = b_in + b_out
    
    m_sr = (m_succ / m_tot * 100) if m_tot > 0 else 0
    b_sr = (b_succ / b_tot * 100) if b_tot > 0 else 0

    # Append Macro Data for Excel
    excel_macro_telemetry.append({
        "Dataset": dataset_name,
        "MAS_Execution_Time_s": round(m_time, 2),
        "MAS_Total_Tokens": m_total_tok,
        "MAS_Success_Rate_%": round(m_sr, 1),
        "Base_Execution_Time_s": round(b_time, 2),
        "Base_Total_Tokens": b_total_tok,
        "Base_Success_Rate_%": round(b_sr, 1)
    })

    # Append Micro Data for Excel
    nodes_data = parse_telemetry_by_node(mas_logs)
    for name, data in nodes_data.items():
        n_sr = (data["success_calls"] / data["total_calls"] * 100) if data["total_calls"] > 0 else 0
        excel_micro_telemetry.append({
            "Dataset": dataset_name,
            "Agent_Node": name,
            "Time_s": round(data["exec_time"], 2),
            "In_Tokens": data["in_tokens"],
            "Out_Tokens": data["out_tokens"],
            "Success_Rate_%": round(n_sr, 1)
        })

# ---------------------------------------------------------------------------
# Adversarial Audit
# ---------------------------------------------------------------------------

def process_adversarial(dataset_name: str, mas_path: Path, base_path: Path, anon_path: Path, orig_path: Path):
    if not mas_path.exists() or not base_path.exists() or not anon_path.exists():
        return

    gt = build_ground_truth(anon_path, orig_path)
    mas = load_json(mas_path)
    base = load_json(base_path)
    
    _, mas_c = extract_grades(mas)
    _, base_c = extract_grades(base)

    mas_norm = {match_name(w, gt)[0]: g for w, g in mas_c.items() if match_name(w, gt)[0]}
    base_norm = {match_name(w, gt)[0]: g for w, g in base_c.items() if match_name(w, gt)[0]}

    adversaries = {name: data for name, data in gt.items() if data.get("is_adversary") is True}

    for name, gt_data in adversaries.items():
        m_grade = mas_norm.get(name)
        b_grade = base_norm.get(name)
        t_grade = gt_data['credibility']
        role = gt_data.get('adversary_role', 'deceptive target').replace("_", " ").title()

        m_dist = credibility_distance(m_grade, t_grade) if m_grade is not None else 99
        b_dist = credibility_distance(b_grade, t_grade) if b_grade is not None else 99

        if m_grade is None or b_grade is None:
            winner = "INCOMPLETE"
        elif m_dist < b_dist:
            winner = "MAS"
        elif b_dist < m_dist:
            winner = "BASELINE"
        else:
            winner = "DRAW"

        excel_adversarial.append({
            "Dataset": dataset_name,
            "Target": name,
            "Role": role,
            "True_Credibility": t_grade,
            "MAS_Score": m_grade,
            "Baseline_Score": b_grade,
            "Winner": winner
        })


# ---------------------------------------------------------------------------
# Main Execution Loop & Excel Export
# ---------------------------------------------------------------------------

def export_to_excel(output_path: Path):
    print(f"\n============================================================")
    print(f" 💾 EXPORTING METRICS TO EXCEL")
    print(f"============================================================")
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(excel_accuracy).to_excel(writer, sheet_name="Accuracy Stats", index=False)
        pd.DataFrame(excel_macro_telemetry).to_excel(writer, sheet_name="Macro Telemetry", index=False)
        pd.DataFrame(excel_micro_telemetry).to_excel(writer, sheet_name="Micro Telemetry", index=False)
        pd.DataFrame(excel_adversarial).to_excel(writer, sheet_name="Adversarial Audit", index=False)
    
    print(f"✅ Successfully saved comprehensive metrics to:\n   {output_path.name}")


def main() -> None:
    base_dir = Path(__file__).parent
    
    print("============================================================")
    print(" 🚀 STARTING BATCH EVALUATION PIPELINE")
    print("============================================================")

    for dataset in DATASETS:
        safe_name = dataset.replace(" ", "_")
        
        report_path = base_dir / "results" / f"{safe_name}_final_report.json"
        baseline_path = base_dir / "results" / f"{safe_name}_baseline_results.json"
        anon_path = base_dir.parent / "Datasets" / dataset / "anonymized_story.json"
        original_path = base_dir.parent / "Datasets" / dataset / "original_story.json"

        # Check if files exist before processing
        if not report_path.exists():
            print(f"[!] Missing MAS report for '{dataset}'... skipping.")
            continue
            
        # Extract and compile data
        evaluate(dataset, report_path, anon_path, original_path, "MAS (Pipeline)")
        evaluate(dataset, baseline_path, anon_path, original_path, "Baseline (Zero-Shot)")
        process_telemetry(dataset, report_path, baseline_path)
        process_adversarial(dataset, report_path, baseline_path, anon_path, original_path)

    # Export to Excel
    export_path = base_dir / "results" / "aggregated_evaluation_metrics.xlsx"
    export_to_excel(export_path)


if __name__ == "__main__":
    main()