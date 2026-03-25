"""Background grading worker.

Runs grading jobs in a thread pool so the API can return immediately.
"""

import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import database as db

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "Revised Prompts V2"
CACHE_PATH = ROOT / "grader" / "test_content_cache.json"

# Thread pool for background grading jobs
_executor = ThreadPoolExecutor(max_workers=2)


def _run_grading_job(job_id: str):
    """Execute a grading job (runs in background thread)."""
    import sys
    sys.path.insert(0, str(ROOT))

    from grader.engine import init, get_client_and_model
    from grader.engine.consensus import grade_question_consensus
    from grader.engine.models import max_score_for
    from grader.engine.prompts import (
        build_grading_passage,
        load_prompt,
        load_q11_article,
        load_test_content,
    )

    try:
        db.update_job_status(job_id, "running")
        job = db.get_job(job_id)

        test_code = job["test_code"]
        responses = job["responses"]
        num_runs = job["num_runs"]

        # Initialize engine
        init()
        client, model = get_client_and_model()

        # Load prompt — check DB first, then fall back to filesystem
        db_prompt = db.get_active_prompt(test_code)
        if db_prompt:
            rubric = db_prompt["prompt_text"]
        else:
            rubric = load_prompt(test_code, PROMPTS_DIR)

        # Load test content — check DB first, then fall back to cache
        db_test = db.get_test(test_code)
        if db_test and db_test.get("passage"):
            passage = db_test["passage"]
            question_texts = db_test["questions"]
            q11_article = db_test.get("q11_article")
        else:
            content = load_test_content(test_code, CACHE_PATH)
            if content:
                passage = content["passage"]
                question_texts = dict(content["questions"])
            else:
                passage = ""
                question_texts = {}
            q11_article = load_q11_article(test_code, CACHE_PATH)

        total_score = 0
        total_max = 0

        for qnum_str, response_text in sorted(responses.items(), key=lambda x: int(x[0])):
            qnum = int(qnum_str)
            q_text = question_texts.get(str(qnum), question_texts.get(qnum, ""))
            grading_passage = build_grading_passage(passage, q11_article, qnum)
            max_score = max_score_for(qnum)

            result = grade_question_consensus(
                client, model, rubric, grading_passage, q_text, response_text,
                qnum, max_score, num_runs=num_runs,
            )

            db.save_question_result(job_id, result)
            total_score += result.final_score.total_score
            total_max += result.final_score.total_max

        db.update_job_status(job_id, "complete")

    except Exception as e:
        db.update_job_status(job_id, "failed", error=traceback.format_exc())


def submit_job(job_id: str):
    """Submit a grading job to the background thread pool."""
    _executor.submit(_run_grading_job, job_id)
