"""
Extract previously graded student tests from DOCX files.

Parses the 'Graded tests/' DOCX files and extracts structured data:
student name, test version, per-question scores, feedback, and responses.

Only extracts tests matching versions we have revised prompts for.
Caps at 10 students per test version.

Usage:
  python grader/extract_graded.py
  python grader/extract_graded.py --max-per-version 5
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from docx import Document

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
GRADED_DIR = ROOT / "Graded tests"
REVISED_DIR = ROOT / "Revised CJ Prompts"
OUTPUT_PATH = ROOT / "grader" / "extracted_graded_tests.json"

# Discover which test versions have revised prompts
AVAILABLE_VERSIONS = set()
for f in REVISED_DIR.glob("*.txt"):
    # e.g. "G3.1 CJ Revised.txt" → "3.1"
    name = f.stem.replace(" CJ Revised", "")
    if name.startswith("G"):
        AVAILABLE_VERSIONS.add(name[1:])  # "3.1"


def parse_docx(docx_path: Path) -> list:
    """
    Parse a graded-tests DOCX and return a list of student records.

    Each record:
    {
        "student": "Lavender Marrero",
        "test_version": "G3.3",
        "source_doc": "AlphaWrite Tests graded 3-8 V4.docx",
        "questions": {
            "1": {"score": "2/2", "feedback": "...", "response": "..."},
            ...
        }
    }
    """
    doc = Document(str(docx_path))
    paragraphs = doc.paragraphs
    source_name = docx_path.name

    # Phase 1: find all student start indices (Title-style paragraphs)
    student_starts = []
    for i, p in enumerate(paragraphs):
        if p.style and p.style.name == "Title" and p.text.strip():
            student_starts.append(i)

    records = []
    for idx, start_i in enumerate(student_starts):
        end_i = student_starts[idx + 1] if idx + 1 < len(student_starts) else len(paragraphs)

        title_text = paragraphs[start_i].text.strip()

        # Parse student name and version from title
        # Format: "FirstName LastName X.Y" or "FirstName MiddleName LastName X.Y"
        parts = title_text.rsplit(None, 1)
        if len(parts) < 2:
            continue

        version_str = parts[1]  # e.g. "3.3"
        student_name = parts[0]  # e.g. "Lavender Marrero"

        # Skip versions we don't have prompts for
        if version_str not in AVAILABLE_VERSIONS:
            continue

        # Phase 2: parse questions within this student's block
        questions = {}
        current_qnum = None
        current_section = None  # "score_feedback" or "response"
        current_score = None
        current_feedback_lines = []
        current_response_lines = []

        for j in range(start_i + 1, end_i):
            p = paragraphs[j]
            text = p.text.strip()
            style = p.style.name if p.style else ""

            if not text:
                continue

            # Detect question start: "Question {N}Graded"
            q_match = re.match(r"Question (\d+)Graded", text)
            if q_match and "Heading" in style:
                # Save previous question if any
                if current_qnum is not None:
                    questions[str(current_qnum)] = {
                        "score": current_score or "0/0",
                        "feedback": "\n".join(current_feedback_lines).strip(),
                        "response": "\n".join(current_response_lines).strip(),
                    }

                current_qnum = int(q_match.group(1))
                current_section = "score_feedback"
                current_score = None
                current_feedback_lines = []
                current_response_lines = []
                continue

            if current_qnum is None:
                continue

            # Detect score line: "Score: X/Y" in heading
            score_match = re.match(r"Score:\s*(\d+/\d+)", text)
            if score_match and "Heading" in style:
                current_score = score_match.group(1)
                continue

            # Detect "Your Response" heading — switch to response collection
            if text == "Your Response" and "Heading" in style:
                current_section = "response"
                continue

            # Detect next section heading (like "Score" heading) — skip
            if style == "Heading 4" and text == "Score":
                current_section = "score_feedback"
                continue

            # Collect text based on current section
            if current_section == "score_feedback" and style == "normal":
                # Skip bare score lines like "2/2" or "100%" or "67%"
                if re.match(r"^\d+/\d+$", text):
                    continue
                if re.match(r"^\d+%$", text):
                    continue
                # This is feedback text
                current_feedback_lines.append(text)

            elif current_section == "response" and style == "normal":
                current_response_lines.append(text)

        # Save the last question
        if current_qnum is not None:
            questions[str(current_qnum)] = {
                "score": current_score or "0/0",
                "feedback": "\n".join(current_feedback_lines).strip(),
                "response": "\n".join(current_response_lines).strip(),
            }

        if questions:
            records.append({
                "student": student_name,
                "test_version": f"G{version_str}",
                "source_doc": source_name,
                "questions": questions,
            })

    return records


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract graded tests from DOCX files")
    parser.add_argument(
        "--max-per-version", type=int, default=10,
        help="Maximum students to extract per test version (default: 10)"
    )
    args = parser.parse_args()

    print(f"Available revised prompt versions: {sorted(AVAILABLE_VERSIONS)}")
    print(f"Max per version: {args.max_per_version}")
    print()

    # Find all DOCX files
    docx_files = sorted(GRADED_DIR.glob("*.docx"))
    if not docx_files:
        print(f"No DOCX files found in {GRADED_DIR}")
        return 1

    # Extract from all files
    all_records = []
    for docx_path in docx_files:
        print(f"Parsing: {docx_path.name} ...", end=" ", flush=True)
        records = parse_docx(docx_path)
        print(f"{len(records)} matchable students")
        all_records.extend(records)

    # Cap per version
    version_counts = defaultdict(int)
    filtered = []
    for rec in all_records:
        ver = rec["test_version"]
        if version_counts[ver] < args.max_per_version:
            filtered.append(rec)
            version_counts[ver] += 1

    # Summary
    print(f"\nTotal extracted: {len(filtered)} students")
    total_questions = sum(len(r["questions"]) for r in filtered)
    print(f"Total questions: {total_questions}")
    print()
    print("Per-version breakdown:")
    for ver in sorted(version_counts.keys()):
        count = version_counts[ver]
        print(f"  {ver}: {count} students")

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
