"""
Batch comparison runner — grades all PDFs in 'Tests for prompt testing'
using both original and revised prompts, saves results as JSON.

Usage:
  python grader/run_comparison.py
  python grader/run_comparison.py --model claude-opus-4-6-20250725
  python grader/run_comparison.py --limit 5           # only first 5 PDFs total
  python grader/run_comparison.py --max-per-code 5    # max 5 PDFs per test code
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "grader"))

from grade import (
    load_env,
    create_client,
    get_default_model,
    grade_pdf,
    format_report,
    load_revised_prompt,
    RESULTS_DIR,
)

TESTING_DIR = ROOT / "Tests for prompt testing"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Batch comparison runner")
    parser.add_argument("--model", default=None, help="Anthropic model ID")
    parser.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0=all)")
    parser.add_argument("--test-code", default=None, help="Only process this test code (e.g. G3.1)")
    parser.add_argument("--max-per-code", type=int, default=5, help="Max PDFs per test code (0=all, default=5)")
    parser.add_argument("--dry-run", action="store_true", help="List PDFs without grading")

    args = parser.parse_args()

    load_env(ROOT / ".env")
    load_env(ROOT / "grader" / ".env")

    model = args.model or os.environ.get("ANTHROPIC_MODEL", "").strip() or get_default_model()

    # Collect PDFs
    pdfs = sorted(TESTING_DIR.glob("*.pdf"))
    if args.test_code:
        pdfs = [p for p in pdfs if args.test_code in p.name]

    # Cap per test code (default: 5 per code)
    if args.max_per_code > 0:
        by_code = defaultdict(list)
        for p in pdfs:
            m = re.search(r"G(\d+\.\d+)", p.name)
            code = "G" + m.group(1) if m else "unknown"
            by_code[code].append(p)
        capped = []
        for code in sorted(by_code.keys()):
            group = by_code[code]
            capped.extend(group[: args.max_per_code])
        pdfs = capped
        print(f"Capped to {args.max_per_code} per test code: {len(pdfs)} PDFs across {len(by_code)} codes")

    if args.limit > 0:
        pdfs = pdfs[: args.limit]

    print(f"Total PDFs to process: {len(pdfs)}")
    print(f"Model: {model}")
    print()

    if args.dry_run:
        code_counts = defaultdict(int)
        for p in pdfs:
            m = re.search(r"G(\d+\.\d+)", p.name)
            code = "G" + m.group(1) if m else "?"
            code_counts[code] += 1
            revised = load_revised_prompt(code)
            status = "✅ revised available" if revised else "❌ no revised prompt"
            print(f"  {p.name} → {code} [{status}]")
        print(f"\nPer test code: {dict(sorted(code_counts.items()))}")
        return 0

    try:
        client = create_client()
    except ValueError as e:
        print(str(e))
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Track progress
    total = len(pdfs)
    completed = 0
    errors = []
    start_time = time.time()

    for pdf_path in pdfs:
        completed += 1
        stem = pdf_path.stem.replace(" ", "_")
        out_path = RESULTS_DIR / f"{stem}_both.json"

        # Skip if already processed
        if out_path.exists():
            print(f"[{completed}/{total}] SKIP (already exists): {pdf_path.name}")
            continue

        print(f"[{completed}/{total}] Grading: {pdf_path.name}...", end=" ", flush=True)

        try:
            results = grade_pdf(pdf_path, client, model, prompt_mode="both")

            # Save results
            out_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Quick summary
            orig_total = sum(
                q.get("original", {}).get("total_score", 0)
                for q in results["questions"].values()
                if "original" in q and "error" not in q.get("original", {})
            )
            rev_total = sum(
                q.get("revised", {}).get("total_score", 0)
                for q in results["questions"].values()
                if "revised" in q and "error" not in q.get("revised", {})
            )
            max_total = sum(
                q.get("original", {}).get("total_max", 0)
                or q.get("revised", {}).get("total_max", 0)
                for q in results["questions"].values()
            )

            divergences = 0
            for q in results["questions"].values():
                o = q.get("original", {}).get("total_score", -1)
                r = q.get("revised", {}).get("total_score", -1)
                if o != r and o >= 0 and r >= 0:
                    divergences += 1

            print(f"Original={orig_total} Revised={rev_total} /{max_total} Divergences={divergences}")

        except Exception as e:
            print(f"ERROR: {e}")
            errors.append((pdf_path.name, str(e)))

        # Rate limiting between students
        time.sleep(1)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed: {completed - len(errors)}/{total}")
    print(f"Errors: {len(errors)}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}m)")
    if errors:
        print("\nFailed PDFs:")
        for name, err in errors:
            print(f"  {name}: {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
