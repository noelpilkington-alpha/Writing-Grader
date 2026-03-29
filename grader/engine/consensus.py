"""Three-grader consensus logic.

Runs 3 parallel scoring calls, then resolves to a single final score using:
1. Unanimous — all 3 agree on total_score → pick best feedback
2. Majority  — 2/3 agree → use majority score, pick best feedback from matching runs
3. Judge     — all 3 differ → 4th Claude call reviews all runs and picks winner
"""

import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import QuestionScore, ConsensusResult, ConsensusMethod, sub_maxes
from .scorer import score_question


# ---------------------------------------------------------------------------
# Gibberish / nonsense detection
# ---------------------------------------------------------------------------

def _is_gibberish(text: str) -> bool:
    """Detect if a student response is gibberish or nonsense.

    Returns True if the text appears to be random characters, repeated
    characters, keyboard mashing, or otherwise not a genuine attempt at
    a written response.
    """
    if not text or not text.strip():
        return True

    cleaned = text.strip()

    # Very short responses (single character after stripping spaces)
    no_spaces = cleaned.replace(" ", "")
    if len(no_spaces) < 2:
        return True

    # Single character repeated (e.g., "ooooooooooo", "lllllll", "aaa")
    unique_chars = set(no_spaces.lower())
    if len(unique_chars) <= 2 and len(no_spaces) > 2:
        return True

    # Single character or token repeated with spaces (e.g., "l l l l l", "S S S S")
    tokens = cleaned.split()
    unique_tokens = set(t.lower() for t in tokens)
    if len(tokens) >= 3 and len(unique_tokens) <= 2 and all(len(t) <= 2 for t in tokens):
        return True

    # Random consonant clusters with no vowels — keyboard mashing
    # (e.g., "VV JFDRFV EKDXC KJKRF RGRGN")
    vowels = set("aeiouAEIOU")
    if len(no_spaces) >= 6:
        vowel_count = sum(1 for c in no_spaces if c in vowels)
        vowel_ratio = vowel_count / len(no_spaces)
        # Real English has ~35-40% vowels; gibberish typically < 10%
        if vowel_ratio < 0.10 and len(no_spaces) > 5:
            return True

    # All same word repeated (e.g., "dog dog dog dog dog")
    if len(tokens) >= 3 and len(unique_tokens) == 1:
        return True

    return False


def _pick_best_feedback(runs: list[QuestionScore]) -> QuestionScore:
    """From a set of runs with the same score, pick the one with the longest feedback.

    Longer feedback tends to be more specific and helpful for students.
    """
    return max(runs, key=lambda r: len(r.feedback))


def _judge_call(
    client,
    model: str,
    runs: list[QuestionScore],
    qnum: int,
    max_score: int,
) -> tuple[QuestionScore, str]:
    """4th Claude call to adjudicate when all 3 runs disagree.

    The judge sees all 3 scores + internal notes and picks the most accurate one,
    or synthesizes a corrected score.
    """
    ideas_max, conv_max = sub_maxes(qnum)

    runs_summary = []
    for i, r in enumerate(runs, 1):
        runs_summary.append(
            f"Run {i}: Ideas {r.ideas_score}/{r.ideas_max}, "
            f"Conv {r.conventions_score}/{r.conventions_max}, "
            f"Total {r.total_score}/{r.total_max}\n"
            f"  Notes: {r.internal_notes[:300]}\n"
            f"  Feedback: {r.feedback[:200]}"
        )

    system = (
        "You are a senior grading reviewer. Three independent graders scored the same "
        "student response and all three gave different total scores. Review their reasoning "
        "and determine the most accurate score.\n\n"
        "Output ONLY a JSON object with these keys:\n"
        '  "chosen_run": integer (1, 2, or 3 — which run is most accurate),\n'
        '  "ideas_score": integer (final ideas score),\n'
        '  "conventions_score": integer (final conventions score),\n'
        '  "reasoning": string (brief explanation of your decision)\n'
    )

    user_msg = (
        f"Question {qnum} (max {max_score} pts, Ideas max {ideas_max}, Conv max {conv_max}).\n\n"
        + "\n\n".join(runs_summary)
        + "\n\nWhich run is most accurate? Or provide corrected scores if none are exactly right."
    )

    msg = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    content = msg.content[0].text
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    reasoning = data.get("reasoning", "Judge call failed to parse.")

    # If judge picked a specific run, use it
    chosen = data.get("chosen_run")
    if chosen and 1 <= chosen <= 3:
        result = runs[chosen - 1]
        # But override scores if judge provided different ones
        if "ideas_score" in data and "conventions_score" in data:
            judge_ideas = min(data["ideas_score"], ideas_max)
            judge_conv = min(data["conventions_score"], conv_max)
            judge_total = min(judge_ideas + judge_conv, max_score)
            # Only override if judge's scores differ from chosen run
            if judge_total != result.total_score:
                result = QuestionScore(
                    question=qnum,
                    ideas_score=judge_ideas,
                    ideas_max=ideas_max,
                    conventions_score=judge_conv,
                    conventions_max=conv_max,
                    total_score=judge_total,
                    total_max=max_score,
                    feedback=runs[chosen - 1].feedback,
                    internal_notes=f"Judge override: {reasoning}",
                )
        return result, reasoning

    # Judge provided scores but no chosen_run — build from scores
    if "ideas_score" in data and "conventions_score" in data:
        judge_ideas = min(data["ideas_score"], ideas_max)
        judge_conv = min(data["conventions_score"], conv_max)
        judge_total = min(judge_ideas + judge_conv, max_score)
        # Use feedback from the run closest to judge's score
        closest = min(runs, key=lambda r: abs(r.total_score - judge_total))
        return QuestionScore(
            question=qnum,
            ideas_score=judge_ideas,
            ideas_max=ideas_max,
            conventions_score=judge_conv,
            conventions_max=conv_max,
            total_score=judge_total,
            total_max=max_score,
            feedback=closest.feedback,
            internal_notes=f"Judge synthesis: {reasoning}",
        ), reasoning

    # Fallback: use median score run
    sorted_runs = sorted(runs, key=lambda r: r.total_score)
    return sorted_runs[1], f"Judge parse failed; using median. Raw: {content[:200]}"


def grade_question_consensus(
    client,
    model: str,
    rubric: str,
    passage: str,
    question: str,
    response: str,
    qnum: int,
    max_score: int,
    num_runs: int = 3,
    temperature: float = 0.3,
) -> ConsensusResult:
    """Grade a question using multiple runs and consensus.

    Runs `num_runs` parallel scoring calls, then resolves via consensus.
    """
    # Blank response shortcut
    if not response or not response.strip():
        blank = QuestionScore.blank(qnum, max_score)
        return ConsensusResult(
            question=qnum,
            final_score=blank,
            consensus_method=ConsensusMethod.SINGLE,
            runs=[blank],
        )

    # Gibberish detection — catch nonsense before wasting API calls
    if _is_gibberish(response):
        gibberish = QuestionScore.gibberish(qnum, max_score)
        return ConsensusResult(
            question=qnum,
            final_score=gibberish,
            consensus_method=ConsensusMethod.SINGLE,
            runs=[gibberish],
        )

    # Run graders in parallel
    runs: list[QuestionScore] = []
    with ThreadPoolExecutor(max_workers=num_runs) as pool:
        futures = [
            pool.submit(
                score_question,
                client, model, rubric, passage, question, response,
                qnum, max_score, temperature,
            )
            for _ in range(num_runs)
        ]
        for f in as_completed(futures):
            try:
                runs.append(f.result())
            except Exception as e:
                # Log the failure but mark it clearly as an API error
                import logging
                logging.error(f"Grading run failed for Q{qnum}: {e}")
                runs.append(QuestionScore(
                    question=qnum,
                    ideas_score=0, ideas_max=sub_maxes(qnum)[0],
                    conventions_score=0, conventions_max=sub_maxes(qnum)[1],
                    total_score=0, total_max=max_score,
                    feedback="[GRADING ERROR] This question could not be graded due to an API error. Please retry.",
                    internal_notes=f"API_ERROR: {e}",
                ))

    # Filter out failed runs for consensus
    valid_runs = [r for r in runs if not r.internal_notes.startswith("API_ERROR:") and r.internal_notes != "JSON parse failed after 2 attempts."]
    if not valid_runs:
        valid_runs = runs  # use whatever we got

    if len(valid_runs) == 1:
        return ConsensusResult(
            question=qnum,
            final_score=valid_runs[0],
            consensus_method=ConsensusMethod.SINGLE,
            runs=runs,
        )

    # Check consensus on total_score
    scores = [r.total_score for r in valid_runs]
    counts = Counter(scores)
    most_common_score, freq = counts.most_common(1)[0]

    # Unanimous
    if freq == len(valid_runs):
        best = _pick_best_feedback(valid_runs)
        return ConsensusResult(
            question=qnum,
            final_score=best,
            consensus_method=ConsensusMethod.UNANIMOUS,
            runs=runs,
        )

    # Majority (2+ out of 3 agree)
    if freq >= 2:
        matching = [r for r in valid_runs if r.total_score == most_common_score]
        best = _pick_best_feedback(matching)
        return ConsensusResult(
            question=qnum,
            final_score=best,
            consensus_method=ConsensusMethod.MAJORITY,
            runs=runs,
        )

    # All differ — judge call
    time.sleep(0.3)
    judge_result, reasoning = _judge_call(client, model, valid_runs, qnum, max_score)
    return ConsensusResult(
        question=qnum,
        final_score=judge_result,
        consensus_method=ConsensusMethod.JUDGE,
        runs=runs,
        judge_reasoning=reasoning,
    )
