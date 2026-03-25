"""Writing Test Grading Engine — public API.

Usage:
    from grader.engine import init, grade_student, grade_question

    init()  # loads env, creates client
    result = grade_student(test_code="G3.1", responses={1: "...", 2: "...", ...})
    result = grade_question(test_code="G3.1", qnum=1, response="...")
"""

import json
import time
from pathlib import Path
from typing import Optional

from .client import create_client, get_model, init_env
from .consensus import grade_question_consensus
from .models import (
    ConsensusMethod,
    ConsensusResult,
    QuestionScore,
    StudentResult,
    max_score_for,
)
from .prompts import build_grading_passage, load_prompt, load_q11_article, load_test_content

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "Revised Prompts V2"
CACHE_PATH = ROOT / "grader" / "test_content_cache.json"
RESULTS_DIR = ROOT / "grader" / "results"

# Module-level state (initialized via init())
_client = None
_model = None


def init(root: Optional[Path] = None):
    """Initialize the grading engine: load env, create client."""
    global _client, _model
    r = root or ROOT
    init_env(r)
    _client = create_client()
    _model = get_model()


def get_client_and_model():
    """Return the current client and model, initializing if needed."""
    global _client, _model
    if _client is None:
        init()
    return _client, _model


def grade_question(
    test_code: str,
    qnum: int,
    response: str,
    *,
    passage: Optional[str] = None,
    question_text: Optional[str] = None,
    q11_article: Optional[str] = None,
    num_runs: int = 3,
    student_name: str = "",
    verbose: bool = True,
) -> ConsensusResult:
    """Grade a single question with consensus.

    If passage/question_text are not provided, loads them from cache.
    """
    client, model = get_client_and_model()

    # Load prompt
    rubric = load_prompt(test_code, PROMPTS_DIR)

    # Load test content from cache if not provided
    if passage is None or question_text is None:
        content = load_test_content(test_code, CACHE_PATH)
        if content is None:
            raise ValueError(
                f"Test {test_code} not in cache and passage/question_text not provided."
            )
        if passage is None:
            passage = content["passage"]
        if question_text is None:
            questions = dict(content["questions"])
            question_text = questions.get(str(qnum), questions.get(qnum, ""))

    # Load Q11 article if needed
    if qnum == 11 and q11_article is None:
        q11_article = load_q11_article(test_code, CACHE_PATH)

    grading_passage = build_grading_passage(passage, q11_article, qnum)
    max_score = max_score_for(qnum)

    if verbose:
        print(f"Grading Q{qnum} ({num_runs} runs) ...", end=" ", flush=True)

    result = grade_question_consensus(
        client, model, rubric, grading_passage, question_text, response,
        qnum, max_score, num_runs=num_runs,
    )

    if verbose:
        fs = result.final_score
        method = result.consensus_method.value
        scores_summary = ", ".join(str(r.total_score) for r in result.runs)
        print(
            f"Ideas {fs.ideas_score}/{fs.ideas_max}  "
            f"Conv {fs.conventions_score}/{fs.conventions_max}  "
            f"Total {fs.total_score}/{fs.total_max}  "
            f"[{method}: {scores_summary}]"
        )

    return result


def grade_student(
    test_code: str,
    responses: dict[int, str],
    *,
    student_name: str = "Unknown",
    passage: Optional[str] = None,
    question_texts: Optional[dict] = None,
    q11_article: Optional[str] = None,
    num_runs: int = 3,
    verbose: bool = True,
    save: bool = True,
) -> StudentResult:
    """Grade all questions for a student with consensus.

    Args:
        test_code: e.g. "G3.1"
        responses: {1: "response text", 2: "...", ...}
        student_name: for display and file naming
        passage: override passage (if not in cache)
        question_texts: override question texts {1: "Q text", ...}
        q11_article: override Q11 article text
        num_runs: number of parallel grading runs per question (default 3)
        verbose: print progress
        save: save results JSON to grader/results/
    """
    client, model = get_client_and_model()

    # Load prompt and content
    rubric = load_prompt(test_code, PROMPTS_DIR)
    content = load_test_content(test_code, CACHE_PATH)

    if passage is None:
        if content:
            passage = content["passage"]
        else:
            passage = ""

    if question_texts is None:
        if content:
            question_texts = dict(content["questions"])
        else:
            question_texts = {}

    if q11_article is None:
        q11_article = load_q11_article(test_code, CACHE_PATH)

    if verbose:
        print(f"Grading {student_name} — {test_code} ({num_runs}-run consensus)")
        print("=" * 60)

    result = StudentResult(
        student=student_name,
        test_code=test_code,
        prompt_version="V2",
    )

    for qnum in sorted(responses.keys()):
        resp = responses[qnum]
        q_text = question_texts.get(str(qnum), question_texts.get(qnum, ""))
        grading_passage = build_grading_passage(passage, q11_article, qnum)
        max_score = max_score_for(qnum)

        if verbose:
            print(f"  Q{qnum} ({num_runs} runs) ...", end=" ", flush=True)

        consensus = grade_question_consensus(
            client, model, rubric, grading_passage, q_text, resp,
            qnum, max_score, num_runs=num_runs,
        )

        if verbose:
            fs = consensus.final_score
            method = consensus.consensus_method.value
            scores_summary = ", ".join(str(r.total_score) for r in consensus.runs)
            blank_tag = " [BLANK]" if not resp.strip() else ""
            print(
                f"Ideas {fs.ideas_score}/{fs.ideas_max}  "
                f"Conv {fs.conventions_score}/{fs.conventions_max}  "
                f"Total {fs.total_score}/{fs.total_max}  "
                f"[{method}: {scores_summary}]{blank_tag}"
            )

        result.questions[str(qnum)] = consensus
        time.sleep(0.3)

    result.compute_totals()

    if verbose:
        print("=" * 60)
        print(f"Final: {result.total_score}/{result.total_max}")

    if save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = student_name.replace(" ", "_")
        out_path = RESULTS_DIR / f"{safe_name}_{test_code}_V2.json"
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if verbose:
            print(f"Saved to {out_path}")

    return result
