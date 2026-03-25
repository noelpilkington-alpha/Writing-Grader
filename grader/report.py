"""
Comparison report generator — reads all JSON results from grader/results/
and generates a comprehensive comparison report.

Usage:
  python grader/report.py
  python grader/report.py --csv   # also output CSV
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "grader" / "results"
REPORTS_DIR = ROOT / "Reports"


def load_all_results() -> list:
    """Load all *_both.json result files."""
    results = []
    for f in sorted(RESULTS_DIR.glob("*_both.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = f.name
            results.append(data)
        except Exception as e:
            print(f"Warning: could not load {f.name}: {e}")
    return results


def analyze_results(results: list) -> dict:
    """Analyze all results and compute statistics."""
    stats = {
        "total_students": len(results),
        "total_questions": 0,
        "questions_with_both": 0,
        "agreements": 0,
        "divergences": 0,
        "orig_higher": 0,
        "revised_higher": 0,
        "total_orig_score": 0,
        "total_rev_score": 0,
        "total_max_score": 0,
        "divergence_details": [],
        "by_question_type": defaultdict(lambda: {"agree": 0, "diverge": 0}),
        "by_test_code": defaultdict(lambda: {
            "students": 0, "agree": 0, "diverge": 0,
            "orig_total": 0, "rev_total": 0, "max_total": 0,
        }),
        "per_student": [],
    }

    for r in results:
        test_code = r.get("test", "?")
        student = r.get("student", "?")
        stats["by_test_code"][test_code]["students"] += 1

        student_orig = 0
        student_rev = 0
        student_max = 0
        student_divergences = []

        for qnum_str, q in r.get("questions", {}).items():
            qnum = int(qnum_str)
            stats["total_questions"] += 1

            orig = q.get("original", {})
            rev = q.get("revised", {})

            if "error" in orig or "error" in rev:
                continue
            if "total_score" not in orig or "total_score" not in rev:
                continue

            stats["questions_with_both"] += 1
            o_score = orig["total_score"]
            r_score = rev["total_score"]
            max_score = orig.get("total_max", rev.get("total_max", 0))

            student_orig += o_score
            student_rev += r_score
            student_max += max_score
            stats["total_orig_score"] += o_score
            stats["total_rev_score"] += r_score
            stats["total_max_score"] += max_score

            # Question type
            if qnum <= 5:
                qtype = "Q1-Q5 (Editing)"
            elif qnum <= 10:
                qtype = "Q6-Q10 (Writing)"
            else:
                qtype = "Q11 (Essay/Paragraph)"

            if o_score == r_score:
                stats["agreements"] += 1
                stats["by_question_type"][qtype]["agree"] += 1
                stats["by_test_code"][test_code]["agree"] += 1
            else:
                stats["divergences"] += 1
                stats["by_question_type"][qtype]["diverge"] += 1
                stats["by_test_code"][test_code]["diverge"] += 1

                if o_score > r_score:
                    stats["orig_higher"] += 1
                    direction = "orig_higher"
                else:
                    stats["revised_higher"] += 1
                    direction = "revised_higher"

                detail = {
                    "student": student,
                    "test": test_code,
                    "question": qnum,
                    "qtype": qtype,
                    "original_score": o_score,
                    "revised_score": r_score,
                    "max_score": max_score,
                    "diff": r_score - o_score,
                    "direction": direction,
                    "orig_ideas": orig.get("ideas_score", "?"),
                    "rev_ideas": rev.get("ideas_score", "?"),
                    "orig_conv": orig.get("conventions_score", "?"),
                    "rev_conv": rev.get("conventions_score", "?"),
                    "orig_notes": orig.get("internal_notes", "")[:200],
                    "rev_notes": rev.get("internal_notes", "")[:200],
                }
                stats["divergence_details"].append(detail)
                student_divergences.append(detail)

        stats["per_student"].append({
            "student": student,
            "test": test_code,
            "orig_total": student_orig,
            "rev_total": student_rev,
            "max_total": student_max,
            "divergences": len(student_divergences),
        })

    return stats


def generate_markdown_report(stats: dict) -> str:
    """Generate a markdown comparison report."""
    lines = []
    lines.append("# Prompt Comparison Report")
    lines.append(f"## Original vs Revised CJ Prompts\n")

    # Summary
    lines.append("## Summary Statistics\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Students graded | {stats['total_students']} |")
    lines.append(f"| Total questions scored | {stats['questions_with_both']} |")
    lines.append(f"| Agreements (same score) | {stats['agreements']} ({_pct(stats['agreements'], stats['questions_with_both'])}) |")
    lines.append(f"| Divergences (different score) | {stats['divergences']} ({_pct(stats['divergences'], stats['questions_with_both'])}) |")
    lines.append(f"| Original scored higher | {stats['orig_higher']} |")
    lines.append(f"| Revised scored higher | {stats['revised_higher']} |")
    lines.append(f"| Total original score | {stats['total_orig_score']}/{stats['total_max_score']} |")
    lines.append(f"| Total revised score | {stats['total_rev_score']}/{stats['total_max_score']} |")
    lines.append("")

    # By question type
    lines.append("## Divergence by Question Type\n")
    lines.append("| Question Type | Agreements | Divergences | Agreement Rate |")
    lines.append("|---------------|-----------|-------------|----------------|")
    for qtype in sorted(stats["by_question_type"].keys()):
        d = stats["by_question_type"][qtype]
        total = d["agree"] + d["diverge"]
        lines.append(f"| {qtype} | {d['agree']} | {d['diverge']} | {_pct(d['agree'], total)} |")
    lines.append("")

    # By test code
    lines.append("## Results by Test Code\n")
    lines.append("| Test | Students | Agreements | Divergences | Avg Orig | Avg Revised |")
    lines.append("|------|----------|-----------|-------------|----------|-------------|")
    for code in sorted(stats["by_test_code"].keys()):
        d = stats["by_test_code"][code]
        n = d["students"] or 1
        lines.append(
            f"| {code} | {d['students']} | {d['agree']} | {d['diverge']} "
            f"| {d.get('orig_total', 0)/n:.1f} | {d.get('rev_total', 0)/n:.1f} |"
        )
    # Compute by_test_code totals from per_student
    for ps in stats["per_student"]:
        code = ps["test"]
        if code in stats["by_test_code"]:
            stats["by_test_code"][code].setdefault("orig_total", 0)
            stats["by_test_code"][code].setdefault("rev_total", 0)
    lines.append("")

    # Per-student summary
    lines.append("## Per-Student Scores\n")
    lines.append("| Student | Test | Original | Revised | Max | Divergences |")
    lines.append("|---------|------|----------|---------|-----|-------------|")
    for ps in sorted(stats["per_student"], key=lambda x: (x["test"], x["student"])):
        flag = " ***" if ps["divergences"] > 0 else ""
        lines.append(
            f"| {ps['student']} | {ps['test']} | {ps['orig_total']} | {ps['rev_total']} "
            f"| {ps['max_total']} | {ps['divergences']}{flag} |"
        )
    lines.append("")

    # Divergence details
    if stats["divergence_details"]:
        lines.append("## Divergence Details\n")
        lines.append("| Student | Test | Q# | Type | Original | Revised | Diff | Orig Notes | Rev Notes |")
        lines.append("|---------|------|----|------|----------|---------|------|------------|-----------|")
        for d in sorted(stats["divergence_details"], key=lambda x: abs(x["diff"]), reverse=True):
            sign = "+" if d["diff"] > 0 else ""
            lines.append(
                f"| {d['student']} | {d['test']} | Q{d['question']} | {d['qtype']} "
                f"| {d['original_score']}/{d['max_score']} "
                f"(I:{d['orig_ideas']} C:{d['orig_conv']}) "
                f"| {d['revised_score']}/{d['max_score']} "
                f"(I:{d['rev_ideas']} C:{d['rev_conv']}) "
                f"| {sign}{d['diff']} | {d['orig_notes'][:80]} | {d['rev_notes'][:80]} |"
            )
        lines.append("")

    return "\n".join(lines)


def generate_csv(stats: dict, path: Path) -> None:
    """Generate CSV with per-question data."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Student", "Test", "Question", "Type",
            "Orig_Ideas", "Orig_Conv", "Orig_Total",
            "Rev_Ideas", "Rev_Conv", "Rev_Total",
            "Max", "Divergence",
        ])
        # We need the raw results for this
        results = load_all_results()
        for r in results:
            for qnum_str, q in r.get("questions", {}).items():
                qnum = int(qnum_str)
                orig = q.get("original", {})
                rev = q.get("revised", {})
                if "error" in orig or "error" in rev:
                    continue

                qtype = "Editing" if qnum <= 5 else ("Writing" if qnum <= 10 else "Essay")
                o_total = orig.get("total_score", "")
                r_total = rev.get("total_score", "")
                diverge = "YES" if o_total != r_total else ""

                writer.writerow([
                    r.get("student", ""),
                    r.get("test", ""),
                    qnum,
                    qtype,
                    orig.get("ideas_score", ""),
                    orig.get("conventions_score", ""),
                    o_total,
                    rev.get("ideas_score", ""),
                    rev.get("conventions_score", ""),
                    r_total,
                    orig.get("total_max", ""),
                    diverge,
                ])


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "N/A"
    return f"{num / denom * 100:.1f}%"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate comparison report")
    parser.add_argument("--csv", action="store_true", help="Also output CSV")
    args = parser.parse_args()

    results = load_all_results()
    if not results:
        print(f"No result files found in {RESULTS_DIR}")
        print("Run 'python grader/run_comparison.py' first.")
        return 1

    print(f"Loaded {len(results)} result files")

    stats = analyze_results(results)
    report = generate_markdown_report(stats)

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / "comparison_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Report saved to: {report_path}")

    if args.csv:
        csv_path = REPORTS_DIR / "comparison_data.csv"
        generate_csv(stats, csv_path)
        print(f"CSV saved to: {csv_path}")

    # Print summary to terminal
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Students: {stats['total_students']}")
    print(f"Questions scored: {stats['questions_with_both']}")
    print(f"Agreement rate: {_pct(stats['agreements'], stats['questions_with_both'])}")
    print(f"Divergences: {stats['divergences']}")
    print(f"  Original higher: {stats['orig_higher']}")
    print(f"  Revised higher: {stats['revised_higher']}")
    print(f"Total original: {stats['total_orig_score']}/{stats['total_max_score']}")
    print(f"Total revised:  {stats['total_rev_score']}/{stats['total_max_score']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
