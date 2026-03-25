"""Writing Test Grader — FastAPI Application.

Run with: uvicorn api.app:app --reload --port 8000
API docs: http://localhost:8000/docs
"""

import csv
import io
import json
import re
import tempfile
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import database as db
from .auth import require_api_key
from .schemas import (
    ApiKeyCreateRequest,
    ApiKeyResponse,
    GradeRequest,
    GradeResponse,
    JobResultResponse,
    JobStatusResponse,
    PromptResponse,
    PromptUploadRequest,
    QuestionResultResponse,
    TestCreateRequest,
    TestListResponse,
    TestResponse,
)
from .worker import submit_job

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Writing Test Grader API",
    description=(
        "AI-powered writing test grader using 3-grader comparative judgement consensus. "
        "Supports G3-G8 standardized writing assessments."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


# ============================================================
# Health
# ============================================================

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "writing-test-grader"}


# ============================================================
# API Keys (admin — no auth required for key creation)
# ============================================================

@app.post("/api-keys", response_model=ApiKeyResponse, tags=["Admin"])
def create_api_key(req: ApiKeyCreateRequest):
    """Create a new API key. Store the returned key securely — it cannot be retrieved later."""
    key = db.create_api_key(req.name)
    return ApiKeyResponse(
        key=key,
        name=req.name,
        message="Store this key securely. It cannot be retrieved later.",
    )


# ============================================================
# Grading
# ============================================================

@app.post("/grade", response_model=GradeResponse, tags=["Grading"])
def submit_grading(req: GradeRequest, _key: dict = Depends(require_api_key)):
    """Submit a grading job. Returns a job ID to poll for results.

    Responses should be keyed by question number as strings: {"1": "answer", "2": "answer", ...}
    Blank responses (empty string) will receive 0 points automatically.
    """
    # Validate test code exists (in DB or filesystem)
    prompt_exists = db.get_active_prompt(req.test_code) is not None
    prompt_file = ROOT / "Revised Prompts V2" / f"{req.test_code} CJ V2.txt"
    if not prompt_exists and not prompt_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No grading prompt found for test code '{req.test_code}'.",
        )

    job_id = db.create_job(
        student_name=req.student_name,
        test_code=req.test_code,
        responses=req.responses,
        num_runs=req.num_runs,
    )

    submit_job(job_id)

    return GradeResponse(
        job_id=job_id,
        status="pending",
        message=f"Grading job submitted. Poll GET /grade/{job_id}/status for progress.",
    )


@app.post("/grade/pdf", response_model=GradeResponse, tags=["Grading"])
async def submit_grading_pdf(
    file: UploadFile = File(..., description="Student test PDF"),
    test_code: str = Query(..., description="Test code, e.g. G3.1"),
    student_name: str = Query(default="", description="Student name (auto-detected from PDF if blank)"),
    num_runs: int = Query(default=3, ge=1, le=5),
    _key: dict = Depends(require_api_key),
):
    """Upload a student PDF for grading. Extracts responses automatically.

    The PDF should be an Edulastic-exported test with student responses.
    """
    import re
    import sys
    sys.path.insert(0, str(ROOT))
    from grader.grade import detect_student_name, extract_passage_and_questions

    # Save uploaded PDF to temp file
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Extract text for student name detection
        doc = fitz.open(str(tmp_path))
        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()

        if not student_name:
            student_name = detect_student_name(full_text)

        # Extract responses
        extracted = extract_passage_and_questions(tmp_path)
        questions = extracted.get("questions", {})

        if not questions:
            raise HTTPException(
                status_code=422,
                detail="Could not extract any responses from the PDF. The PDF may use Type3 fonts or have an unexpected format.",
            )

        # Convert to string-keyed responses
        responses = {}
        for qnum, q_data in questions.items():
            responses[str(qnum)] = q_data.get("response", "")

    finally:
        tmp_path.unlink(missing_ok=True)

    # Validate prompt exists
    prompt_exists = db.get_active_prompt(test_code) is not None
    prompt_file = ROOT / "Revised Prompts V2" / f"{test_code} CJ V2.txt"
    if not prompt_exists and not prompt_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No grading prompt found for test code '{test_code}'.",
        )

    job_id = db.create_job(
        student_name=student_name,
        test_code=test_code,
        responses=responses,
        num_runs=num_runs,
    )

    submit_job(job_id)

    return GradeResponse(
        job_id=job_id,
        status="pending",
        message=f"PDF processed. {len(responses)} responses extracted for {student_name}. Poll GET /grade/{job_id}/status for progress.",
    )


@app.get("/grade/{job_id}/status", response_model=JobStatusResponse, tags=["Grading"])
def get_job_status(job_id: str, _key: dict = Depends(require_api_key)):
    """Check the status of a grading job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return JobStatusResponse(
        job_id=job["id"],
        student_name=job["student_name"],
        test_code=job["test_code"],
        status=job["status"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )


@app.get("/grade/{job_id}/result", response_model=JobResultResponse, tags=["Grading"])
def get_job_result(job_id: str, _key: dict = Depends(require_api_key)):
    """Get the complete grading result for a finished job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job["status"] != "complete":
        raise HTTPException(
            status_code=409,
            detail=f"Job is '{job['status']}'. Results available when status is 'complete'.",
        )

    results = db.get_job_results(job_id)
    questions = []
    total_score = 0
    total_max = 0

    for r in results:
        run_scores = [rd.get("total_score", 0) for rd in r["run_details"]]
        questions.append(QuestionResultResponse(
            question=r["question"],
            ideas_score=r["final_ideas_score"],
            ideas_max=r["final_ideas_max"],
            conventions_score=r["final_conventions_score"],
            conventions_max=r["final_conventions_max"],
            total_score=r["final_total_score"],
            total_max=r["final_total_max"],
            feedback=r["final_feedback"],
            consensus_method=r["consensus_method"],
            run_scores=run_scores,
            judge_reasoning=r["judge_reasoning"],
        ))
        total_score += r["final_total_score"]
        total_max += r["final_total_max"]

    return JobResultResponse(
        job_id=job_id,
        student_name=job["student_name"],
        test_code=job["test_code"],
        status=job["status"],
        total_score=total_score,
        total_max=total_max,
        questions=questions,
    )


# ============================================================
# Jobs List & Export
# ============================================================

@app.get("/grade", tags=["Grading"])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None, description="Filter by status: pending, running, complete, failed"),
    search: Optional[str] = Query(default=None, description="Search by student name, test code, or job ID"),
    _key: dict = Depends(require_api_key),
):
    """List recent grading jobs with optional filters."""
    jobs = db.list_jobs(limit=limit, status=status, search=search)
    # Attach total scores for completed jobs
    for job in jobs:
        if job["status"] == "complete":
            results = db.get_job_results(job["id"])
            job["total_score"] = sum(r["final_total_score"] for r in results)
            job["total_max"] = sum(r["final_total_max"] for r in results)
        else:
            job["total_score"] = None
            job["total_max"] = None
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/grade/{job_id}/export", tags=["Grading"])
def export_job_csv(job_id: str, _key: dict = Depends(require_api_key)):
    """Export grading results as a CSV file."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job["status"] != "complete":
        raise HTTPException(status_code=409, detail="Job not complete yet.")

    results = db.get_job_results(job_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Student", "Test", "Question", "Ideas Score", "Ideas Max",
        "Conventions Score", "Conventions Max", "Total Score", "Total Max",
        "Consensus Method", "Run Scores", "Feedback",
    ])
    for r in results:
        run_scores = [rd.get("total_score", 0) for rd in r["run_details"]]
        writer.writerow([
            job["student_name"], job["test_code"], r["question"],
            r["final_ideas_score"], r["final_ideas_max"],
            r["final_conventions_score"], r["final_conventions_max"],
            r["final_total_score"], r["final_total_max"],
            r["consensus_method"], str(run_scores), r["final_feedback"],
        ])

    output.seek(0)
    filename = f"{job['student_name'].replace(' ', '_')}_{job['test_code']}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# Tests
# ============================================================

@app.get("/tests", response_model=TestListResponse, tags=["Tests"])
def list_tests(_key: dict = Depends(require_api_key)):
    """List all available tests."""
    tests = db.list_tests()
    items = []
    for t in tests:
        items.append(TestResponse(
            test_code=t["test_code"],
            grade_level=t["grade_level"],
            title=t["title"],
            has_passage=bool(t.get("passage", False)),
            question_count=0,
            has_q11_article=False,
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        ))
    return TestListResponse(tests=items)


@app.post("/tests", response_model=TestResponse, tags=["Tests"])
def create_or_update_test(req: TestCreateRequest, _key: dict = Depends(require_api_key)):
    """Create or update a test (passage, questions, Q11 article)."""
    t = db.upsert_test(
        test_code=req.test_code,
        grade_level=req.grade_level,
        title=req.title,
        passage=req.passage,
        questions=req.questions,
        q11_article=req.q11_article,
    )
    questions = json.loads(t["questions"]) if isinstance(t["questions"], str) else t["questions"]
    return TestResponse(
        test_code=t["test_code"],
        grade_level=t["grade_level"],
        title=t["title"],
        has_passage=bool(t["passage"]),
        question_count=len(questions),
        has_q11_article=bool(t.get("q11_article")),
        created_at=t["created_at"],
        updated_at=t["updated_at"],
    )


@app.get("/tests/{test_code}", tags=["Tests"])
def get_test(test_code: str, _key: dict = Depends(require_api_key)):
    """Get full test details including passage and questions."""
    t = db.get_test(test_code)
    if not t:
        raise HTTPException(status_code=404, detail=f"Test '{test_code}' not found.")
    return t


# ============================================================
# Prompts
# ============================================================

@app.post("/prompts/{test_code}", response_model=PromptResponse, tags=["Prompts"])
def upload_prompt(test_code: str, req: PromptUploadRequest, _key: dict = Depends(require_api_key)):
    """Upload or update the grading prompt for a test code.

    The new prompt becomes the active version. Previous prompts are deactivated.
    """
    p = db.upsert_prompt(test_code, req.prompt_text, req.version)
    return PromptResponse(
        test_code=p["test_code"],
        version=p["version"],
        active=bool(p["active"]),
        created_at=p["created_at"],
        prompt_length=len(p["prompt_text"]),
    )


@app.get("/prompts/{test_code}", response_model=PromptResponse, tags=["Prompts"])
def get_prompt(test_code: str, _key: dict = Depends(require_api_key)):
    """Get the active grading prompt for a test code."""
    p = db.get_active_prompt(test_code)
    if not p:
        # Check filesystem
        path = ROOT / "Revised Prompts V2" / f"{test_code} CJ V2.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return PromptResponse(
                test_code=test_code,
                version="V2",
                active=True,
                created_at="filesystem",
                prompt_length=len(text),
            )
        raise HTTPException(status_code=404, detail=f"No prompt found for '{test_code}'.")
    return PromptResponse(
        test_code=p["test_code"],
        version=p["version"],
        active=bool(p["active"]),
        created_at=p["created_at"],
        prompt_length=len(p["prompt_text"]),
    )


# ============================================================
# Batch Grading
# ============================================================

@app.post("/grade/batch", tags=["Grading"])
def submit_batch_grading(
    submissions: list[GradeRequest],
    _key: dict = Depends(require_api_key),
):
    """Submit multiple grading jobs at once. Returns a list of job IDs.

    Each item in the list is a standard GradeRequest.
    All jobs run in parallel in the background.
    """
    jobs = []
    for req in submissions:
        # Validate prompt exists
        prompt_exists = db.get_active_prompt(req.test_code) is not None
        prompt_file = ROOT / "Revised Prompts V2" / f"{req.test_code} CJ V2.txt"
        if not prompt_exists and not prompt_file.exists():
            jobs.append({
                "student_name": req.student_name,
                "test_code": req.test_code,
                "job_id": None,
                "error": f"No grading prompt found for '{req.test_code}'.",
            })
            continue

        job_id = db.create_job(
            student_name=req.student_name,
            test_code=req.test_code,
            responses=req.responses,
            num_runs=req.num_runs,
        )
        submit_job(job_id)
        jobs.append({
            "student_name": req.student_name,
            "test_code": req.test_code,
            "job_id": job_id,
            "error": None,
        })

    return {
        "submitted": sum(1 for j in jobs if j["job_id"]),
        "failed": sum(1 for j in jobs if not j["job_id"]),
        "jobs": jobs,
    }


# ============================================================
# Admin — Sync filesystem prompts/tests into DB
# ============================================================

@app.post("/admin/sync", tags=["Admin"])
def sync_filesystem(_key: dict = Depends(require_api_key)):
    """Import all filesystem prompts and cached tests into the database.

    - Reads all `Revised Prompts V2/*.txt` files and creates DB prompts
    - Reads `test_content_cache.json` and creates DB test entries
    - Does NOT overwrite existing DB entries (only fills gaps)
    """
    tests_synced = 0
    prompts_synced = 0

    # Collect all test codes from prompts dir (needed to create test stubs)
    all_prompt_codes = set()
    prompts_dir = ROOT / "Revised Prompts V2"
    if prompts_dir.exists():
        for path in sorted(prompts_dir.glob("*.txt")):
            match = re.match(r"(G\d+\.\d+)\s+CJ\s+V2\.txt", path.name)
            if match:
                all_prompt_codes.add(match.group(1))

    # Step 1: Sync tests from cache FIRST (foreign key requires tests exist before prompts)
    cache_path = ROOT / "grader" / "test_content_cache.json"
    cache = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        for test_code, entry in cache.items():
            if db.get_test(test_code) is None:
                grade_match = re.match(r"G(\d+)", test_code)
                grade_level = int(grade_match.group(1)) if grade_match else 3
                questions = dict(entry.get("questions", {}))
                db.upsert_test(
                    test_code=test_code,
                    grade_level=grade_level,
                    title=entry.get("title", ""),
                    passage=entry.get("passage", ""),
                    questions=questions,
                    q11_article=entry.get("q11_article"),
                )
                tests_synced += 1

    # Step 2: Create stub test entries for any prompt codes not in cache
    for test_code in all_prompt_codes:
        if db.get_test(test_code) is None:
            grade_match = re.match(r"G(\d+)", test_code)
            grade_level = int(grade_match.group(1)) if grade_match else 3
            db.upsert_test(
                test_code=test_code,
                grade_level=grade_level,
                title=f"{test_code} (prompt only — no cached content)",
            )
            tests_synced += 1

    # Step 3: Now sync prompts (all test entries exist)
    if prompts_dir.exists():
        for path in sorted(prompts_dir.glob("*.txt")):
            match = re.match(r"(G\d+\.\d+)\s+CJ\s+V2\.txt", path.name)
            if not match:
                continue
            test_code = match.group(1)
            if db.get_active_prompt(test_code) is None:
                text = path.read_text(encoding="utf-8")
                db.upsert_prompt(test_code, text, "V2")
                prompts_synced += 1

    return {
        "tests_synced": tests_synced,
        "prompts_synced": prompts_synced,
        "message": f"Synced {tests_synced} tests and {prompts_synced} prompts from filesystem.",
    }


# ============================================================
# Dashboard (served last so it doesn't shadow API routes)
# ============================================================

@app.get("/", tags=["System"])
def dashboard():
    """Serve the admin dashboard."""
    return FileResponse(
        str(STATIC_DIR / "dashboard.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
