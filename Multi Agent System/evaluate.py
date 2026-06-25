"""
Evaluation harness for the forensic multi-agent system.

Compares final_report.json NATO grades against ground truth from original_story.json,
using the shared W## witness IDs to build the name mapping automatically.

Usage:
    python evaluate.py
    python evaluate.py --report final_report.json --anon ../Datasets/The Murder of Roger Ackroyd/anonymized_story.json --original ../Datasets/The Murder of Roger Ackroyd/original_story.json
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
    Returns {anonymized_name: {"reliability": "A", "credibility": 1}}
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


def evaluate(report_path: Path, anon_path: Path, original_path: Path) -> None:
    report = load_json(report_path)
    ground_truth = build_ground_truth(anon_path, original_path)

    reliability_grades = {r["witness"]: r["grade"] for r in report.get("reliability_grades", [])}
    credibility_grades = {c["witness"]: c["credibility_grade"] for c in report.get("credibility_metrics", [])}

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
            "pred_r": pred_r,
            "true_r": true_r,
            "match_r": match_r,
            "dist_r": dist_r,
            "pred_c": pred_c,
            "true_c": true_c,
            "match_c": match_c,
            "dist_c": dist_c,
            "fuzzy": fuzzy,
        })

    # -----------------------------------------------------------------------
    # Print table
    # -----------------------------------------------------------------------
    col_w = 36
    header = (
        f"{'Witness':<{col_w}} "
        f"{'Reliability':^20}   "
        f"{'Credibility':^20}"
    )
    sub = (
        f"{'':<{col_w}} "
        f"{'Pred   True  Match':^20}   "
        f"{'Pred   True  Match':^20}"
    )
    sep = "-" * len(header)

    print()
    print("=" * len(header))
    print("  EVALUATION REPORT")
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

    # -----------------------------------------------------------------------
    # Missing witnesses
    # -----------------------------------------------------------------------
    report_witnesses_lookup = {w: {} for w in all_report_witnesses}
    in_gt_not_report = [
        f"{name} (original: {gt['original_name']})"
        for name, gt in ground_truth.items()
        if fuzzy_match(name, all_report_witnesses) is None and name not in all_report_witnesses
    ]

    if in_gt_not_report:
        print()
        print(f"  Witnesses in ground truth but NOT in report ({len(in_gt_not_report)}):")
        for m in in_gt_not_report:
            print(f"    - {m}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_paths() -> tuple[Path, Path, Path]:
    base = Path(__file__).parent
    datasets = base.parent / "Datasets" / "The Murder of Roger Ackroyd"
    return (
        base / "results" / "final_report.json",
        datasets / "anonymized_story.json",
        datasets / "original_story.json",
    )


def main() -> None:
    default_report, default_anon, default_orig = _default_paths()

    parser = argparse.ArgumentParser(description="Evaluate NATO grade accuracy of the forensic MAS.")
    parser.add_argument("--report",   default=str(default_report), help="Path to final_report.json")
    parser.add_argument("--anon",     default=str(default_anon),   help="Path to anonymized_story.json")
    parser.add_argument("--original", default=str(default_orig),   help="Path to original_story.json")
    args = parser.parse_args()

    evaluate(Path(args.report), Path(args.anon), Path(args.original))


if __name__ == "__main__":
    main()
