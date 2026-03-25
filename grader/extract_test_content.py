"""
Extract passage text and question text from student test PDFs.

Uses existing student PDFs (one per test version) with the proven
extract_passage_and_questions() parser from grade.py.

Caches results to a JSON file for use by the validation runner.

Usage:
  python grader/extract_test_content.py
"""

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

# Reuse existing extraction from grade.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import extract_passage_and_questions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "grader" / "test_content_cache.json"

# Test versions we have revised prompts for
TARGET_VERSIONS = [
    "G3.1", "G3.2", "G3.3", "G3.4", "G3.5",
    "G4.1", "G4.2", "G4.3", "G4.4",
    "G5.1", "G5.2", "G5.3",
    "G6.1", "G7.1", "G8.1",
]


def find_student_pdf(version: str) -> Path:
    """Find a student PDF for a given test version to extract passage/questions from."""
    search_dirs = [
        ROOT / "Tests for prompt testing",
        ROOT / "Tests to Grade",
    ]

    for d in search_dirs:
        if not d.exists():
            continue
        for pdf in d.glob("*.pdf"):
            doc = fitz.open(str(pdf))
            text = doc[0].get_text()
            doc.close()
            m = re.search(r"Alpha Standardized Writing (G[3-8]\.\d+)", text)
            if m and m.group(1) == version:
                return pdf

    raise FileNotFoundError(f"No student PDF found for {version}")


def main():
    cache = {}

    for version in TARGET_VERSIONS:
        try:
            pdf_path = find_student_pdf(version)
        except FileNotFoundError as e:
            print(f"  SKIP {version}: {e}")
            continue

        print(f"Extracting {version} from {pdf_path.name}...", end=" ", flush=True)

        result = extract_passage_and_questions(pdf_path)
        passage = result["passage"]
        questions = {
            str(qnum): q["question"]
            for qnum, q in result["questions"].items()
        }

        cache[version] = {
            "passage": passage,
            "questions": questions,
            "source_pdf": pdf_path.name,
        }

        q_count = len(questions)
        p_len = len(passage)
        print(f"passage={p_len} chars, questions={q_count}")

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved to: {OUTPUT_PATH}")
    print(f"Versions cached: {len(cache)}")


if __name__ == "__main__":
    main()
