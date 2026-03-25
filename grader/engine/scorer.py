"""Single-grader scoring: one Claude API call per question."""

import json
import re
import time

from .models import QuestionScore, sub_maxes

SYSTEM_PROMPT = (
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


def _fill_rubric(rubric: str, passage: str, question: str, response: str) -> str:
    """Replace template placeholders in the rubric."""
    filled = rubric
    filled = filled.replace("{{passage}}", passage or "(no passage)")
    filled = filled.replace("{{question}}", question or "(no question)")
    filled = filled.replace("{{response}}", response or "(no response)")
    return filled


def _parse_json(text: str) -> dict | None:
    """Try to parse JSON from the API response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _clamp_scores(data: dict, qnum: int, max_score: int) -> dict:
    """Ensure scores don't exceed known maximums."""
    ideas_max, conv_max = sub_maxes(qnum)
    data["ideas_score"] = min(data.get("ideas_score", 0), ideas_max)
    data["ideas_max"] = ideas_max
    data["conventions_score"] = min(data.get("conventions_score", 0), conv_max)
    data["conventions_max"] = conv_max
    data["total_score"] = min(
        data["ideas_score"] + data["conventions_score"],
        max_score,
    )
    data["total_max"] = max_score
    data.setdefault("question", qnum)
    return data


def score_question(
    client,
    model: str,
    rubric: str,
    passage: str,
    question: str,
    response: str,
    qnum: int,
    max_score: int,
    temperature: float = 0.3,
) -> QuestionScore:
    """Run a single grading call and return a QuestionScore.

    This is the atomic unit of grading — one Claude call, one score.
    """
    filled = _fill_rubric(rubric, passage, question, response)
    tokens = 2048 if qnum == 11 else 1024
    user_msg = f"Grade question {qnum} (max {max_score} points).\n\n{filled}"

    data = None
    for attempt in range(2):
        msg = client.messages.create(
            model=model,
            max_tokens=tokens,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = msg.content[0].text
        data = _parse_json(content)
        if data is not None:
            break

        # Retry with explicit JSON reminder
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
            "feedback": content[:500] if content else "Grading failed.",
            "internal_notes": "JSON parse failed after 2 attempts.",
        }

    data = _clamp_scores(data, qnum, max_score)
    data.setdefault("feedback", "")
    data.setdefault("internal_notes", "")

    return QuestionScore.from_dict(data)
