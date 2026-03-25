"""
Generate a validation report comparing revised prompt scores
against previously graded scores.

Usage:
  python grader/validation_report.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = ROOT / "grader" / "results" / "validation"
REPORT_PATH = ROOT / "Reports" / "validation_report.md"


def load_results() -> list:
    """Load combined validation results."""
    combined = VALIDATION_DIR / "_all_results.json"
    if combined.exists():
        return json.loads(combined.read_text(encoding="utf-8"))

    # Fall back to individual files
    results = []
    for f in sorted(VALIDATION_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        results.append(json.loads(f.read_text(encoding="utf-8")))
    return results


def generate_report(results: list) -> str:
    """Generate a markdown validation report."""
    lines = []
    lines.append("# Prompt Validation Report")
    lines.append("")
    lines.append("Comparison of revised CJ prompt scores vs. previously graded scores.")
    lines.append("")

    # Aggregate stats
    total_questions = 0
    total_matches = 0
    total_errors = 0
    total_new_higher = 0
    total_old_higher = 0
    total_old_sum = 0
    total_new_sum = 0

    version_stats = defaultdict(lambda: {
        "questions": 0, "matches": 0, "errors": 0,
        "new_higher": 0, "old_higher": 0,
        "old_sum": 0, "new_sum": 0, "students": 0,
    })

    qnum_stats = defaultdict(lambda: {
        "questions": 0, "matches": 0, "new_higher": 0, "old_higher": 0,
        "diffs": [],
    })

    divergences = []  # (student, version, qnum, old, new, diff)

    for r in results:
        version = r["test_version"]
        student = r["student"]
        version_stats[version]["students"] += 1

        for qnum_str, q in r["questions"].items():
            qnum = int(qnum_str)

            if q.get("error"):
                total_errors += 1
                version_stats[version]["errors"] += 1
                continue

            total_questions += 1
            version_stats[version]["questions"] += 1
            qnum_stats[qnum]["questions"] += 1

            old_total = q.get("old_total", 0)
            new_total = q.get("new_total", 0)
            diff = q.get("diff", new_total - old_total)

            total_old_sum += old_total
            total_new_sum += new_total
            version_stats[version]["old_sum"] += old_total
            version_stats[version]["new_sum"] += new_total

            if q.get("match"):
                total_matches += 1
                version_stats[version]["matches"] += 1
                qnum_stats[qnum]["matches"] += 1
            else:
                qnum_stats[qnum]["diffs"].append(diff)
                divergences.append((student, version, qnum, old_total, new_total, diff))
                if diff > 0:
                    total_new_higher += 1
                    version_stats[version]["new_higher"] += 1
                    qnum_stats[qnum]["new_higher"] += 1
                elif diff < 0:
                    total_old_higher += 1
                    version_stats[version]["old_higher"] += 1
                    qnum_stats[qnum]["old_higher"] += 1

    # Overall summary
    scored = total_questions
    pct = total_matches / scored * 100 if scored > 0 else 0

    lines.append("## Overall Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Students validated | {len(results)} |")
    lines.append(f"| Questions scored | {scored} |")
    lines.append(f"| Errors | {total_errors} |")
    lines.append(f"| Agreement rate | {pct:.1f}% ({total_matches}/{scored}) |")
    lines.append(f"| Revised higher | {total_new_higher} |")
    lines.append(f"| Previously graded higher | {total_old_higher} |")
    lines.append(f"| Total old score | {total_old_sum} |")
    lines.append(f"| Total revised score | {total_new_sum} |")
    lines.append("")

    # Per-version breakdown
    lines.append("## Per-Version Breakdown")
    lines.append("")
    lines.append("| Version | Students | Questions | Agreement | Revised ↑ | Old ↑ | Old Total | New Total |")
    lines.append("|---------|----------|-----------|-----------|-----------|-------|-----------|-----------|")

    for ver in sorted(version_stats.keys()):
        s = version_stats[ver]
        q = s["questions"]
        m = s["matches"]
        p = m / q * 100 if q > 0 else 0
        lines.append(
            f"| {ver} | {s['students']} | {q} | {p:.0f}% ({m}/{q}) "
            f"| {s['new_higher']} | {s['old_higher']} "
            f"| {s['old_sum']} | {s['new_sum']} |"
        )
    lines.append("")

    # Per-question breakdown
    lines.append("## Per-Question Breakdown")
    lines.append("")
    lines.append("| Q# | Scored | Agreement | Revised ↑ | Old ↑ | Avg Diff |")
    lines.append("|----|--------|-----------|-----------|-------|----------|")

    for qnum in sorted(qnum_stats.keys()):
        s = qnum_stats[qnum]
        q = s["questions"]
        m = s["matches"]
        p = m / q * 100 if q > 0 else 0
        avg_diff = sum(s["diffs"]) / len(s["diffs"]) if s["diffs"] else 0
        lines.append(
            f"| Q{qnum} | {q} | {p:.0f}% ({m}/{q}) "
            f"| {s['new_higher']} | {s['old_higher']} "
            f"| {avg_diff:+.1f} |"
        )
    lines.append("")

    # Divergence details (top 20 biggest)
    divergences.sort(key=lambda x: abs(x[5]), reverse=True)
    lines.append("## Largest Divergences")
    lines.append("")
    lines.append("| Student | Version | Q# | Old | New | Diff |")
    lines.append("|---------|---------|----|----|-----|------|")

    for student, version, qnum, old, new, diff in divergences[:20]:
        sign = "+" if diff > 0 else ""
        lines.append(f"| {student} | {version} | Q{qnum} | {old} | {new} | {sign}{diff} |")
    lines.append("")

    # G6-G8 feedback samples (for manual review)
    lines.append("## G6-G8 Essay Feedback Samples")
    lines.append("")
    lines.append("Manual review recommended — check that feedback follows the new 3-paragraph structure.")
    lines.append("")

    g68_count = 0
    for r in results:
        if r["test_version"] not in ("G6.1", "G7.1", "G8.1"):
            continue
        if g68_count >= 5:
            break

        q11 = r["questions"].get("11")
        if not q11 or q11.get("error"):
            continue

        g68_count += 1
        lines.append(f"### {r['student']} ({r['test_version']})")
        lines.append(f"**Old score:** {q11['old_score']} | **New score:** {q11['new_score']}")
        lines.append("")
        lines.append("**New feedback:**")
        lines.append(f"> {q11.get('new_feedback', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


def main():
    results = load_results()
    if not results:
        print("No validation results found.")
        print(f"Expected at: {VALIDATION_DIR}")
        return 1

    print(f"Loaded {len(results)} validated students")

    report = generate_report(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Report saved to: {REPORT_PATH}")

    # Also print summary to console
    print()
    print(report[:2000])
    if len(report) > 2000:
        print("... (see full report in file)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
