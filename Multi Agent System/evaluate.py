"""
Evaluation harness for the forensic multi-agent system.

Compares final_report.json and baseline_results.json NATO grades against 
ground truth from original_story.json, using the shared W## witness IDs 
to build the name mapping automatically.
"""

import argparse
import difflib
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

RELIABILITY_ORDER = ["A", "B", "C", "D", "E", "F"]
CREDIBILITY_ORDER = [1, 2, 3, 4, 5, 6]


def reliability_distance(a: str, b: str) -> int:
    """Absolute distance between two reliability grades (A-F)."""
    try:
        return abs(RELIABILITY_ORDER.index(a) - RELIABILITY_ORDER.index(b))
    except ValueError:
        return 99


def credibility_distance(a: int, b: int) -> int:
    """Absolute distance between two credibility grades (1-6)."""
    try:
        return abs(int(a) - int(b))
    except (TypeError, ValueError):
        return 99


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

def fuzzy_match(name: str, candidates: list[str], cutoff: float = 0.75) -> str | None:
    """Return the best fuzzy match from candidates, or None if below cutoff."""
    matches = difflib.get_close_matches(name.lower(), [c.lower() for c in candidates], n=1, cutoff=cutoff)
    if not matches:
        return None
    # Return the original-cased candidate
    matched_lower = matches[0]
    for c in candidates:
        if c.lower() == matched_lower:
            return c
    return None


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_ground_truth(anon_path: Path, original_path: Path) -> dict[str, dict]:
    """
    Returns {anonymized_name: {"reliability": "A", "credibility": 1, "is_adversary": bool, "adversary_role": str}}
    by joining on shared W## IDs.
    """
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
    """
    Try exact match first, then fuzzy.
    Returns (matched_anon_name, gt_entry) or (None, None).
    """
    if name in ground_truth:
        return name, ground_truth[name]

    matched = fuzzy_match(name, list(ground_truth.keys()))
    if matched:
        return matched, ground_truth[matched]

    return None, None


def extract_grades(report: dict) -> tuple[dict, dict]:
    """Dynamically extracts grades for either MAS or Baseline schema."""
    rel_grades = {}
    cred_grades = {}
    
    # 1. Check for MAS format
    if "reliability_grades" in report:
        rel_grades = {r["witness"]: r["grade"] for r in report.get("reliability_grades", [])}
        cred_grades = {c["witness"]: c["credibility_grade"] for c in report.get("credibility_metrics", [])}
    
    # 2. Check for Baseline format
    elif "evaluations" in report:
        rel_grades = {e["witness"]: e["reliability_grade"] for e in report.get("evaluations", [])}
        cred_grades = {e["witness"]: e["credibility_grade"] for e in report.get("evaluations", [])}

    return rel_grades, cred_grades


def evaluate(report_path: Path, anon_path: Path, original_path: Path, title: str) -> None:
    if not report_path.exists():
        print(f"\n[!] Missing report: {report_path.name}")
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
            match_r = "OK" if dist_r == 0 else (f"+/-{dist_r}" if dist_r <= 1 else f"off{dist_r}")
            match_c = "OK" if dist_c == 0 else (f"+/-{dist_c}" if dist_c <= 1 else f"off{dist_c}")
            fuzzy = " (fuzzy)" if matched_name != witness else ""
        else:
            true_r = "?"
            true_c = "?"
            dist_r = dist_c = 99
            match_r = match_c = "—"
            fuzzy = " (no GT)"

        rows.append({
            "witness": witness,
            "pred_r": pred_r, "true_r": true_r, "match_r": match_r, "dist_r": dist_r,
            "pred_c": pred_c, "true_c": true_c, "match_c": match_c, "dist_c": dist_c,
            "fuzzy": fuzzy,
        })

    # -----------------------------------------------------------------------
    # Print table
    # -----------------------------------------------------------------------
    col_w = 36
    header = f"{'Witness':<{col_w}} {'Reliability':^20}   {'Credibility':^20}"
    sub = f"{'':<{col_w}} {'Pred  True  Match':^20}   {'Pred  True  Match':^20}"
    sep = "-" * len(header)

    print()
    print("=" * len(header))
    print(f"  {title}")
    print(f"  Report : {report_path.name}")
    print(f"  Dataset: {anon_path.parent.name}")
    print("=" * len(header))
    print(header)
    print(sub)
    print(sep)

    for r in rows:
        label = f"{r['witness']}{r['fuzzy']}"
        rel_col = f"{r['pred_r']:>4}  {r['true_r']:>4}  {r['match_r']:>5}"
        cred_col = f"{str(r['pred_c']):>4}  {str(r['true_c']):>4}  {r['match_c']:>5}"
        print(f"{label:<{col_w}} {rel_col:^20}   {cred_col:^20}")

    print(sep)

    # -----------------------------------------------------------------------
    # Summary stats (only rows that have ground truth)
    # -----------------------------------------------------------------------
    graded = [r for r in rows if r["true_r"] != "?"]
    n = len(graded)

    if n == 0:
        print("\nNo matched witnesses with ground truth — cannot compute accuracy.")
        return

    r_exact   = sum(1 for r in graded if r["dist_r"] == 0)
    r_within1 = sum(1 for r in graded if r["dist_r"] <= 1)
    c_exact   = sum(1 for r in graded if r["dist_c"] == 0)
    c_within1 = sum(1 for r in graded if r["dist_c"] <= 1)

    print()
    print(f"  Matched witnesses (with ground truth): {n}")
    print()
    print(f"  Reliability of Source (A-F)")
    print(f"    Exact match  : {r_exact}/{n}  ({100*r_exact/n:.0f}%)")
    print(f"    Within +/-1  : {r_within1}/{n}  ({100*r_within1/n:.0f}%)")
    print()
    print(f"  Credibility of Information (1-6)")
    print(f"    Exact match  : {c_exact}/{n}  ({100*c_exact/n:.0f}%)")
    print(f"    Within +/-1  : {c_within1}/{n}  ({100*c_within1/n:.0f}%)")


# ---------------------------------------------------------------------------
# Telemetry Dashboard
# ---------------------------------------------------------------------------

def parse_telemetry(log_list: list) -> tuple:
    """Aggregates totals from a list of telemetry dictionaries."""
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
        except (ValueError, AttributeError):
            pass

    return in_tokens, out_tokens, exec_time, success_calls, total_calls


def parse_telemetry_by_node(log_list: list) -> dict:
    """Groups telemetry metrics by agent_name."""
    nodes = {}
    for log in log_list:
        name = log.get("agent_name", "UnknownAgent")
        if name not in nodes:
            nodes[name] = {
                "in_tokens": 0, "out_tokens": 0,
                "exec_time": 0.0, "success_calls": 0, "total_calls": 0
            }
        
        nodes[name]["in_tokens"] += log.get("input_tokens", 0)
        nodes[name]["out_tokens"] += log.get("output_tokens", 0)
        nodes[name]["exec_time"] += log.get("execution_time_seconds", 0.0)
        
        ratio_str = log.get("llm_success_ratio", "1/1")
        try:
            s, t = map(int, ratio_str.split('/'))
            nodes[name]["success_calls"] += s
            nodes[name]["total_calls"] += t
        except (ValueError, AttributeError):
            pass
            
    return nodes


def print_telemetry_dashboard(mas_path: Path, base_path: Path) -> None:
    if not mas_path.exists() or not base_path.exists():
        return

    mas = load_json(mas_path)
    base = load_json(base_path)

    mas_logs = mas.get("telemetry_log", [])
    base_logs = base.get("telemetry_log", [])

    if not mas_logs and not base_logs:
        return

    # --- 1. MACRO DASHBOARD (Totals) ---
    m_in, m_out, m_time, m_succ, m_tot = parse_telemetry(mas_logs)
    b_in, b_out, b_time, b_succ, b_tot = parse_telemetry(base_logs)

    m_total_tok = m_in + m_out
    b_total_tok = b_in + b_out

    m_tps = m_total_tok / m_time if m_time > 0 else 0
    b_tps = b_total_tok / b_time if b_time > 0 else 0
    
    m_sr = (m_succ / m_tot * 100) if m_tot > 0 else 0
    b_sr = (b_succ / b_tot * 100) if b_tot > 0 else 0

    print("\n============================================================")
    print(" 📊 MACRO TELEMETRY (Pipeline Totals)")
    print("============================================================")
    print(f"{'Metric':<25} | {'Baseline (Zero-Shot)':<20} | {'MAS (Pipeline)':<20}")
    print("-" * 70)
    print(f"{'Execution Time (s)':<25} | {b_time:>18.2f} | {m_time:>18.2f}")
    print(f"{'Total Tokens':<25} | {b_total_tok:>18,} | {m_total_tok:>18,}")
    print(f"{'  ├ Input Tokens':<25} | {b_in:>18,} | {m_in:>18,}")
    print(f"{'  └ Output Tokens':<25} | {b_out:>18,} | {m_out:>18,}")
    print(f"{'Throughput (Tokens/sec)':<25} | {b_tps:>18.1f} | {m_tps:>18.1f}")
    print(f"{'LLM Call Success Rate':<25} | {b_sr:>17.1f}% | {m_sr:>17.1f}%")
    print("-" * 70)

    # --- 2. MICRO DASHBOARD (Node Breakdown) ---
    print("\n============================================================")
    print(" 🔬 MICRO TELEMETRY (MAS Node Breakdown)")
    print("============================================================")
    
    nodes_data = parse_telemetry_by_node(mas_logs)
    
    if not nodes_data:
        print("No node-level telemetry found.")
        return

    # Table Header
    print(f"{'Agent Node':<30} | {'Time (s)':<10} | {'In Tokens':<12} | {'Out Tokens':<12} | {'Success'}")
    print("-" * 82)
    
    # Sort by execution time (longest running first) to easily spot bottlenecks
    sorted_nodes = sorted(nodes_data.items(), key=lambda item: item[1]['exec_time'], reverse=True)

    for name, data in sorted_nodes:
        t_time = data["exec_time"]
        t_in = data["in_tokens"]
        t_out = data["out_tokens"]
        
        # Calculate success rate for this specific node
        n_succ = data["success_calls"]
        n_tot = data["total_calls"]
        n_sr = (n_succ / n_tot * 100) if n_tot > 0 else 0
        
        print(f"{name:<30} | {t_time:>9.2f}s | {t_in:>12,} | {t_out:>12,} | {n_sr:>5.1f}% ({n_succ}/{n_tot})")
    print("-" * 82)
    print()


# ---------------------------------------------------------------------------
# Adversarial Audit
# ---------------------------------------------------------------------------

def print_adversarial_audit(mas_path: Path, base_path: Path, anon_path: Path, orig_path: Path) -> None:
    if not mas_path.exists() or not base_path.exists():
        return

    gt = build_ground_truth(anon_path, orig_path)
    mas = load_json(mas_path)
    base = load_json(base_path)
    
    _, mas_c = extract_grades(mas)
    _, base_c = extract_grades(base)

    mas_norm = {match_name(w, gt)[0]: g for w, g in mas_c.items() if match_name(w, gt)[0]}
    base_norm = {match_name(w, gt)[0]: g for w, g in base_c.items() if match_name(w, gt)[0]}

    adversaries = {name: data for name, data in gt.items() if data.get("is_adversary") is True}

    if not adversaries:
        return

    print("\n============================================================")
    print(" 🎯 ADVERSARIAL AUDIT (High-Value Targets Only)")
    print("============================================================")
    print("Evaluating performance specifically on witnesses flagged as")
    print("Deceptive, Hostile, or Prime Suspects in the Ground Truth.\n")

    mas_wins = 0
    base_wins = 0

    for idx, (name, gt_data) in enumerate(adversaries.items(), 1):
        m_grade = mas_norm.get(name)
        b_grade = base_norm.get(name)
        t_grade = gt_data['credibility']
        role = gt_data.get('adversary_role', 'deceptive target').replace("_", " ").title()

        m_dist = credibility_distance(m_grade, t_grade) if m_grade is not None else 99
        b_dist = credibility_distance(b_grade, t_grade) if b_grade is not None else 99

        print(f"TARGET {idx}: {name} [{role}]")
        print("-" * 60)
        print(f"True Credibility: {t_grade}")
        print(f"MAS Score       : {m_grade if m_grade is not None else '?'} (Off by {m_dist if m_grade is not None else 'N/A'})")
        print(f"Baseline Score  : {b_grade if b_grade is not None else '?'} (Off by {b_dist if b_grade is not None else 'N/A'})")

        if m_grade is None or b_grade is None:
            print("Outcome         : [INCOMPLETE] One or both systems missed this target.\n")
            continue

        if m_dist < b_dist:
            print("Outcome         : [WIN] MAS outperformed Baseline.\n")
            mas_wins += 1
        elif b_dist < m_dist:
            print("Outcome         : [LOSS] Baseline outperformed MAS.\n")
            base_wins += 1
        else:
            print("Outcome         : [DRAW] Both systems achieved identical distance.\n")

    print("============================================================")
    print(" 🚨 ADVERSARIAL SUMMARY")
    print("============================================================")
    print(f"MAS Accuracy Wins      : {mas_wins}")
    print(f"Baseline Accuracy Wins : {base_wins}")
    if mas_wins > base_wins:
        print("Conclusion: The MAS pipeline is superior at detecting deception in this dataset.")
    elif base_wins > mas_wins:
        print("Conclusion: The Baseline is currently superior at identifying deception.")
    else:
        print("Conclusion: Both models perform equally well (or poorly) on deceptive targets.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MAS vs Baseline.")
    parser.add_argument("--dataset", default="The Leavenworth Case")
    parser.add_argument("--report", default="results/final_report.json")
    parser.add_argument("--baseline", default="results/baseline_results.json")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    report_path = base_dir / args.report
    baseline_path = base_dir / args.baseline
    
    anon_path = base_dir.parent / "Datasets" / args.dataset / "anonymized_story.json"
    original_path = base_dir.parent / "Datasets" / args.dataset / "original_story.json"

    # 1. Evaluate MAS General Accuracy
    evaluate(report_path, anon_path, original_path, "MAS PIPELINE EVALUATION")
    
    # 2. Evaluate Baseline General Accuracy
    evaluate(baseline_path, anon_path, original_path, "BASELINE EVALUATION")

    # 3. Print Telemetry & Efficiency Metrics
    print_telemetry_dashboard(report_path, baseline_path)

    # 4. Print High-Stakes Adversarial Audit
    print_adversarial_audit(report_path, baseline_path, anon_path, original_path)


if __name__ == "__main__":
    main()