"""
Build V2 prompts: Revised Q1-Q10 rules + Original Q11 rules.

For G3-G5: Hybrid — revised prompt framework (Sections 1-5 Q1-Q10, Section 4 gates,
           comma splice protocol) with original Q11 conceptual mastery, scoring, and feedback.
For G6-G8: Original prompt directly (Q11-only tests).
"""

import re
import sys
from pathlib import Path
from docx import Document

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BAK_PATH = ROOT / "Copy of Writing AlphaTests Prompts.docx.bak"
REVISED_DIR = ROOT / "Revised CJ Prompts"
V2_DIR = ROOT / "Revised Prompts V2"

ALL_TESTS = (
    [f"G3.{i}" for i in range(1, 11)]
    + [f"G4.{i}" for i in range(1, 8)]
    + [f"G5.{i}" for i in range(1, 5)]
    + [f"G6.{i}" for i in range(1, 6)]
    + [f"G7.{i}" for i in range(1, 6)]
    + [f"G8.{i}" for i in range(1, 5)]
)

SEP = "════════════════════════════════════════════════════════"


def extract_original(test_code: str) -> str:
    """Extract original prompt from backup DOCX."""
    doc = Document(str(BAK_PATH))
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
                and text.startswith("G")
                and "." in text
                and text != target
            ):
                break
            lines.append(para.text)
    return "\n".join(lines)


def load_revised(test_code: str) -> str:
    """Load revised prompt from text file."""
    path = REVISED_DIR / f"{test_code} CJ Revised.txt"
    return path.read_text(encoding="utf-8")


def get_grade(test_code: str) -> int:
    return int(test_code.split(".")[0][1:])


# ---------------------------------------------------------------------------
# Original prompt Q11 extraction
# ---------------------------------------------------------------------------

def extract_orig_q11_benchmarks(orig: str) -> str:
    """Extract Q11 benchmark cues from original prompt."""
    lines = orig.split("\n")
    for i, line in enumerate(lines):
        if re.search(r"Q11\s*\(", line) and "Paragraph" in line:
            # Make sure this isn't inside scoring logic
            context = "\n".join(lines[max(0, i - 5) : i])
            if "SCORING" in context.upper():
                continue
            end = i + 1
            for j in range(i + 1, min(i + 6, len(lines))):
                stripped = lines[j].strip()
                if not stripped or stripped.startswith("🧠") or "CONCEPTUAL" in stripped.upper():
                    end = j
                    break
                end = j + 1
            return "\n".join(lines[i:end]).strip()
    return ""


def extract_orig_q11_conceptual(orig: str) -> str:
    """Extract Conceptual Mastery Priority section from original prompt."""
    lines = orig.split("\n")
    start = None
    for i, line in enumerate(lines):
        if "CONCEPTUAL MASTERY" in line.upper() or (
            line.strip().startswith("🧠") and "Q11" in line
        ):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if any(
            marker in stripped.upper()
            for marker in ["SCORING LOGIC", "VISIBLE PHASE", "FEEDBACK OUTPUT"]
        ) or stripped.startswith("🔹 SCORING"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def extract_orig_q11_scoring(orig: str) -> str:
    """Extract Q11 scoring logic from original prompt."""
    lines = orig.split("\n")
    in_scoring = False
    start = None
    for i, line in enumerate(lines):
        if "SCORING LOGIC" in line.upper() or "🔹 SCORING" in line.upper():
            in_scoring = True
            continue
        if in_scoring and re.search(r"Q11\s*\(", line):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if any(
            marker in stripped.upper()
            for marker in [
                "VISIBLE PHASE",
                "FEEDBACK OUTPUT",
                "ADDITIONAL INTERNAL",
            ]
        ) or stripped.startswith("🔹 VISIBLE") or stripped.startswith("🔹 ADDITIONAL"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def extract_orig_q11_feedback(orig: str) -> str:
    """Extract Q11 feedback rules from original prompt."""
    lines = orig.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.search(r"Q11\s", line) and ("Feedback" in line or "sentence" in line.lower()):
            # Look for Q11 feedback section (e.g., "Q11 (3-5 sentences)" or "Q11 Feedback")
            start = i
            break
    if start is None:
        # Try alternate pattern
        for i, line in enumerate(lines):
            if re.search(r"Q11\s*\(", line) and any(
                w in line.lower() for w in ["sentence", "paragraph", "feedback"]
            ):
                # Make sure this is in the feedback section, not benchmark/scoring
                context = "\n".join(lines[max(0, i - 10) : i])
                if "VISIBLE" in context.upper() or "FEEDBACK" in context.upper():
                    start = i
                    break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if any(
            marker in stripped.upper()
            for marker in [
                "ADDITIONAL INTERNAL",
                "TEST-SPECIFIC",
                "EXECUTION",
            ]
        ) or stripped.startswith("🔹 ADDITIONAL") or stripped.startswith("🔹 TEST"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


# ---------------------------------------------------------------------------
# Revised prompt section manipulation
# ---------------------------------------------------------------------------

def find_section_boundaries(text: str) -> dict:
    """Find line indices for each SECTION in the revised prompt.

    Returns {section_num: (header_sep_start, content_end)}
    where header_sep_start is the ════ line BEFORE the SECTION header,
    and content_end is the ════ line BEFORE the next section header.
    """
    lines = text.split("\n")
    sections = {}
    section_header_lines = []

    for i, line in enumerate(lines):
        m = re.match(r"SECTION\s+(\d+):", line.strip())
        if m:
            section_header_lines.append((int(m.group(1)), i))

    for idx, (num, header_idx) in enumerate(section_header_lines):
        # Find the ════ line before this header
        start = header_idx
        for j in range(header_idx - 1, max(0, header_idx - 3), -1):
            if lines[j].strip().startswith("════"):
                start = j
                break

        # Find the end: ════ line before the next section header, or end of text
        if idx + 1 < len(section_header_lines):
            next_header_idx = section_header_lines[idx + 1][1]
            end = next_header_idx
            for j in range(next_header_idx - 1, header_idx, -1):
                if lines[j].strip().startswith("════"):
                    end = j
                    break
        else:
            end = len(lines)

        sections[num] = (start, end)

    return sections


def get_section_content(text: str, section_num: int) -> str:
    """Get the content of a section (between its ════ header and next section)."""
    boundaries = find_section_boundaries(text)
    if section_num not in boundaries:
        return ""
    start, end = boundaries[section_num]
    lines = text.split("\n")
    return "\n".join(lines[start:end])


def replace_section_content(text: str, section_num: int, new_content: str) -> str:
    """Replace an entire section with new content."""
    boundaries = find_section_boundaries(text)
    if section_num not in boundaries:
        return text
    start, end = boundaries[section_num]
    lines = text.split("\n")
    return "\n".join(lines[:start] + new_content.split("\n") + lines[end:])


def remove_section(text: str, section_num: int) -> str:
    """Remove an entire section."""
    boundaries = find_section_boundaries(text)
    if section_num not in boundaries:
        return text
    start, end = boundaries[section_num]
    lines = text.split("\n")
    # Remove blank lines between sections
    result_lines = lines[:start] + lines[end:]
    return "\n".join(result_lines)


def replace_q11_in_mixed_section(text: str, section_num: int, q11_marker_pattern: str, new_q11: str) -> str:
    """Replace only the Q11 portion within a section that has Q1-Q10 and Q11 parts."""
    boundaries = find_section_boundaries(text)
    if section_num not in boundaries:
        return text
    sec_start, sec_end = boundaries[section_num]
    lines = text.split("\n")
    section_lines = lines[sec_start:sec_end]

    q11_offset = None
    for i, line in enumerate(section_lines):
        if re.search(q11_marker_pattern, line):
            q11_offset = i
            break

    if q11_offset is None:
        return text

    # Keep everything before Q11, replace from Q11 onward
    new_section_lines = section_lines[:q11_offset] + new_q11.split("\n") + [""]
    return "\n".join(lines[:sec_start] + new_section_lines + lines[sec_end:])


# ---------------------------------------------------------------------------
# V2 builders
# ---------------------------------------------------------------------------

def build_v2_g3_to_g5(test_code: str, revised: str, original: str) -> str:
    """Build V2 hybrid for G3-G5: revised Q1-Q10 + original Q11."""

    # Extract Q11 parts from original
    orig_benchmarks = extract_orig_q11_benchmarks(original)
    orig_conceptual = extract_orig_q11_conceptual(original)
    orig_scoring = extract_orig_q11_scoring(original)
    orig_feedback = extract_orig_q11_feedback(original)

    result = revised

    # 1. Replace Section 6 (Evidence Rules) with original's Conceptual Mastery
    new_section_6 = f"""{SEP}
SECTION 6: Q11 CONCEPTUAL MASTERY PRIORITY
{SEP}

{orig_conceptual}
"""
    result = replace_section_content(result, 6, new_section_6)

    # 2. Remove Section 8 (Calibration Anchors)
    result = remove_section(result, 8)

    # 3. Replace Q11 scoring in Section 7
    if orig_scoring:
        result = replace_q11_in_mixed_section(
            result, 7, r"Q11\s*\(", orig_scoring
        )

    # 4. Replace Q11 feedback in Section 10
    if orig_feedback:
        result = replace_q11_in_mixed_section(
            result, 10, r"Q11\s*\(", orig_feedback
        )

    # 5. Update header
    result = result.replace(
        "Version: 2.0 (with all 8 accuracy improvements)",
        "Version: V2 (Revised Q1-Q10 + Original Q11)",
    )
    # Also update the first line title
    result = result.replace(" CJ — REVISED PROMPT", " CJ — V2 PROMPT")

    return result


def build_v2_g6_to_g8(test_code: str, original: str) -> str:
    """Build V2 for G6-G8: use original prompt (Q11-only tests)."""
    grade = get_grade(test_code)
    version = test_code.split(".")[1]

    header = f"""{test_code} CJ — V2 PROMPT
Test: Instructions
Version: V2 (Original Q11 grading)
========================================================

"""
    return header + original


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    V2_DIR.mkdir(exist_ok=True)

    success = 0
    errors = []

    for test_code in ALL_TESTS:
        grade = get_grade(test_code)
        revised_path = REVISED_DIR / f"{test_code} CJ Revised.txt"

        if not revised_path.exists():
            errors.append(f"{test_code}: No revised prompt found")
            continue

        revised = load_revised(test_code)
        original = extract_original(test_code)

        if not original.strip():
            errors.append(f"{test_code}: No original prompt found in .bak")
            continue

        if grade <= 5:
            v2 = build_v2_g3_to_g5(test_code, revised, original)
        else:
            v2 = build_v2_g6_to_g8(test_code, original)

        out_path = V2_DIR / f"{test_code} CJ V2.txt"
        out_path.write_text(v2, encoding="utf-8")
        success += 1
        print(f"  ✓ {test_code}")

    print(f"\nDone: {success}/{len(ALL_TESTS)} V2 prompts created")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")


if __name__ == "__main__":
    main()
