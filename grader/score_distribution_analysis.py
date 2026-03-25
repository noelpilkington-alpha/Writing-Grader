"""
Score Distribution Analysis

Analyzes old vs revised prompt score distributions to determine
whether old prompts were systematically lenient.

Usage:
  python grader/score_distribution_analysis.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = ROOT / "grader" / "results" / "validation"
REPORT_PATH = ROOT / "Reports" / "score_distribution_analysis.md"


def load_results() -> list:
    combined = VALIDATION_DIR / "_all_results.json"
    if combined.exists():
        return json.loads(combined.read_text(encoding="utf-8"))
    results = []
    for f in sorted(VALIDATION_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        results.append(json.loads(f.read_text(encoding="utf-8")))
    return results


def pct(n, d):
    return f"{n/d*100:.1f}%" if d > 0 else "N/A"


def histogram_bar(count, total, width=30):
    filled = round(count / total * width) if total > 0 else 0
    return "█" * filled + "░" * (width - filled)


def generate_analysis(results: list) -> str:
    lines = []
    lines.append("# Score Distribution Analysis")
    lines.append("")
    lines.append("**Goal:** Determine whether old prompts were systematically lenient")
    lines.append("by analyzing score distributions, ceiling effects, and rubric dimension patterns.")
    lines.append("")

    # ═══════════════════════════════════════════════════
    # Collect all question-level data
    # ═══════════════════════════════════════════════════
    q11_old_scores = []
    q11_new_scores = []
    q11_old_pcts = []  # as % of max
    q11_new_pcts = []
    q11_ideas = []
    q11_ideas_max = []
    q11_conv = []
    q11_conv_max = []
    q11_details = []  # (student, version, old, new, ideas, conv, notes)

    q1_10_old = defaultdict(list)  # qnum -> list of old scores
    q1_10_new = defaultdict(list)  # qnum -> list of new scores
    q1_10_max = {}  # qnum -> max score

    version_q11_old = defaultdict(list)
    version_q11_new = defaultdict(list)

    for r in results:
        version = r["test_version"]
        student = r["student"]
        grade = int(version[1])

        for qnum_str, q in r["questions"].items():
            if q.get("error"):
                continue

            qnum = int(qnum_str)
            old_total = q.get("old_total", 0)
            new_total = q.get("new_total", 0)

            if qnum == 11:
                q11_old_scores.append(old_total)
                q11_new_scores.append(new_total)
                q11_old_pcts.append(old_total / 20 * 100)
                q11_new_pcts.append(new_total / 20 * 100)
                version_q11_old[version].append(old_total)
                version_q11_new[version].append(new_total)

                ideas = q.get("new_ideas", 0)
                ideas_max = q.get("new_ideas_max", 15)
                conv = q.get("new_conv", 0)
                conv_max = q.get("new_conv_max", 5)
                q11_ideas.append(ideas)
                q11_ideas_max.append(ideas_max)
                q11_conv.append(conv)
                q11_conv_max.append(conv_max)
                q11_details.append((
                    student, version, old_total, new_total,
                    ideas, ideas_max, conv, conv_max,
                    q.get("internal_notes", "")
                ))
            else:
                # Q1-Q10
                max_s = 2 if qnum <= 5 else 3
                q1_10_max[qnum] = max_s
                q1_10_old[qnum].append(old_total)
                q1_10_new[qnum].append(new_total)

    # ═══════════════════════════════════════════════════
    # SECTION 1: Q11 Essay Score Distribution
    # ═══════════════════════════════════════════════════
    lines.append("## 1. Q11 Essay Score Distribution (N=%d)" % len(q11_old_scores))
    lines.append("")

    # Old score distribution
    old_counter = Counter(q11_old_scores)
    new_counter = Counter(q11_new_scores)
    all_scores = sorted(set(list(old_counter.keys()) + list(new_counter.keys())))

    lines.append("### Score Frequency Table")
    lines.append("")
    lines.append("| Score | Old Count | Old % | New Count | New % |")
    lines.append("|-------|-----------|-------|-----------|-------|")
    n = len(q11_old_scores)
    for s in range(0, 21):
        oc = old_counter.get(s, 0)
        nc = new_counter.get(s, 0)
        if oc > 0 or nc > 0:
            lines.append(f"| {s}/20 | {oc} | {pct(oc, n)} | {nc} | {pct(nc, n)} |")
    lines.append("")

    # Summary stats
    old_mean = sum(q11_old_scores) / len(q11_old_scores) if q11_old_scores else 0
    new_mean = sum(q11_new_scores) / len(q11_new_scores) if q11_new_scores else 0
    old_median = sorted(q11_old_scores)[len(q11_old_scores) // 2] if q11_old_scores else 0
    new_median = sorted(q11_new_scores)[len(q11_new_scores) // 2] if q11_new_scores else 0

    # Ceiling effect: % scoring >= 80% (16+/20)
    old_ceiling = sum(1 for s in q11_old_scores if s >= 16)
    new_ceiling = sum(1 for s in q11_new_scores if s >= 16)

    # Floor effect: % scoring < 50% (< 10/20)
    old_floor = sum(1 for s in q11_old_scores if s < 10)
    new_floor = sum(1 for s in q11_new_scores if s < 10)

    lines.append("### Summary Statistics")
    lines.append("")
    lines.append("| Metric | Old Prompts | Revised Prompts |")
    lines.append("|--------|-------------|-----------------|")
    lines.append(f"| Mean | {old_mean:.1f}/20 ({old_mean/20*100:.0f}%) | {new_mean:.1f}/20 ({new_mean/20*100:.0f}%) |")
    lines.append(f"| Median | {old_median}/20 | {new_median}/20 |")
    lines.append(f"| Min | {min(q11_old_scores)}/20 | {min(q11_new_scores)}/20 |")
    lines.append(f"| Max | {max(q11_old_scores)}/20 | {max(q11_new_scores)}/20 |")
    lines.append(f"| Scoring ≥80% (16+) | {old_ceiling}/{n} ({pct(old_ceiling, n)}) | {new_ceiling}/{n} ({pct(new_ceiling, n)}) |")
    lines.append(f"| Scoring <50% (0-9) | {old_floor}/{n} ({pct(old_floor, n)}) | {new_floor}/{n} ({pct(new_floor, n)}) |")

    # Standard deviation
    old_var = sum((s - old_mean)**2 for s in q11_old_scores) / n
    new_var = sum((s - new_mean)**2 for s in q11_new_scores) / n
    lines.append(f"| Std Dev | {old_var**0.5:.1f} | {new_var**0.5:.1f} |")
    lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 2: Ceiling Effect Analysis
    # ═══════════════════════════════════════════════════
    lines.append("## 2. Ceiling Effect Analysis")
    lines.append("")
    lines.append("A ceiling effect occurs when scores cluster near the maximum, ")
    lines.append("reducing the ability to differentiate between students. ")
    lines.append("In educational assessment, if >40% of students score ≥80%, ")
    lines.append("the instrument likely lacks sufficient discrimination.")
    lines.append("")

    # Per-version ceiling
    lines.append("### Per-Version Ceiling Effect (Q11, scoring ≥16/20)")
    lines.append("")
    lines.append("| Version | N | Old ≥16 | Old % | New ≥16 | New % | Verdict |")
    lines.append("|---------|---|---------|-------|---------|-------|---------|")

    for ver in sorted(version_q11_old.keys()):
        old_list = version_q11_old[ver]
        new_list = version_q11_new[ver]
        vn = len(old_list)
        oc = sum(1 for s in old_list if s >= 16)
        nc = sum(1 for s in new_list if s >= 16)
        op = oc / vn * 100 if vn > 0 else 0
        np_ = nc / vn * 100 if vn > 0 else 0
        verdict = "CEILING" if op >= 40 else "OK"
        lines.append(f"| {ver} | {vn} | {oc} | {op:.0f}% | {nc} | {np_:.0f}% | {verdict} |")
    lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 3: Q1-Q10 Score Distributions
    # ═══════════════════════════════════════════════════
    lines.append("## 3. Q1-Q10 Score Distributions")
    lines.append("")
    lines.append("### Full Marks Rate (% of students receiving maximum score)")
    lines.append("")
    lines.append("| Q# | Max | N | Old Full Marks | Old % | New Full Marks | New % |")
    lines.append("|----|-----|---|----------------|-------|----------------|-------|")

    for qnum in sorted(q1_10_old.keys()):
        max_s = q1_10_max[qnum]
        old_list = q1_10_old[qnum]
        new_list = q1_10_new[qnum]
        qn = len(old_list)
        old_full = sum(1 for s in old_list if s == max_s)
        new_full = sum(1 for s in new_list if s == max_s)
        lines.append(
            f"| Q{qnum} | {max_s} | {qn} "
            f"| {old_full} | {pct(old_full, qn)} "
            f"| {new_full} | {pct(new_full, qn)} |"
        )
    lines.append("")

    # Per-question score distribution detail
    lines.append("### Detailed Score Distributions")
    lines.append("")

    for qnum in sorted(q1_10_old.keys()):
        max_s = q1_10_max[qnum]
        old_list = q1_10_old[qnum]
        new_list = q1_10_new[qnum]
        qn = len(old_list)

        old_mean_q = sum(old_list) / qn if qn else 0
        new_mean_q = sum(new_list) / qn if qn else 0

        lines.append(f"**Q{qnum}** (max {max_s}, N={qn}) — Old mean: {old_mean_q:.2f}, New mean: {new_mean_q:.2f}")
        lines.append("")
        lines.append(f"| Score | Old | New |")
        lines.append(f"|-------|-----|-----|")
        old_c = Counter(old_list)
        new_c = Counter(new_list)
        for s in range(0, max_s + 1):
            lines.append(f"| {s}/{max_s} | {old_c.get(s, 0)} ({pct(old_c.get(s, 0), qn)}) | {new_c.get(s, 0)} ({pct(new_c.get(s, 0), qn)}) |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 4: Rubric Dimension Analysis (Q11)
    # ═══════════════════════════════════════════════════
    lines.append("## 4. Q11 Rubric Dimension Breakdown (Revised Prompts)")
    lines.append("")
    lines.append("Since old prompts only gave total scores, we can only see rubric")
    lines.append("dimension detail from the revised prompts. This shows where the")
    lines.append("revised prompts are spending their deductions.")
    lines.append("")

    if q11_ideas:
        ideas_mean = sum(q11_ideas) / len(q11_ideas)
        ideas_max_val = q11_ideas_max[0] if q11_ideas_max else 15
        conv_mean = sum(q11_conv) / len(q11_conv)
        conv_max_val = q11_conv_max[0] if q11_conv_max else 5

        ideas_full = sum(1 for i in q11_ideas if i == ideas_max_val)
        conv_full = sum(1 for c in q11_conv if c == conv_max_val)
        n_q11 = len(q11_ideas)

        lines.append("| Dimension | Max | Mean | Mean % | Full Marks | Full % |")
        lines.append("|-----------|-----|------|--------|------------|--------|")
        lines.append(f"| Ideas | {ideas_max_val} | {ideas_mean:.1f} | {ideas_mean/ideas_max_val*100:.0f}% | {ideas_full}/{n_q11} | {pct(ideas_full, n_q11)} |")
        lines.append(f"| Conventions | {conv_max_val} | {conv_mean:.1f} | {conv_mean/conv_max_val*100:.0f}% | {conv_full}/{n_q11} | {pct(conv_full, n_q11)} |")
        lines.append(f"| **Total** | **20** | **{ideas_mean + conv_mean:.1f}** | **{(ideas_mean + conv_mean)/20*100:.0f}%** | | |")
        lines.append("")

        # Ideas score distribution
        lines.append("### Ideas Score Distribution")
        lines.append("")
        ideas_counter = Counter(q11_ideas)
        lines.append("| Score | Count | % |")
        lines.append("|-------|-------|---|")
        for s in range(0, ideas_max_val + 1):
            c = ideas_counter.get(s, 0)
            if c > 0:
                lines.append(f"| {s}/{ideas_max_val} | {c} | {pct(c, n_q11)} |")
        lines.append("")

        # Conventions score distribution
        lines.append("### Conventions Score Distribution")
        lines.append("")
        conv_counter = Counter(q11_conv)
        lines.append("| Score | Count | % |")
        lines.append("|-------|-------|---|")
        for s in range(0, conv_max_val + 1):
            c = conv_counter.get(s, 0)
            if c > 0:
                lines.append(f"| {s}/{conv_max_val} | {c} | {pct(c, n_q11)} |")
        lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 5: Grade-Band Analysis
    # ═══════════════════════════════════════════════════
    lines.append("## 5. Grade-Band Comparison")
    lines.append("")

    grade_bands = {
        "G3 (3rd grade)": ["G3.1", "G3.2", "G3.3", "G3.4", "G3.5"],
        "G4 (4th grade)": ["G4.1", "G4.2", "G4.3", "G4.4"],
        "G5 (5th grade)": ["G5.1", "G5.2"],
        "G6+ (6th-8th)": ["G6.1", "G7.1", "G8.1"],
    }

    for band_name, versions in grade_bands.items():
        band_old_q11 = []
        band_new_q11 = []
        band_old_q110 = []
        band_new_q110 = []

        for r in results:
            if r["test_version"] not in versions:
                continue
            for qnum_str, q in r["questions"].items():
                if q.get("error"):
                    continue
                qnum = int(qnum_str)
                old_total = q.get("old_total", 0)
                new_total = q.get("new_total", 0)
                if qnum == 11:
                    band_old_q11.append(old_total)
                    band_new_q11.append(new_total)
                else:
                    band_old_q110.append(old_total)
                    band_new_q110.append(new_total)

        lines.append(f"### {band_name}")
        lines.append("")

        if band_old_q11:
            bm_old = sum(band_old_q11) / len(band_old_q11)
            bm_new = sum(band_new_q11) / len(band_new_q11)
            lines.append(f"- **Q11 essays** (N={len(band_old_q11)}): Old mean {bm_old:.1f}/20 ({bm_old/20*100:.0f}%), New mean {bm_new:.1f}/20 ({bm_new/20*100:.0f}%), Δ = {bm_new - bm_old:+.1f}")

        if band_old_q110:
            bm_old_110 = sum(band_old_q110) / len(band_old_q110)
            bm_new_110 = sum(band_new_q110) / len(band_new_q110)
            # Compute average max for this band
            lines.append(f"- **Q1-Q10** (N={len(band_old_q110)}): Old mean {bm_old_110:.2f}, New mean {bm_new_110:.2f}, Δ = {bm_new_110 - bm_old_110:+.2f}")

        lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 6: Leniency Indicators
    # ═══════════════════════════════════════════════════
    lines.append("## 6. Leniency Indicators Summary")
    lines.append("")

    indicators = []

    # Indicator 1: Ceiling effect on Q11
    if q11_old_scores:
        ceiling_pct = old_ceiling / n * 100
        if ceiling_pct >= 60:
            indicators.append(("Q11 Ceiling Effect", "STRONG",
                f"{ceiling_pct:.0f}% of old Q11 scores ≥16/20 — extremely compressed range"))
        elif ceiling_pct >= 40:
            indicators.append(("Q11 Ceiling Effect", "MODERATE",
                f"{ceiling_pct:.0f}% of old Q11 scores ≥16/20 — limited discrimination"))
        else:
            indicators.append(("Q11 Ceiling Effect", "WEAK",
                f"{ceiling_pct:.0f}% of old Q11 scores ≥16/20 — adequate spread"))

    # Indicator 2: Score variance
    if q11_old_scores:
        old_sd = old_var ** 0.5
        if old_sd < 2.0:
            indicators.append(("Q11 Score Spread", "STRONG",
                f"Old SD={old_sd:.1f} — very compressed, most students score similarly"))
        elif old_sd < 3.0:
            indicators.append(("Q11 Score Spread", "MODERATE",
                f"Old SD={old_sd:.1f} — somewhat compressed"))
        else:
            indicators.append(("Q11 Score Spread", "WEAK",
                f"Old SD={old_sd:.1f} — reasonable spread"))

    # Indicator 3: Q1-Q10 full marks rate
    total_q110 = 0
    total_full_old = 0
    for qnum in q1_10_old:
        max_s = q1_10_max[qnum]
        total_q110 += len(q1_10_old[qnum])
        total_full_old += sum(1 for s in q1_10_old[qnum] if s == max_s)

    if total_q110 > 0:
        full_rate = total_full_old / total_q110 * 100
        if full_rate >= 70:
            indicators.append(("Q1-Q10 Full Marks Rate", "STRONG",
                f"{full_rate:.0f}% of old Q1-Q10 scores are full marks — almost no discrimination"))
        elif full_rate >= 50:
            indicators.append(("Q1-Q10 Full Marks Rate", "MODERATE",
                f"{full_rate:.0f}% of old Q1-Q10 scores are full marks"))
        else:
            indicators.append(("Q1-Q10 Full Marks Rate", "WEAK",
                f"{full_rate:.0f}% of old Q1-Q10 scores are full marks — reasonable"))

    # Indicator 4: Directional bias
    if q11_old_scores:
        old_higher_q11 = sum(1 for o, n in zip(q11_old_scores, q11_new_scores) if o > n)
        new_higher_q11 = sum(1 for o, n in zip(q11_old_scores, q11_new_scores) if n > o)
        if old_higher_q11 > new_higher_q11 * 3:
            indicators.append(("Directional Bias (Q11)", "STRONG",
                f"Old higher {old_higher_q11}x vs New higher {new_higher_q11}x — systematic unidirectional gap"))
        elif old_higher_q11 > new_higher_q11 * 1.5:
            indicators.append(("Directional Bias (Q11)", "MODERATE",
                f"Old higher {old_higher_q11}x vs New higher {new_higher_q11}x"))
        else:
            indicators.append(("Directional Bias (Q11)", "WEAK",
                f"Old higher {old_higher_q11}x vs New higher {new_higher_q11}x — roughly balanced"))

    lines.append("| Indicator | Strength | Evidence |")
    lines.append("|-----------|----------|----------|")
    for name, strength, evidence in indicators:
        lines.append(f"| {name} | **{strength}** | {evidence} |")
    lines.append("")

    # ═══════════════════════════════════════════════════
    # SECTION 7: Conclusions
    # ═══════════════════════════════════════════════════
    lines.append("## 7. Conclusions")
    lines.append("")

    strong_count = sum(1 for _, s, _ in indicators if s == "STRONG")
    moderate_count = sum(1 for _, s, _ in indicators if s == "MODERATE")

    if strong_count >= 2:
        lines.append("**Overall assessment: Evidence of old prompt leniency is STRONG.**")
        lines.append("")
        lines.append("Multiple indicators point to the old prompts being systematically generous:")
    elif strong_count >= 1 or moderate_count >= 2:
        lines.append("**Overall assessment: Evidence of old prompt leniency is MODERATE.**")
        lines.append("")
        lines.append("Some indicators suggest the old prompts were more generous than warranted:")
    else:
        lines.append("**Overall assessment: Evidence of old prompt leniency is WEAK.**")
        lines.append("")
        lines.append("The data does not clearly indicate systematic leniency in the old prompts.")

    lines.append("")
    for name, strength, evidence in indicators:
        lines.append(f"- **{name}** ({strength}): {evidence}")
    lines.append("")

    lines.append("### Recommended Next Steps")
    lines.append("")
    lines.append("1. **Manual expert grading** of 5-10 high-divergence Q11 essays to establish ground truth")
    lines.append("2. **Compare against STAAR anchor papers** if available, to calibrate expected score ranges")
    lines.append("3. **Review internal_notes** on the largest divergences to understand *why* scores differ")
    lines.append("")

    return "\n".join(lines)


def main():
    results = load_results()
    if not results:
        print("No validation results found.")
        return 1

    print(f"Loaded {len(results)} validated students")

    report = generate_analysis(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Report saved to: {REPORT_PATH}")

    # Print to console
    print()
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
