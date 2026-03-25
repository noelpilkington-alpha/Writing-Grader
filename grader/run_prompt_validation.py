"""
Prompt Validation Runner

Re-grades previously graded student tests using revised CJ prompts,
then compares the new scores against the original graded scores.

Prerequisites:
  1. Run extract_test_content.py to cache passage/question text
  2. Run extract_graded.py to extract student responses from DOCX files

Usage:
  python grader/run_prompt_validation.py
  python grader/run_prompt_validation.py --versions G6.1 G7.1 G8.1
  python grader/run_prompt_validation.py --max-students 5
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Optional

sys.stdout.reconfigure(encoding="utf-8")

# Reuse from grade.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import (
    ROOT,
    call_anthropic,
    create_client,
    get_default_model,
    infer_max_score,
    load_env,
    load_revised_prompt,
)

CONTENT_CACHE_PATH = ROOT / "grader" / "test_content_cache.json"
EXTRACTED_PATH = ROOT / "grader" / "extracted_graded_tests.json"
VALIDATION_DIR = ROOT / "grader" / "results" / "validation"


def load_content_cache() -> dict:
    """Load pre-extracted passage and question text per test version."""
    if not CONTENT_CACHE_PATH.exists():
        print(f"ERROR: Content cache not found at {CONTENT_CACHE_PATH}")
        print("Run: python grader/extract_test_content.py")
        sys.exit(1)
    return json.loads(CONTENT_CACHE_PATH.read_text(encoding="utf-8"))


def load_extracted_tests() -> list:
    """Load extracted student tests from DOCX files."""
    if not EXTRACTED_PATH.exists():
        print(f"ERROR: Extracted tests not found at {EXTRACTED_PATH}")
        print("Run: python grader/extract_graded.py")
        sys.exit(1)
    return json.loads(EXTRACTED_PATH.read_text(encoding="utf-8"))


def parse_score(score_str: str) -> tuple:
    """Parse 'X/Y' score string into (score, max)."""
    parts = score_str.split("/")
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    return 0, 0


def validate_student(
    student: dict,
    content_cache: dict,
    client,
    model: str,
) -> Optional[dict]:
    """
    Re-grade one student test using the revised prompt and compare
    against the previously graded scores.
    """
    version = student["test_version"]
    name = student["student"]

    # Load revised prompt
    prompt = load_revised_prompt(version)
    if not prompt:
        print(f"    No revised prompt for {version}, skipping")
        return None

    # Get passage and question text from cache
    if version not in content_cache:
        print(f"    No content cache for {version}, skipping")
        return None

    content = content_cache[version]
    passage = content["passage"]
    cached_questions = content["questions"]

    grade = int(version[1])
    essay_only = grade >= 6

    result = {
        "student": name,
        "test_version": version,
        "source_doc": student["source_doc"],
        "questions": {},
    }

    for qnum_str, q_data in student["questions"].items():
        qnum = int(qnum_str)

        # Skip Q1-Q10 for G6-G8
        if essay_only and qnum != 11:
            continue

        # Get question text from cache (fall back to generic if missing)
        question_text = cached_questions.get(qnum_str, f"Question {qnum}")

        response_text = q_data["response"]
        if not response_text.strip():
            # Blank response — score 0
            result["questions"][qnum_str] = {
                "old_score": q_data["score"],
                "new_score": "0/" + q_data["score"].split("/")[-1],
                "old_feedback": q_data["feedback"][:200],
                "new_feedback": "No response provided.",
                "match": q_data["score"].startswith("0"),
            }
            continue

        max_score = infer_max_score(version, qnum)

        try:
            new_result = call_anthropic(
                client, model, prompt,
                passage, question_text, response_text,
                qnum, max_score,
            )
        except Exception as e:
            result["questions"][qnum_str] = {
                "old_score": q_data["score"],
                "new_score": "ERROR",
                "error": str(e),
            }
            time.sleep(1)
            continue

        new_total = new_result.get("total_score", 0)
        new_max = new_result.get("total_max", max_score)
        new_score_str = f"{new_total}/{new_max}"

        old_score, old_max = parse_score(q_data["score"])

        result["questions"][qnum_str] = {
            "old_score": q_data["score"],
            "new_score": new_score_str,
            "old_total": old_score,
            "new_total": new_total,
            "match": old_score == new_total,
            "diff": new_total - old_score,
            "old_feedback": q_data["feedback"][:300],
            "new_feedback": new_result.get("feedback", "")[:500],
            "new_ideas": new_result.get("ideas_score", 0),
            "new_ideas_max": new_result.get("ideas_max", 0),
            "new_conv": new_result.get("conventions_score", 0),
            "new_conv_max": new_result.get("conventions_max", 0),
            "internal_notes": new_result.get("internal_notes", "")[:300],
        }

        time.sleep(0.5)  # Rate limiting

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate revised prompts against graded tests")
    parser.add_argument(
        "--versions", nargs="+", default=None,
        help="Only validate specific versions (e.g., G6.1 G7.1)"
    )
    parser.add_argument(
        "--max-students", type=int, default=None,
        help="Max students to validate (across all versions)"
    )
    parser.add_argument(
        "--model", default=None,
        help="Model ID override"
    )
    args = parser.parse_args()

    # Load env
    load_env(ROOT / ".env")
    load_env(ROOT / "grader" / ".env")

    model = args.model or os.environ.get("ANTHROPIC_MODEL", "").strip() or get_default_model()

    print("=== Prompt Validation Runner ===")
    print(f"Model: {model}")
    print()

    # Load data
    content_cache = load_content_cache()
    tests = load_extracted_tests()

    # Filter by version if specified
    if args.versions:
        tests = [t for t in tests if t["test_version"] in args.versions]

    # Limit total students
    if args.max_students:
        tests = tests[:args.max_students]

    print(f"Tests to validate: {len(tests)}")
    total_questions = sum(len(t["questions"]) for t in tests)
    print(f"Total questions: {total_questions}")
    print()

    # Create client
    try:
        client = create_client()
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    # Create output dir
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    # Run validation
    results = []
    matches = 0
    total = 0
    errors = 0

    for i, student in enumerate(tests):
        name = student["student"]
        version = student["test_version"]
        q_count = len(student["questions"])
        print(f"[{i+1}/{len(tests)}] {name} {version} ({q_count} questions)...", flush=True)

        result = validate_student(student, content_cache, client, model)
        if result is None:
            continue

        results.append(result)

        # Track stats
        for qnum_str, q in result["questions"].items():
            total += 1
            if q.get("error"):
                errors += 1
            elif q.get("match"):
                matches += 1

        # Save incrementally
        stem = f"{name.replace(' ', '_')}_{version}"
        out_path = VALIDATION_DIR / f"{stem}.json"
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Progress summary
        if total > 0:
            pct = matches / (total - errors) * 100 if (total - errors) > 0 else 0
            print(f"  → Running agreement: {pct:.1f}% ({matches}/{total-errors}), errors: {errors}")

    # Final summary
    print()
    print("=" * 50)
    print("VALIDATION COMPLETE")
    print(f"Students: {len(results)}")
    print(f"Questions: {total}")
    print(f"Errors: {errors}")
    scored = total - errors
    if scored > 0:
        print(f"Agreement: {matches}/{scored} ({matches/scored*100:.1f}%)")
    print(f"Results saved to: {VALIDATION_DIR}")

    # Save combined results
    combined_path = VALIDATION_DIR / "_all_results.json"
    combined_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Combined results: {combined_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
