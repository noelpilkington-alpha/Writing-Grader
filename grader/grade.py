"""
Writing Test AI Grader — v2

Grades student PDFs using CJ prompts via Claude (Anthropic API or AWS Bedrock).
Supports A/B comparison mode: original (DOCX) vs revised (text files).

Usage:
  python grader/grade.py "Tests to Grade/Student G3.1.pdf"
  python grader/grade.py "Tests to Grade/Student G3.1.pdf" --prompt revised
  python grader/grade.py "Tests to Grade/Student G3.1.pdf" --prompt both
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")

import anthropic
import fitz  # PyMuPDF
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = ROOT / "Copy of Writing AlphaTests Prompts.docx"
REVISED_DIR = ROOT / "Revised CJ Prompts"
RESULTS_DIR = ROOT / "grader" / "results"
CACHE_PATH = ROOT / "grader" / "test_content_cache.json"

# Default models per provider
DEFAULT_MODELS = {
    "bedrock": "us.anthropic.claude-sonnet-4-6",
    "anthropic": "claude-sonnet-4-6-20250514",
}


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def create_client():
    """Create the appropriate Anthropic client (direct API or Bedrock)."""
    provider = os.environ.get("ANTHROPIC_PROVIDER", "bedrock").strip().lower()

    if provider == "bedrock":
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).strip()
        return anthropic.AnthropicBedrock(aws_region=region)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set. Set it in .env or environment.")
        return anthropic.Anthropic(api_key=api_key)


def get_default_model() -> str:
    """Get the default model ID for the configured provider."""
    provider = os.environ.get("ANTHROPIC_PROVIDER", "bedrock").strip().lower()
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["bedrock"])


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------
def extract_prompt_from_docx(test_code: str) -> str:
    """Extract a CJ prompt from the master DOCX."""
    doc = Document(str(DOCX_PATH))
    target = f"{test_code} CJ"
    capture = False
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text == target:
            capture = True
            continue
        if capture:
            if (
                text.endswith(" CJ")
                and text[0] == "G"
                and "." in text
                and text != target
            ):
                break
            lines.append(para.text)
    return "\n".join(lines)


def load_revised_prompt(test_code: str) -> Optional[str]:
    """Load a revised prompt from the Revised CJ Prompts folder."""
    path = REVISED_DIR / f"{test_code} CJ Revised.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def load_q11_article(test_code: str) -> Optional[str]:
    """Load the Q11 article from the test content cache.

    For G3-G5 tests, Q11 references a separate article from the Q1-Q10
    passage. This function returns that article text so it can be included
    when grading Q11. Returns None for G6+ or if no article is cached.
    """
    grade_num = int(test_code.split(".")[0][1:])
    if grade_num >= 6:
        return None
    if not CACHE_PATH.exists():
        return None
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    entry = cache.get(test_code, {})
    return entry.get("q11_article")


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------
def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a student PDF using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def detect_test_version(text: str) -> str:
    m = re.search(r"Alpha Standardized Writing (G[3-8]\.\d+)", text)
    if not m:
        raise ValueError("Could not detect test version in PDF.")
    return m.group(1)


def detect_student_name(text: str) -> str:
    m = re.search(r"Student Name:\s*(.+?)(?:\n|$)", text)
    if m:
        name = m.group(1).strip()
        # Edulastic format: "Last, First"
        if "," in name:
            parts = name.split(",", 1)
            return f"{parts[1].strip()} {parts[0].strip()}"
        return name
    return "Unknown"


def extract_passage_and_questions(pdf_path: Path) -> dict:
    """
    Extract passage, questions, and responses from the raw PDF text.

    Strategy: Use "N Words" markers as anchors. Each question block ends with
    a Words marker. Walk backwards from each marker to find the question number
    and content.

    Returns: {"passage": str, "questions": {qnum: {"question": str, "response": str}}}
    """
    doc = fitz.open(str(pdf_path))
    all_lines = []
    for page in doc:
        text = page.get_text()
        for line in text.split("\n"):
            all_lines.append(line.strip())
    doc.close()

    # Filter heavy noise but keep ALL content lines (including standalone numbers)
    filtered = []
    for line in all_lines:
        if not line:
            continue
        if line.startswith("http"):
            continue
        if "Pear Assessment" in line:
            continue
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2}", line):
            continue
        # Keep page indicators like "2/7" but skip date-formatted ones (already handled)
        filtered.append(line)

    # Find all "N Words" markers (anchors)
    words_indices = []
    for i, line in enumerate(filtered):
        if re.match(r"^\d+\s+Words?$", line, re.IGNORECASE) or line == "0 Words":
            words_indices.append(i)

    if not words_indices:
        return {"passage": "", "questions": {}}

    # For each Words marker, look backwards to find the question number.
    # The question block is: [qnum_line, ..., content_lines, ..., response, Words_marker]
    # Between consecutive Words markers there may also be score/time/meta lines.
    question_blocks = []  # (qnum, content_start, content_end_exclusive)

    for wi_idx, wi in enumerate(words_indices):
        # Look backward from the Words marker to find a standalone question number
        # The question number is a standalone line "1" through "11" that appears
        # BEFORE the question text and response.
        # Stop looking at the previous Words marker (or start of file).
        search_start = words_indices[wi_idx - 1] + 1 if wi_idx > 0 else 0

        qnum = None
        qnum_line_idx = None

        for j in range(wi - 1, search_start - 1, -1):
            line = filtered[j]
            # Skip known meta/noise
            if re.match(r"^\d+(\.\d+)?s$", line):  # timing
                continue
            if re.match(r"^\d+/\d+$", line):  # page like "2/7"
                continue
            if any(w in line for w in [
                "What Strong Writing", "Ideas &", "Writing Conventions",
                "Area", "Score",
            ]):
                continue

            # Check if this is a standalone question number (1-11)
            m = re.match(r"^(1[01]?|[2-9])$", line)
            if m:
                candidate = int(m.group(1))
                if 1 <= candidate <= 11:
                    # Verify: the line AFTER this should be question text (not another number)
                    if j + 1 < wi:
                        next_line = filtered[j + 1]
                        # If next line is also a short number or timing, this is probably
                        # a score, not a question number. Question text is usually longer.
                        if len(next_line) > 5 or re.match(r"^[A-Z]", next_line):
                            qnum = candidate
                            qnum_line_idx = j
                            break
                    else:
                        qnum = candidate
                        qnum_line_idx = j
                        break

        if qnum is not None and qnum_line_idx is not None:
            # Content is from qnum_line+1 to Words marker (exclusive)
            question_blocks.append((qnum, qnum_line_idx + 1, wi))

    # Deduplicate (keep first occurrence of each qnum)
    seen = set()
    unique_blocks = []
    for qnum, start, end in question_blocks:
        if qnum not in seen:
            seen.add(qnum)
            unique_blocks.append((qnum, start, end))
    question_blocks = unique_blocks

    # Extract passage: use the full PDF text before the first question
    passage = ""
    if question_blocks:
        # The first question number line
        first_q_line = question_blocks[0][1] - 1  # -1 to get the qnum line itself
        passage_lines = []
        for i in range(first_q_line):
            line = filtered[i]
            # Skip headers, rubric, metadata
            if any(w in line for w in [
                "Score", "What Strong Writing", "Ideas &", "Writing",
                "Conventions", "point", "Test Name:", "Student Name:",
                "Class Name:", "Due:", "Status:", "Submitted", "TOTAL SCORE",
                "Instructions", "Q1-5:", "Q6-10:", "Area", "Edulastic",
                "Read the selection and answer",
            ]):
                continue
            if re.match(r"^\d+(\.\d+)?s$", line):
                continue
            if re.match(r"^\d+\s+Words?$", line, re.IGNORECASE) or line == "0 Words":
                continue
            if re.match(r"^\d+$", line) and len(line) <= 2:
                continue
            if re.match(r"^\d+/\d+$", line):
                continue
            if len(line) > 10:
                passage_lines.append(line)
        passage = "\n".join(passage_lines)

    # Extract questions and responses from blocks
    questions = {}
    for qnum, start, end in question_blocks:
        block = []
        for i in range(start, end):
            line = filtered[i]
            # Skip timing and score metadata that leaked into the block
            if re.match(r"^\d+(\.\d+)?s$", line):
                continue
            if re.match(r"^\d+/\d+$", line):
                continue
            # Skip standalone small numbers (scores: 0, 1, 2, 3)
            if re.match(r"^[0-3]$", line):
                continue
            block.append(line)

        if not block:
            continue

        if qnum == 11:
            # For Q11: split at "Write your paragraph/response/essay"
            split_idx = 0
            for k, bl in enumerate(block):
                if re.search(
                    r"(?:Write your|write your).{0,30}(?:paragraph|response|essay|box)",
                    bl, re.IGNORECASE,
                ):
                    split_idx = k + 1
            question_text = "\n".join(block[:split_idx]).strip()
            response_text = "\n".join(block[split_idx:]).strip()
        else:
            # For Q1-Q10: everything except the last line is question, last line is response
            if len(block) >= 2:
                question_text = "\n".join(block[:-1]).strip()
                response_text = block[-1].strip()
            elif len(block) == 1:
                question_text = ""
                response_text = block[0].strip()
            else:
                question_text = ""
                response_text = ""

        questions[qnum] = {
            "question": question_text,
            "response": response_text,
        }

    return {"passage": passage, "questions": questions}


# ---------------------------------------------------------------------------
# API calling
# ---------------------------------------------------------------------------
def build_grading_prompt(
    rubric: str, passage: str, question: str, response: str, qnum: int, max_score: int
) -> str:
    """Build the full prompt to send to the API."""
    # Replace template variables in rubric
    filled = rubric
    filled = filled.replace("{{passage}}", passage or "(no passage)")
    filled = filled.replace("{{question}}", question or "(no question)")
    filled = filled.replace("{{response}}", response or "(no response)")

    return filled


def _sub_maxes(qnum: int):
    """Return (ideas_max, conventions_max) for a given question number."""
    if qnum <= 5:
        return (1, 1)      # Q1-Q5: 1 Ideas + 1 Conventions = 2
    if qnum <= 10:
        return (2, 1)      # Q6-Q10: 2 Ideas + 1 Conventions = 3
    return (15, 5)          # Q11: 15 Ideas + 5 Conventions = 20


def call_anthropic(
    client,
    model: str,
    rubric: str,
    passage: str,
    question: str,
    response: str,
    qnum: int,
    max_score: int,
) -> Dict:
    """Send a grading request to the Anthropic API and parse structured output."""
    prompt = build_grading_prompt(rubric, passage, question, response, qnum, max_score)

    system = (
        "You are a grading assistant. Follow the rubric exactly. "
        "Your entire response must be a single valid JSON object — no preamble, "
        "no commentary, no markdown fences, no reasoning walkthrough before the JSON. "
        "Do all reasoning internally, then output ONLY the JSON.\n"
        "Required keys:\n"
        '  "question": integer (question number),\n'
        '  "ideas_score": integer,\n'
        '  "ideas_max": integer,\n'
        '  "conventions_score": integer,\n'
        '  "conventions_max": integer,\n'
        '  "total_score": integer,\n'
        '  "total_max": integer,\n'
        '  "feedback": string (student-facing feedback following the rubric output rules),\n'
        '  "internal_notes": string (brief internal reasoning)\n'
    )

    # Q11 essays need more tokens for the longer feedback and reasoning
    tokens = 2048 if qnum == 11 else 1024

    user_msg = f"Grade question {qnum} (max {max_score} points).\n\n{prompt}"

    data = None
    for attempt in range(2):
        msg = client.messages.create(
            model=model,
            max_tokens=tokens,
            temperature=0.2,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = msg.content[0].text

        # Parse JSON from response
        try:
            data = json.loads(content)
            break
        except json.JSONDecodeError:
            # Try to extract JSON block from surrounding text
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                    break
                except json.JSONDecodeError:
                    pass

        # First attempt failed — retry with explicit reminder
        if attempt == 0:
            user_msg = (
                "Your previous response was not valid JSON. "
                "Respond with ONLY a JSON object, starting with { and ending with }. "
                "No other text.\n\n" + user_msg
            )
            time.sleep(0.5)

    if data is None:
        data = {
            "question": qnum,
            "ideas_score": 0, "ideas_max": 0,
            "conventions_score": 0, "conventions_max": 0,
            "total_score": 0, "total_max": max_score,
            "feedback": content[:500],
            "internal_notes": "JSON parse failed",
        }

    # Ensure required keys
    data.setdefault("question", qnum)
    data.setdefault("total_max", max_score)
    data.setdefault("total_score", data.get("ideas_score", 0) + data.get("conventions_score", 0))

    # Clamp scores to known maximums — prevents prompts from exceeding stated caps
    ideas_max, conv_max = _sub_maxes(qnum)
    if "ideas_score" in data:
        data["ideas_score"] = min(data["ideas_score"], ideas_max)
        data["ideas_max"] = ideas_max
    if "conventions_score" in data:
        data["conventions_score"] = min(data["conventions_score"], conv_max)
        data["conventions_max"] = conv_max
    data["total_score"] = min(
        data.get("ideas_score", 0) + data.get("conventions_score", 0),
        max_score,
    )
    data["total_max"] = max_score

    return data


def infer_max_score(test_version: str, qnum: int) -> int:
    if qnum == 11:
        return 20
    if qnum <= 5:
        return 2
    if qnum <= 10:
        return 3
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def grade_pdf(
    pdf_path: Path,
    client,
    model: str,
    prompt_mode: str = "both",
) -> Dict:
    """Grade a single PDF and return results."""
    pdf_text = extract_pdf_text(pdf_path)
    test_version = detect_test_version(pdf_text)
    student_name = detect_student_name(pdf_text)

    extracted = extract_passage_and_questions(pdf_path)
    passage = extracted["passage"]
    questions = extracted["questions"]

    # Load prompts
    original_prompt = extract_prompt_from_docx(test_version)
    revised_prompt = load_revised_prompt(test_version)

    if not original_prompt:
        raise ValueError(f"No original prompt found for {test_version}")

    grade = int(test_version.split(".")[0][1:])
    essay_only = grade >= 6

    # For G3-G5 tests, Q11 uses a separate article from the Q1-Q10 passage.
    # Load it from the cache so the grader has the full context.
    q11_article = load_q11_article(test_version)

    results = {
        "student": student_name,
        "test": test_version,
        "pdf": pdf_path.name,
        "questions": {},
    }

    for qnum in sorted(questions.keys()):
        if essay_only and qnum != 11:
            continue

        q = questions[qnum]
        max_score = infer_max_score(test_version, qnum)

        # For Q11 on G3-G5 tests, use the Q11 article instead of the
        # Q1-Q10 passage so the grader can verify text-based evidence.
        grading_passage = passage
        if qnum == 11 and q11_article:
            grading_passage = (
                passage + "\n\nQ11 ARTICLE:\n" + q11_article
            )

        q_result = {"question": q["question"][:200], "response": q["response"][:500]}

        # Grade with original prompt
        if prompt_mode in ("original", "both"):
            try:
                orig_result = call_anthropic(
                    client, model, original_prompt,
                    grading_passage, q["question"], q["response"],
                    qnum, max_score,
                )
                q_result["original"] = orig_result
            except Exception as e:
                q_result["original"] = {"error": str(e)}
            time.sleep(0.5)  # Rate limiting

        # Grade with revised prompt
        if prompt_mode in ("revised", "both") and revised_prompt:
            try:
                rev_result = call_anthropic(
                    client, model, revised_prompt,
                    grading_passage, q["question"], q["response"],
                    qnum, max_score,
                )
                q_result["revised"] = rev_result
            except Exception as e:
                q_result["revised"] = {"error": str(e)}
            time.sleep(0.5)

        results["questions"][str(qnum)] = q_result

    return results


def format_report(results: Dict, prompt_mode: str) -> str:
    """Format results as a human-readable report."""
    lines = []
    lines.append(f"Student: {results['student']}")
    lines.append(f"Test: {results['test']}")
    lines.append(f"PDF: {results['pdf']}")
    lines.append("")

    orig_total = 0
    rev_total = 0
    max_total = 0

    for qnum_str in sorted(results["questions"].keys(), key=int):
        qnum = int(qnum_str)
        q = results["questions"][qnum_str]
        max_score = infer_max_score(results["test"], qnum)
        max_total += max_score

        line = f"Q{qnum} ({max_score}pts): "
        parts = []

        if "original" in q and "error" not in q["original"]:
            o = q["original"]
            score = o.get("total_score", 0)
            orig_total += score
            parts.append(f"Original={score}/{max_score}")
            if "ideas_score" in o:
                parts[-1] += f" (I:{o['ideas_score']}/{o.get('ideas_max','')} C:{o.get('conventions_score','')}/{o.get('conventions_max','')})"

        if "revised" in q and "error" not in q["revised"]:
            r = q["revised"]
            score = r.get("total_score", 0)
            rev_total += score
            parts.append(f"Revised={score}/{max_score}")
            if "ideas_score" in r:
                parts[-1] += f" (I:{r['ideas_score']}/{r.get('ideas_max','')} C:{r.get('conventions_score','')}/{r.get('conventions_max','')})"

        # Check divergence
        if "original" in q and "revised" in q:
            o_score = q.get("original", {}).get("total_score", -1)
            r_score = q.get("revised", {}).get("total_score", -1)
            if o_score != r_score and o_score >= 0 and r_score >= 0:
                parts.append(f"*** DIVERGENCE ({o_score} vs {r_score}) ***")

        line += " | ".join(parts)
        lines.append(line)

    lines.append("")
    if prompt_mode in ("original", "both"):
        lines.append(f"ORIGINAL TOTAL: {orig_total}/{max_total}")
    if prompt_mode in ("revised", "both"):
        lines.append(f"REVISED TOTAL:  {rev_total}/{max_total}")

    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Grade a student writing test PDF")
    parser.add_argument("pdf", help="Path to the student PDF")
    parser.add_argument(
        "--prompt", choices=["original", "revised", "both"], default="both",
        help="Which prompt to use (default: both)"
    )
    parser.add_argument(
        "--model", default=None,
        help="Model ID (default: from env or auto-detected per provider)"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results JSON to grader/results/"
    )

    args = parser.parse_args()

    # Load environment
    load_env(ROOT / ".env")
    load_env(ROOT / "grader" / ".env")

    model = args.model or os.environ.get("ANTHROPIC_MODEL", "").strip() or get_default_model()

    try:
        client = create_client()
    except ValueError as e:
        print(str(e))
        return 1

    pdf_path = Path(args.pdf)
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1

    print(f"Grading: {pdf_path.name}")
    print(f"Model: {model}")
    print(f"Prompt mode: {args.prompt}")
    print()

    results = grade_pdf(pdf_path, client, model, args.prompt)

    # Print report
    print(format_report(results, args.prompt))

    # Save JSON
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stem = pdf_path.stem.replace(" ", "_")
        out_path = RESULTS_DIR / f"{stem}_{args.prompt}.json"
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nResults saved to: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
