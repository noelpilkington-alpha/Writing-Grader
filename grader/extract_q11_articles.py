"""Extract Q11 articles from G3-G5 master PDFs and add to test_content_cache.json.

For G3-G5 tests, Q11 references a separate article from the Q1-Q10 passage.
This script extracts those articles from the master PDFs so the grading
pipeline can include them when grading Q11.
"""

import json
import re
import sys
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "grader" / "test_content_cache.json"

# Master PDF locations
MASTER_DIRS = {
    "G3": ROOT / "G3",
    "G4": ROOT / "G4",
    "G5": ROOT / "G5",
}


def find_master_pdf(test_code: str) -> Path | None:
    """Find the master PDF for a given test code like G3.2."""
    grade = test_code.split(".")[0]  # "G3"
    master_dir = MASTER_DIRS.get(grade)
    if not master_dir or not master_dir.exists():
        return None
    pattern = f"Alpha Standardized Writing {test_code}.pdf"
    path = master_dir / pattern
    if path.exists():
        return path
    return None


def extract_q11_article(pdf_path: Path) -> str:
    """Extract the Q11 article text from a master PDF.

    The article appears between the Q1-Q10 passage pages and the Q11 prompt.
    We look for the article title page (which contains "write one paragraph"
    or similar instruction) and extract text until we hit the Q11 prompt
    ("Prompt" / "Read the article" / "Based on the information").
    """
    doc = fitz.open(str(pdf_path))
    all_text = []
    for page in doc:
        all_text.append(page.get_text())
    doc.close()

    full_text = "\n".join(all_text)

    # Normalize non-breaking spaces to regular spaces for pattern matching
    norm_text = full_text.replace("\xa0", " ")

    # Strategy: The Q11 article appears between "Read the selection." (after
    # Q10) and the Q11 "Prompt" section. In master PDFs, the structure is:
    #   ... Q10 content ... "Read the selection." ... [Article Title] ...
    #   [article body] ... "Prompt" ... [Q11 instructions]
    #
    # In student PDFs, the article appears between Q10's "N Words" marker
    # and Q11's "Prompt" marker.

    # Find the article title: look for the line right after "Read the selection."
    # that appears near the Q11 section (roughly past the halfway point)
    start_idx = None

    # Method 1: "Read the selection." marker before the article
    for m in re.finditer(r"Read the selection\.\n", norm_text):
        # Only consider occurrences in the second half of the PDF
        if m.start() > len(norm_text) * 0.3:
            start_idx = m.end()
            break

    # Method 2: "write one paragraph" instruction (with possible nbsp)
    if start_idx is None:
        m = re.search(
            r"You will read a short text and write\s+one\s+paragraph",
            norm_text,
            re.IGNORECASE,
        )
        if m:
            pre = norm_text[: m.start()]
            last_nl = pre.rfind("\n")
            start_idx = last_nl + 1 if last_nl >= 0 else m.start()

    if start_idx is None:
        return ""

    # Find article end: the "Prompt" header or "Read the article/excerpt" line
    article_region = norm_text[start_idx:]
    end_idx = None

    # Look for "\nPrompt\n" first (most reliable)
    m = re.search(r"\nPrompt\n", article_region)
    if m:
        end_idx = m.start()

    # Try: "Read the article/excerpt/story" as prompt start (no "Prompt" header)
    if end_idx is None:
        m = re.search(
            r'\n(?:Read the article|Read the excerpt|Read the story|Read [\u201c"])',
            article_region,
        )
        if m:
            end_idx = m.start()

    # Last resort: "Write your paragraph"
    if end_idx is None:
        m = re.search(r"Write your paragraph", article_region)
        if m:
            end_idx = m.start()

    if end_idx is None:
        return ""

    raw_article = article_region[:end_idx]

    # Clean up the article text
    lines = raw_article.split("\n")
    cleaned = []

    # Skip patterns: rubric, instructions, metadata
    skip_phrases = [
        "What Strong Writing",
        "Ideas &",
        "Writing Conventions",
        "Writing",
        "Conventions",
        "Organization",
        "Area",
        "Score",
        "points",
        "You have a clear main",
        "Your paragraph stays",
        "You give strong reasons",
        "Your ideas are organized",
        "You use correct grammar",
        "You spell words correctly",
        "You use proper punctuation",
        "You use correct sentence",
        "examples to support your point",
        "capitals and periods",
        "structure.",
        "sentence.",
        "write one paragraph",
        "scored based on",
        "in response to a prompt",
        "following two areas",
        "Third party trademark",
        "Instructions",
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines matching any skip phrase (case-insensitive)
        if any(w.lower() in line.lower() for w in skip_phrases):
            continue
        # Skip standalone small numbers (page numbers, scores, rubric scores)
        if re.match(r"^[0-9]{1,2}$", line):
            continue
        # Skip standalone periods or other single-char noise
        if len(line) <= 1:
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


def main():
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    results = {}
    for test_code in sorted(cache.keys()):
        grade_num = int(test_code.split(".")[0][1:])
        if grade_num >= 6:
            # G6-G8 use the same passage for Q11, no separate article
            continue

        pdf_path = find_master_pdf(test_code)
        if not pdf_path:
            print(f"  {test_code}: NO MASTER PDF FOUND")
            continue

        article = extract_q11_article(pdf_path)
        if article:
            # Get the article title (first line)
            title = article.split("\n")[0] if article else "?"
            print(f"  {test_code}: Extracted ({len(article)} chars) - {title}")
            results[test_code] = article
        else:
            print(f"  {test_code}: FAILED TO EXTRACT")

    # Update cache
    updated = 0
    for test_code, article in results.items():
        if test_code in cache:
            cache[test_code]["q11_article"] = article
            updated += 1

    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nUpdated {updated} tests in cache")


if __name__ == "__main__":
    main()
