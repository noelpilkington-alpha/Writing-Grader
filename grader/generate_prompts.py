"""
Generate revised CJ prompts for all test codes that have student PDFs
in the 'Tests for prompt testing' folder.

Uses a template approach:
1. Extract the original prompt from the DOCX
2. Extract passage/question info from blank test PDFs
3. Apply the standardized 12-section template with all 8 improvements
4. Save to 'Revised CJ Prompts/'
"""

import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Optional: use fitz for blank-test PDF extraction
try:
    import fitz
except ImportError:
    fitz = None

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = ROOT / "Copy of Writing AlphaTests Prompts.docx"
REVISED_DIR = ROOT / "Revised CJ Prompts"
BLANK_TESTS = {
    "G3": ROOT / "G3",
    "G4": ROOT / "G4",
    "G5": ROOT / "G5",
    "G6": ROOT / "G6",
    "G7": ROOT / "G7",
    "G8": ROOT / "G8",
}


# ---------------------------------------------------------------------------
# Grade-level configuration
# ---------------------------------------------------------------------------
GRADE_CONFIG = {
    3: {
        "tone": "kind but careful",
        "grade_word": "Grade 3",
        "q_range": "Q1-Q11",
        "essay_only": False,
        "tol_q1_q10": 2,
        "tol_q11": 3,
        "tol_label": "≤ 2 minor errors (Q1-Q10), ≤ 3 (Q11)",
    },
    4: {
        "tone": "strict but friendly",
        "grade_word": "Grade 4",
        "q_range": "Q1-Q11",
        "essay_only": False,
        "tol_q1_q10": 1,
        "tol_q11": 2,
        "tol_label": "≤ 1 minor error (Q1-Q10), ≤ 2 (Q11)",
    },
    5: {
        "tone": "strict but friendly",
        "grade_word": "Grade 5",
        "q_range": "Q1-Q11",
        "essay_only": False,
        "tol_q1_q10": 1,
        "tol_q11": 2,
        "tol_label": "≤ 1 minor error (Q1-Q10), ≤ 2 (Q11)",
    },
    6: {
        "tone": "encouraging and analytical",
        "grade_word": "Grade 6",
        "q_range": "Q11 only",
        "essay_only": True,
        "tol_essay": 2,
        "tol_label": "≤ 2 minor errors for essay",
    },
    7: {
        "tone": "strict but encouraging",
        "grade_word": "Grade 7",
        "q_range": "Q11 only",
        "essay_only": True,
        "tol_essay": 2,
        "tol_label": "≤ 2 minor errors for essay",
        "rubric_type": "5-category",
    },
    8: {
        "tone": "strict but encouraging",
        "grade_word": "Grade 8",
        "q_range": "Q11 only",
        "essay_only": True,
        "tol_essay": 2,
        "tol_label": "≤ 2 minor errors for essay",
        "rubric_type": "5-category",
    },
}


def extract_prompt_from_docx(test_code: str) -> str:
    """Extract a single CJ prompt section from the master DOCX."""
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


def extract_blank_test_info(test_code: str) -> dict:
    """Extract passage topic and Q11 prompt from the blank test PDF."""
    grade_folder = test_code.split(".")[0]  # e.g. "G3"
    folder = BLANK_TESTS.get(grade_folder)
    if not folder:
        return {"passage_topic": "", "q11_prompt": "", "passage_titles": ""}

    pdf_name = f"Alpha Standardized Writing {test_code}.pdf"
    pdf_path = folder / pdf_name
    if not pdf_path.exists() or fitz is None:
        return {"passage_topic": "", "q11_prompt": "", "passage_titles": ""}

    doc = fitz.open(str(pdf_path))
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    # Try to extract Q11 prompt
    q11_prompt = ""
    m = re.search(r"(?:Prompt|11)\s*\n(.*?)(?:Write your|Make sure)", full_text, re.S)
    if m:
        q11_prompt = m.group(1).strip()

    # Try to extract passage titles
    titles = []
    for m in re.finditer(r"(?:Read the selection[.\s]*)\n(.+?)(?:\n|$)", full_text):
        title = m.group(1).strip()
        if title and len(title) < 100:
            titles.append(title)

    return {
        "passage_topic": " / ".join(titles) if titles else "",
        "q11_prompt": q11_prompt,
        "passage_titles": " / ".join(titles) if titles else "",
    }


def extract_test_specific_section(original_prompt: str, test_code: str) -> str:
    """Extract test-specific details (Q1-Q11 skill references) from original."""
    lines = original_prompt.split("\n")
    test_lines = []
    capture = False
    for line in lines:
        stripped = line.strip()
        # Look for per-question references
        if re.match(r"Q\d+\s*[–—-]", stripped) or "target" in stripped.lower():
            capture = True
        if capture:
            test_lines.append(line)
            if stripped == "" and len(test_lines) > 2:
                # Check if we've moved past the question references
                if not any(
                    re.match(r"Q\d+", l.strip()) for l in test_lines[-3:]
                ):
                    break

    # Also extract any passage/topic references
    for line in lines:
        stripped = line.strip()
        if "passage" in stripped.lower() and (
            "read" in stripped.lower() or "selection" in stripped.lower()
        ):
            test_lines.append(line)
        if "standards" in stripped.lower() or "CCSS" in stripped or "TEKS" in stripped:
            test_lines.append(line)

    return "\n".join(test_lines)


def detect_q11_type(original_prompt: str, grade: int) -> str:
    """Detect the Q11 essay type from the original prompt."""
    lower = original_prompt.lower()
    if grade >= 6:
        if "expository" in lower:
            return "expository_essay"
        if "argumentative" in lower or "persuasive" in lower:
            return "argumentative_essay"
        if "narrative" in lower:
            return "narrative_essay"
        return "essay"
    if "paragraph" in lower:
        if "opinion" in lower:
            return "opinion_paragraph"
        if "explain" in lower or "expository" in lower:
            return "explanatory_paragraph"
        if "narrative" in lower or "story" in lower or "retell" in lower:
            return "narrative_paragraph"
        return "paragraph"
    return "paragraph"


def build_revised_prompt(test_code: str) -> str:
    """Build a complete revised prompt for a given test code."""
    grade = int(test_code.split(".")[0][1:])
    config = GRADE_CONFIG[grade]
    original = extract_prompt_from_docx(test_code)
    blank_info = extract_blank_test_info(test_code)
    q11_type = detect_q11_type(original, grade)

    # Extract per-question skill references from original
    test_specific = extract_test_specific_section(original, test_code)

    # Build the 12-section template
    sections = []

    # Header
    topic = blank_info["passage_titles"] or "(see original prompt)"
    sections.append(
        f"{test_code} CJ — REVISED PROMPT\n"
        f"Test: {topic}\n"
        f"Version: 2.0 (with all 8 accuracy improvements)\n"
        f"========================================================"
    )

    # Section 1: Global Grading Principles
    sections.append(
        f"\nYou are a {config['tone']} {config['grade_word']} writing grader.\n"
        f"Evaluate responses in four invisible phases — CHECKLIST → COMPARATIVE INTERPRETATION → SCORE → SELF-CHECK → FEEDBACK — and output only FEEDBACK to the student.\n"
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 1: GLOBAL GRADING PRINCIPLES (NON-NEGOTIABLE)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nAll grading decisions must follow task intent first.\n"
        f"Never import expectations from a different question type.\n"
        f"If a response meets the goal of its specific task, it is correct even if it could be expanded in another context."
    )

    # Section 2: CJ Principle
    if grade <= 5:
        anchors = (
            f"Beginning: incomplete, confusing, or off-target.\n"
            f"Developing: idea is present but weak support, thin development, or notable errors.\n"
            f"Proficient: clear, accurate, and fulfills the goal with control of meaning and conventions.\n"
            f"Advanced: precise, fluent, and stylistically strong; exceeds expectations."
        )
    else:
        anchors = (
            f"Beginning: unclear thesis or disorganized ideas; few connections between evidence and main point.\n"
            f"Developing: thesis present but support is thin or loosely connected; some structural issues.\n"
            f"Proficient: clear thesis and logical structure; distinct paragraphs supported by textual evidence; appropriate transitions.\n"
            f"Advanced: fluent and confident writing; precise evidence integration; smooth transitions; strong reasoning."
        )

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 2: COMPARATIVE JUDGEMENT PRINCIPLE (dominant)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nBefore scoring, internally compare ⟦{{{{response}}}}⟧ to {config['grade_word']} anchors:\n"
        f"\n{anchors}\n"
        f"\nAsk in every phase:\n"
        f'  "Does this response read closer to the Proficient example or closer to the Beginning example?"\n'
        f"\nWhen checklist data and CJ conflict, comparative judgement governs.\n"
        f"Base the final decision on overall clarity and quality, not a single error."
    )

    # Section 3: Literal Checklist
    checklist_fields = (
        '  "starts_with_capital": true/false,\n'
        '  "ends_with_terminal": true/false,\n'
        '  "sentence_count_estimate": integer,\n'
        '  "contains_because": true/false,\n'
        '  "contains_but": true/false,\n'
        '  "contains_so": true/false,\n'
        '  "contains_since": true/false,\n'
        '  "contains_and": true/false,\n'
        '  "appositive_present": true/false,\n'
        '  "is_question": true/false,\n'
        '  "looks_like_fragment": true/false,\n'
        '  "run_on_likely": true/false,\n'
        '  "minor_surface_errors": integer,\n'
        '  "major_error_gate": true/false,\n'
        '  "mechanics_clean": true/false'
    )
    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 3: LITERAL CHECKLIST (internal reference only)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nInspect ⟦{{{{response}}}}⟧ exactly as written (no autocorrect; ignore trailing spaces/line breaks). Record internally (don't output):\n"
        f"{{\n{checklist_fields}\n}}\n"
        f"\nUse these as signals only; CJ determines proficiency."
    )

    # Section 4: Error Tolerance & Gates
    if config.get("essay_only"):
        tol_section = (
            f"✏️ Minor Surface-Error Tolerance\n"
            f"Minor errors do not reduce Conventions if meaning is clear.\n"
            f"Examples (not penalized): one simple spelling slip; missing comma after a short opener; one article/apostrophe miss; a single tense or capitalization inconsistency.\n"
            f"\nTOLERANCE THRESHOLDS:\n"
            f"  Essay: ≤ {config.get('tol_essay', 2)} minor errors = no Conventions deduction\n"
            f"\n🔒 TOLERANCE-CJ INTERACTION RULES (NEW)\n"
            f"When error count is AT the tolerance boundary (tolerance + 1):\n"
            f"  → Apply CJ: If meaning is fully clear and writing is fluent, GRANT conventions credit.\n"
            f"  → This is the \"soft boundary\" zone.\n"
            f"\nWhen error count is BEYOND the boundary (tolerance + 2 or more):\n"
            f"  → DENY conventions credit regardless of CJ.\n"
            f"  → This is the \"hard boundary.\"\n"
            f"\n  Examples ({config['grade_word']}, essay tolerance ≤ {config.get('tol_essay', 2)}):\n"
            f"    {config.get('tol_essay', 2)} errors  → Within tolerance → No deduction\n"
            f"    {config.get('tol_essay', 2) + 1} errors  → Soft boundary → CJ decides\n"
            f"    {config.get('tol_essay', 2) + 2}+ errors → Hard boundary → Deduct"
        )
    else:
        t10 = config["tol_q1_q10"]
        t11 = config["tol_q11"]
        tol_section = (
            f"✏️ Minor Surface-Error Tolerance\n"
            f"Minor errors do not reduce Conventions if meaning is clear.\n"
            f"Examples (not penalized): one simple spelling slip; missing comma after a short opener; one article/apostrophe miss; a single tense or capitalization inconsistency.\n"
            f"\nTOLERANCE THRESHOLDS:\n"
            f"  Q1–Q10: ≤ {t10} minor error{'s' if t10 > 1 else ''} = no Conventions deduction\n"
            f"  Q11:    ≤ {t11} minor errors = no Conventions deduction\n"
            f"\n🔒 TOLERANCE-CJ INTERACTION RULES (NEW)\n"
            f"When error count is AT the tolerance boundary (tolerance + 1):\n"
            f"  → Apply CJ: If meaning is fully clear and writing is fluent, GRANT conventions credit.\n"
            f"  → This is the \"soft boundary\" zone.\n"
            f"\nWhen error count is BEYOND the boundary (tolerance + 2 or more):\n"
            f"  → DENY conventions credit regardless of CJ.\n"
            f"  → This is the \"hard boundary.\"\n"
            f"\n  Examples ({config['grade_word']}, Q1–Q10 tolerance ≤ {t10}):\n"
            f"    {t10} error{'s' if t10 > 1 else ''}  → Within tolerance → Conventions 1/1\n"
            f"    {t10 + 1} errors → Soft boundary → CJ decides (grant if clear)\n"
            f"    {t10 + 2}+ errors → Hard boundary → Conventions 0/1\n"
            f"\n  Examples ({config['grade_word']}, Q11 tolerance ≤ {t11}):\n"
            f"    {t11} errors  → Within tolerance → No deduction\n"
            f"    {t11 + 1} errors  → Soft boundary → CJ decides\n"
            f"    {t11 + 2}+ errors → Hard boundary → Deduct"
        )

    major_error_gate = (
        f"\n🚫 Major Error Gate (soft, meaning-first)\n"
        f"Set major_error_gate = true only if meaning is unclear because of:\n"
        f"  - Missing capital and end punctuation with a confusing sentence, or\n"
        f"  - Obvious fragment (no subject/verb), or\n"
        f"  - True run-on/comma splice that blurs meaning.\n"
        f"Do not count as run-on: a single stray comma before that/which/because; long but grammatical sentences.\n"
        f"If the sentence still reads clearly, treat as Developing rather than automatic failure."
    )

    comma_splice = (
        f"\n🔒 COMMA SPLICE DETECTION PROTOCOL (NON-NEGOTIABLE)\n"
        f'Before classifying ANY comma as a "minor error," verify:\n'
        f"  1. Does the comma separate two subject-verb pairs?\n"
        f"  2. Is there a coordinating conjunction (and, but, so, or) after the comma?\n"
        f"  3. Is there a subordinator (that, because, which, who, when, if) connecting them?\n"
        f"\nIf #1 = YES and both #2 and #3 = NO → COMMA SPLICE (major error, not minor).\n"
        f"\nCommon student patterns that ARE comma splices:\n"
        f'  ❌ "My favorite tradition is, we go to the beach every summer."\n'
        f"     → Missing \"that\" — two clauses joined by comma only\n"
        f'  ❌ "I like dogs, they are friendly and fun."\n'
        f"     → Two independent clauses, no conjunction\n"
        f'  ❌ "She ran fast, she won the race."\n'
        f"     → Two independent clauses, no conjunction\n"
        f"\nThese are NOT comma splices (minor or no error):\n"
        f'  ✅ "My favorite tradition is that we go to the beach every summer."\n'
        f'  ✅ "I like dogs because they are friendly and fun."\n'
        f'  ✅ "She ran fast, and she won the race."\n'
        f'  ✅ "After running fast, she won the race." (participial opener + comma)'
    )

    flow_rule = ""
    if not config.get("essay_only"):
        flow_rule = (
            f"\n\n🛡️ Flow Neutrality Rule — Q6–Q10\n"
            f"If grammar is correct and meaning clear, ignore comments about \"flow/smoothness/wordiness.\"\n"
            f"Style alone does not reduce Ideas or Conventions and should not appear in feedback."
        )

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 4: ERROR TOLERANCE & GATES ({config['grade_word']})\n"
        f"════════════════════════════════════════════════════════\n"
        f"\n{tol_section}"
        f"{major_error_gate}"
        f"{comma_splice}"
        f"{flow_rule}"
    )

    # Section 5: Task-Locked Interpretation Rules
    if config.get("essay_only"):
        # G6-G8: essay only
        task_lock = _build_essay_task_lock(test_code, grade, original, blank_info)
    else:
        # G3-G5: full Q1-Q11
        task_lock = _build_full_task_lock(test_code, grade, original, blank_info)

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 5: TASK-LOCKED INTERPRETATION RULES (CRITICAL)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\n{task_lock}"
    )

    # Section 6: Evidence Rules (Q11)
    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 6: EVIDENCE RULES (Q11 ONLY)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\n🧠 Conceptual Mastery Priority\n"
        f"  1. Concept over length; reward clear organization and accurate links.\n"
        f"  2. Conceptual gap (missing/wrong link) → deduct; elaboration gap (short but accurate) → mention only.\n"
        f"  3. Evidence sufficiency: ≥ 2 accurate, relevant details + brief explanations = full Ideas.\n"
        f"  4. Phrase suggestions as extensions, not corrections.\n"
        f"\n🔒 EVIDENCE AUTHENTICITY CHECK (NEW)\n"
        f"Before crediting text-based details, verify each claimed detail actually appears in or can be directly inferred from the passage.\n"
        f"\n  FABRICATED evidence (detail not in passage):\n"
        f"    → Do NOT count toward the ≥ 2 text-based detail requirement\n"
        f"    → If student has < 2 verified details after removing fabricated ones, deduct (-3)\n"
        f"\n  DISTORTED evidence (loosely based on passage but significantly changed):\n"
        f"    → Count as 0.5 — may satisfy requirement if combined with one fully accurate detail\n"
        f"\n  Note: Students may reasonably INFER unstated consequences. Only flag details that have NO basis in the passage text.\n"
        f"\n🔒 VERBATIM COPYING CHECK (NEW)\n"
        f"If ≥ 50% of the paragraph consists of sentences copied word-for-word or near-word-for-word from the passage:\n"
        f"\n  Ideas impact:\n"
        f'    - Copied sentences DO count as "text-based details" (they are accurate)\n'
        f"    - BUT: No original development = -3 (no synthesis or explanation)\n"
        f"    - AND: List-like structure without connections = -3 (no logical flow)\n"
        f"    - Maximum Ideas deduction for copying: -6 (from 15 → 9)\n"
        f"\n  Conventions impact:\n"
        f"    - Only evaluate conventions on student-original text"
    )

    # Section 7: Scoring Logic
    if config.get("essay_only"):
        scoring = _build_essay_scoring(test_code, grade, config)
    else:
        scoring = _build_full_scoring(test_code, grade, config)

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 7: SCORING LOGIC (internal only; never reveal)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\n{scoring}"
    )

    # Section 8: Calibration Anchors (placeholder — test-specific)
    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 8: CALIBRATION ANCHORS — Q11 (NEW)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nUse these scored examples to calibrate your grading before assigning a score.\n"
        f"\n[CALIBRATION ANCHORS — To be generated from passage content]\n"
        f"Compare the student's Q11 response to these mental benchmarks:\n"
        f"  Beginning (Ideas ~5-6/15): Vague, unfocused, few or no text-based details, no clear main idea.\n"
        f"  Developing (Ideas ~9-10/15): Has a main idea and some details, but thin explanations or missing connections.\n"
        f"  Proficient (Ideas ~12-13/15): Clear main idea, ≥2 text-based details with explanations, logical order.\n"
        f"  Advanced (Ideas ~15/15): Strong thesis, 2+ well-explained details, insightful connections, fluent writing."
    )

    # Section 9: Self-Verification Check
    if config.get("essay_only"):
        checks = (
            f"  □ Did I apply essay-only grading (skip Q1-Q10 MCQs)?\n"
            f"  □ Did I count errors against the CORRECT tolerance level?\n"
            f"    ({config['grade_word']}: ≤ {config.get('tol_essay', 2)} for essay)\n"
            f"  □ Did I verify every \"text-based detail\" is actually in the passage?\n"
            f"  □ Did I check for verbatim copying (≥ 50% copied = apply copying protocol)?\n"
            f"  □ Does my CJ placement match my numeric score? If not, adjust the numeric score to match CJ."
        )
    else:
        checks = (
            f"  □ Did I apply the correct TASK-LOCK for this question type?\n"
            f"    (Q1–Q5: no reasons required; Q6–Q10: one sentence with support; Q11: paragraph with evidence)\n"
            f"  □ Did I count errors against the CORRECT tolerance level?\n"
            f"    ({config['grade_word']}: ≤ {config['tol_q1_q10']} for Q1–Q10, ≤ {config['tol_q11']} for Q11)\n"
            f"  □ For appositives: Is the identified structure a true NOUN PHRASE renaming another noun?\n"
            f"  □ For Q6–Q10: Is the \"reason\" genuinely new information, or is it circular?\n"
            f"  □ For Q11: Did I verify every \"text-based detail\" is actually in the passage?\n"
            f"  □ For Q11: Did I check for verbatim copying (≥ 50% copied = apply copying protocol)?\n"
            f"  □ Does my CJ placement match my numeric score? If not, adjust the numeric score to match CJ."
        )

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 9: SELF-VERIFICATION CHECK (NEW — before output)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nBefore outputting scores or feedback, re-read ⟦{{{{response}}}}⟧ one final time and verify:\n"
        f"\n{checks}"
    )

    # Section 10: Feedback Output
    if config.get("essay_only"):
        feedback = (
            f"Q11 (3–5 sentences)\n"
            f"  Begin with a positive (organization, topic, or evidence) → one improvement (focus, evidence link, explanation, or transition) → one short model → warm close.\n"
            f"  Keep ≤ 5 sentences; avoid rubric jargon."
        )
    else:
        feedback = (
            f"Q1–Q5 (2–3 sentences)\n"
            f"  Full: 1 praise + 1 encouragement.\n"
            f"  Not full: 1 praise + 1 specific fix + 1 short model.\n"
            f"  Quote literal mechanics from ⟦…⟧.\n"
            f"  Never suggest writing two separate sentences.\n"
            f"  🚫 Never ask for reasons, explanations, or added detail on Q1–Q5.\n"
            f"\nQ6–Q10 (2–3 sentences)\n"
            f"  If Ideas = 2 and Conventions = 1:\n"
            f"    If minor errors present → praise + gentle note + encouragement.\n"
            f"    Else → brief praise-only (no style notes).\n"
            f"  Otherwise: praise the idea; name what's missing (reason/example/explanation or true grammar issue); give one short model; end positive.\n"
            f'  Never mention "flow/smoothness" unless there\'s a real grammar error.\n'
            f"\nQ11 (3–5 sentences)\n"
            f"  Begin with a positive (organization, topic, or evidence) → one improvement (focus, evidence link, explanation, or transition) → one short model → warm close.\n"
            f"  Keep ≤ 5 sentences; avoid rubric jargon."
        )

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 10: FEEDBACK OUTPUT (student-facing only)\n"
        f"════════════════════════════════════════════════════════\n"
        f"\n{feedback}"
    )

    # Section 11: Test-Specific Details
    # Extract from original prompt
    q_refs = _extract_question_references(original, test_code)
    standards = _extract_standards(original)

    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 11: TEST-SPECIFIC DETAILS\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nTest: {test_code} — {topic}\n"
        f"\nPER-QUESTION TARGET SKILL REFERENCE:\n{q_refs}\n"
        f"\nSTANDARDS ALIGNMENT:\n{standards}"
    )

    # Section 12: Execution
    sections.append(
        f"\n════════════════════════════════════════════════════════\n"
        f"SECTION 12: EXECUTION\n"
        f"════════════════════════════════════════════════════════\n"
        f"\nPerform all checklist → comparative → scoring → SELF-CHECK steps internally; then output only the final feedback (2–3 sentences for Q1–Q10; 3–5 for Q11).\n"
        f"Maintain a warm, specific, encouraging tone.\n"
        f"Never show scores, rubric labels, or JSON data.\n"
        f"\n🔹 TEST CONTENT\n"
        f"Here is the passage:\n"
        f"  {{{{passage}}}}\n"
        f"Here is the question:\n"
        f"  {{{{question}}}}\n"
        f"Here is the student's response:\n"
        f"  {{{{response}}}}"
    )

    return "\n".join(sections)


def _build_full_task_lock(
    test_code: str, grade: int, original: str, blank_info: dict
) -> str:
    """Build task-lock section for G3-G5 tests (Q1-Q11)."""
    parts = []

    # Q1-Q5 Task Lock
    parts.append(
        "🔒 Q1–Q5 TASK LOCK — Sentence Editing / Revision\n"
        "Purpose: Edit, combine, fix, or revise sentences to demonstrate a specific skill.\n"
        "\nABSOLUTE RULES (NON-NEGOTIABLE):\n"
        "  ❌ Do NOT require a reason, explanation, example, or cause\n"
        "  ❌ Do NOT suggest adding \"because,\" \"so,\" or extra detail\n"
        "  ❌ Do NOT reward elaboration beyond the task\n"
        "  ✅ Judge success ONLY on whether the specific task goal is met\n"
        "\nValid Proficient Strategies (all accepted for combining tasks):\n"
        "  - Compound subjects sharing one predicate\n"
        "  - Compound predicates\n"
        "  - Coordination (and / but / so)\n"
        "  - Ellipsis of repeated verbs or clauses when meaning is clear\n"
        "  - Appositives using commas, dashes, or parentheses\n"
        "\nProficient Anchor:\n"
        "  One clear, complete sentence that fulfills the specific task — no extra information required."
    )

    # Appositive rules
    parts.append(
        "\n🔒 APPOSITIVE IDENTIFICATION RULES (NON-NEGOTIABLE)\n"
        "An appositive MUST be:\n"
        "  ✅ A NOUN PHRASE that RENAMES or IDENTIFIES another noun\n"
        "  ✅ Set off by commas, dashes, or parentheses\n"
        "\nAn appositive is NOT:\n"
        '  ❌ A prepositional phrase ("from Kenya, Africa")\n'
        '  ❌ A participial phrase ("named Rex and Buddy")\n'
        '  ❌ An adjective phrase ("tall and strong")\n'
        '  ❌ A relative clause ("who lives in Texas")\n'
        '  ❌ An adverbial phrase ("in the morning")\n'
        "\nScore Ideas 0/1 if the task requires an appositive and no true noun-phrase appositive is present."
    )

    # Check if Q5 is a because/but/so task
    lower = original.lower()
    if "because" in lower and ("but" in lower or "so" in lower) and "combine" in lower:
        parts.append(
            "\nQ5 specific (Combine with because/but/so):\n"
            "  target_skill_satisfied = true if:\n"
            "    - the response uses because, but, or so (NOT \"and,\" \"when,\" \"if,\" \"while,\" etc.)\n"
            "    - preserves the meaning of both original sentences\n"
            "    - forms one grammatically complete sentence\n"
            "\n  IMPORTANT: Only because/but/so satisfy this task. Other conjunctions do NOT meet the requirement."
        )

    # Q6-Q10 Task Lock
    parts.append(
        "\n🔒 Q6–Q10 TASK LOCK — Sentence Writing\n"
        "Purpose: Write one on-topic sentence that includes support.\n"
        "\nRequirements:\n"
        "  - One complete sentence\n"
        "  - On topic\n"
        "  - Includes at least ONE of:\n"
        "    • a clear reason (explicit \"because,\" \"so,\" \"since,\" or \"to…\")\n"
        "    • an explanation of feeling or consequence\n"
        "    • a specific example, time, or event\n"
        "  - Implicit reasoning (emotion, motivation, result) counts.\n"
        "  🚫 Never suggest writing more than one sentence."
    )

    # Circular reasoning check
    parts.append(
        "\n🔒 CIRCULAR REASONING CHECK (Q6–Q10) (NEW)\n"
        "Before awarding Ideas 2/2, verify the \"reason\" is NOT:\n"
        "  - A restatement of the question/premise in different words\n"
        '  - A tautology ("X is important because it matters")\n'
        "  - A vague truism with no specific content\n"
        "\nIf the support merely RESTATES the claim without adding new information, score Ideas 1/2."
    )

    # Q11 Task Lock
    q11_prompt = blank_info.get("q11_prompt", "")
    parts.append(
        f"\n🔒 Q11 TASK LOCK — Paragraph Writing\n"
        f"Purpose: Write one organized paragraph in response to the prompt.\n"
        f"\nRequirements:\n"
        f"  - Clear main idea\n"
        f"  - ≥ 2 text-based details with brief explanations\n"
        f"  - Logical order\n"
        f"  - Conceptual accuracy > length or style"
    )

    return "\n".join(parts)


def _build_essay_task_lock(
    test_code: str, grade: int, original: str, blank_info: dict
) -> str:
    """Build task-lock section for G6-G8 tests (essay only)."""
    parts = []
    q11_prompt = blank_info.get("q11_prompt", "")

    parts.append(
        "🔒 Q11 TASK LOCK — Essay Writing\n"
        "Purpose: Write a well-organized multi-paragraph essay in response to the prompt.\n"
        "\nRequirements:\n"
        "  - Clear thesis statement\n"
        "  - Organized body paragraphs with textual evidence\n"
        "  - Logical transitions between ideas\n"
        "  - Concluding statement\n"
        "  - Conceptual accuracy > length or style"
    )

    # Circular reasoning check (applies to essay body paragraphs too)
    parts.append(
        "\n🔒 CIRCULAR REASONING CHECK (NEW)\n"
        "Before crediting a body paragraph's reasoning, verify it adds NEW information:\n"
        "  - Not a restatement of the thesis\n"
        "  - Not a tautology\n"
        "  - Contains specific evidence connected to the claim"
    )

    return "\n".join(parts)


def _build_full_scoring(test_code: str, grade: int, config: dict) -> str:
    """Build scoring section for G3-G5 tests."""
    return (
        "Q1–Q5 (Sentence Editing / Revision)\n"
        "  Ideas (1 pt): 1 if target_skill_satisfied = true; else 0.\n"
        "  Conventions (1 pt): 1 if capital + terminal, not fragment/run-on, major_error_gate = false, and within error tolerance.\n"
        "  ⚠️ Do NOT deduct or coach for missing reasons or explanations.\n"
        "  CJ override: award credit despite one small slip if fluency/meaning is clear.\n"
        "\nQ6–Q10 (One-sentence writing)\n"
        "  Ideas (2 pts):\n"
        "    2 = exactly one complete, on-topic sentence with genuine (non-circular) reason/example/explanation\n"
        "    1 = on-topic but missing clear support, or circular reasoning, or uses > 1 sentence\n"
        "    0 = off-topic\n"
        "  Conventions (1 pt):\n"
        "    1 if one complete grammatical sentence with capital + end punctuation, no meaning-blurring errors.\n"
        "    Do not deduct for: awkward phrasing; long wording; one minor word-choice/preposition slip.\n"
        "    Only deduct when errors blur meaning, create fragments/run-ons, or break grammar.\n"
        "\nQ11 (Paragraph)\n"
        "  Ideas (15 → 0): Start 15; deduct 2–3 each for missing (clear main idea; focus; ≥ 2 text-based details; explanations; logical order).\n"
        "  Conventions (5 → 0): Start 5; deduct 1 per recurring pattern (run-ons; capitalization/punctuation; grammar/spelling; unclear sentence; missing/weak conclusion). Apply tolerance thresholds from Section 4."
    )


def _build_essay_scoring(test_code: str, grade: int, config: dict) -> str:
    """Build scoring section for G6-G8 tests."""
    if config.get("rubric_type") == "5-category":
        return (
            "Essay Scoring (5-category rubric):\n"
            "  Structure (5 pts): Clear thesis, introduction, body paragraphs, conclusion.\n"
            "  Evidence (5 pts): Accurate text-based details with explanations.\n"
            "  Organization (4 pts): Logical flow, transitions between paragraphs.\n"
            "  Sentences (3 pts): Varied sentence types, clear expression.\n"
            "  Conventions (3 pts): Spelling, grammar, punctuation, capitalization.\n"
            "  Total: 20 pts\n"
            "\nApply tolerance thresholds from Section 4 to Conventions category."
        )
    return (
        "Essay Scoring:\n"
        "  Ideas (15 → 0): Start 15; deduct 2–3 each for missing (clear thesis; focus; ≥ 2 text-based details per body paragraph; explanations; logical order; conclusion).\n"
        "  Conventions (5 → 0): Start 5; deduct 1 per recurring pattern (run-ons; capitalization/punctuation; grammar/spelling; unclear sentence). Apply tolerance thresholds from Section 4."
    )


def _extract_question_references(original: str, test_code: str) -> str:
    """Extract per-question skill references from the original prompt."""
    lines = original.split("\n")
    refs = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"Q\d+\s*[–—-]", stripped):
            refs.append(f"  {stripped}")
        elif re.match(r"Q\d+\s*–\s*Q\d+", stripped):
            refs.append(f"  {stripped}")
    if not refs:
        # Try alternate patterns
        for line in lines:
            stripped = line.strip()
            if re.match(r"Q\d+", stripped) and len(stripped) > 5:
                refs.append(f"  {stripped}")
    return "\n".join(refs) if refs else "  (See original prompt for per-question skill targets)"


def _extract_standards(original: str) -> str:
    """Extract standards alignment from original prompt."""
    lines = original.split("\n")
    standards = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if "CCSS" in stripped or "TEKS" in stripped or "standards" in stripped.lower():
            capture = True
        if capture:
            standards.append(f"  {stripped}")
            if len(standards) > 4:
                break
    return "\n".join(standards) if standards else "  CCSS and TEKS aligned (see original prompt)"


def main():
    REVISED_DIR.mkdir(exist_ok=True)

    # Determine which prompts to generate
    testing_dir = ROOT / "Tests for prompt testing"
    test_codes_needed = set()
    if testing_dir.exists():
        for f in testing_dir.iterdir():
            m = re.search(r"G(\d+\.\d+)", f.name)
            if m:
                test_codes_needed.add("G" + m.group(1))

    already_revised = set()
    for f in REVISED_DIR.iterdir():
        m = re.search(r"G(\d+\.\d+)", f.name)
        if m:
            already_revised.add("G" + m.group(1))

    to_generate = sorted(test_codes_needed - already_revised)

    if not to_generate:
        print("All needed prompts already exist in Revised CJ Prompts/")
        return

    print(f"Generating {len(to_generate)} revised prompts: {', '.join(to_generate)}")
    print()

    for code in to_generate:
        print(f"  Generating {code}...", end=" ")
        try:
            revised = build_revised_prompt(code)
            out_path = REVISED_DIR / f"{code} CJ Revised.txt"
            out_path.write_text(revised, encoding="utf-8")
            print(f"OK ({len(revised):,} chars)")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nDone. {len(to_generate)} prompts saved to {REVISED_DIR}")


if __name__ == "__main__":
    main()
