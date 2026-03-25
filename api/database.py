"""SQLite database for grading jobs, results, and test management."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parents[1] / "grader" / "grading.db"


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key         TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            active      INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS tests (
            test_code       TEXT PRIMARY KEY,
            grade_level     INTEGER NOT NULL,
            title           TEXT NOT NULL DEFAULT '',
            passage         TEXT NOT NULL DEFAULT '',
            questions       TEXT NOT NULL DEFAULT '{}',
            q11_article     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS prompts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            test_code   TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            version     TEXT NOT NULL DEFAULT 'V2',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            active      INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (test_code) REFERENCES tests(test_code)
        );

        CREATE TABLE IF NOT EXISTS grading_jobs (
            id              TEXT PRIMARY KEY,
            student_name    TEXT NOT NULL,
            test_code       TEXT NOT NULL,
            responses       TEXT NOT NULL,
            num_runs        INTEGER NOT NULL DEFAULT 3,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            started_at      TEXT,
            completed_at    TEXT,
            error           TEXT
        );

        CREATE TABLE IF NOT EXISTS grading_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      TEXT NOT NULL,
            question    INTEGER NOT NULL,
            final_ideas_score       INTEGER NOT NULL,
            final_ideas_max         INTEGER NOT NULL,
            final_conventions_score INTEGER NOT NULL,
            final_conventions_max   INTEGER NOT NULL,
            final_total_score       INTEGER NOT NULL,
            final_total_max         INTEGER NOT NULL,
            final_feedback          TEXT NOT NULL DEFAULT '',
            consensus_method        TEXT NOT NULL,
            run_details             TEXT NOT NULL DEFAULT '[]',
            judge_reasoning         TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (job_id) REFERENCES grading_jobs(id)
        );
    """)
    conn.commit()
    conn.close()


# --- API Keys ---

def create_api_key(name: str) -> str:
    """Create a new API key and return it."""
    key = f"wg_{uuid.uuid4().hex}"
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key, name) VALUES (?, ?)",
        (key, name),
    )
    conn.commit()
    conn.close()
    return key


def validate_api_key(key: str) -> Optional[dict]:
    """Validate an API key. Returns key info or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key = ? AND active = 1", (key,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# --- Tests ---

def upsert_test(test_code: str, grade_level: int, title: str = "",
                passage: str = "", questions: dict = None,
                q11_article: str = None) -> dict:
    """Create or update a test."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    questions_json = json.dumps(questions or {}, ensure_ascii=False)
    conn.execute("""
        INSERT INTO tests (test_code, grade_level, title, passage, questions, q11_article, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(test_code) DO UPDATE SET
            grade_level = excluded.grade_level,
            title = excluded.title,
            passage = excluded.passage,
            questions = excluded.questions,
            q11_article = excluded.q11_article,
            updated_at = excluded.updated_at
    """, (test_code, grade_level, title, passage, questions_json, q11_article, now, now))
    conn.commit()
    row = conn.execute("SELECT * FROM tests WHERE test_code = ?", (test_code,)).fetchone()
    conn.close()
    return dict(row)


def get_test(test_code: str) -> Optional[dict]:
    """Get a test by code."""
    conn = get_db()
    row = conn.execute("SELECT * FROM tests WHERE test_code = ?", (test_code,)).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["questions"] = json.loads(result["questions"])
        return result
    return None


def list_tests() -> list[dict]:
    """List all tests."""
    conn = get_db()
    rows = conn.execute("SELECT test_code, grade_level, title, created_at, updated_at FROM tests ORDER BY test_code").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Prompts ---

def upsert_prompt(test_code: str, prompt_text: str, version: str = "V2") -> dict:
    """Create or update the active prompt for a test code."""
    conn = get_db()
    # Deactivate existing prompts for this test
    conn.execute(
        "UPDATE prompts SET active = 0 WHERE test_code = ? AND active = 1",
        (test_code,),
    )
    conn.execute(
        "INSERT INTO prompts (test_code, prompt_text, version) VALUES (?, ?, ?)",
        (test_code, prompt_text, version),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM prompts WHERE test_code = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (test_code,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_active_prompt(test_code: str) -> Optional[dict]:
    """Get the active prompt for a test code."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM prompts WHERE test_code = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (test_code,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Grading Jobs ---

def create_job(student_name: str, test_code: str, responses: dict, num_runs: int = 3) -> str:
    """Create a new grading job. Returns job ID."""
    job_id = uuid.uuid4().hex[:12]
    conn = get_db()
    conn.execute(
        "INSERT INTO grading_jobs (id, student_name, test_code, responses, num_runs) VALUES (?, ?, ?, ?, ?)",
        (job_id, student_name, test_code, json.dumps(responses, ensure_ascii=False), num_runs),
    )
    conn.commit()
    conn.close()
    return job_id


def update_job_status(job_id: str, status: str, error: str = None):
    """Update a job's status."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    if status == "running":
        conn.execute(
            "UPDATE grading_jobs SET status = ?, started_at = ? WHERE id = ?",
            (status, now, job_id),
        )
    elif status in ("complete", "failed"):
        conn.execute(
            "UPDATE grading_jobs SET status = ?, completed_at = ?, error = ? WHERE id = ?",
            (status, now, error, job_id),
        )
    else:
        conn.execute(
            "UPDATE grading_jobs SET status = ? WHERE id = ?",
            (status, job_id),
        )
    conn.commit()
    conn.close()


def list_jobs(limit: int = 50, status: str = None, search: str = None) -> list[dict]:
    """List recent grading jobs with optional filters."""
    conn = get_db()
    query = "SELECT id, student_name, test_code, num_runs, status, created_at, started_at, completed_at FROM grading_jobs"
    params = []
    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if search:
        conditions.append("(student_name LIKE ? OR test_code LIKE ? OR id LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job(job_id: str) -> Optional[dict]:
    """Get a job by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM grading_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["responses"] = json.loads(result["responses"])
        return result
    return None


def save_question_result(job_id: str, consensus_result) -> None:
    """Save a ConsensusResult to the database."""
    conn = get_db()
    fs = consensus_result.final_score
    run_details = json.dumps([r.to_dict() for r in consensus_result.runs], ensure_ascii=False)
    conn.execute("""
        INSERT INTO grading_results
        (job_id, question, final_ideas_score, final_ideas_max,
         final_conventions_score, final_conventions_max,
         final_total_score, final_total_max, final_feedback,
         consensus_method, run_details, judge_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, consensus_result.question,
        fs.ideas_score, fs.ideas_max,
        fs.conventions_score, fs.conventions_max,
        fs.total_score, fs.total_max,
        fs.feedback, consensus_result.consensus_method.value,
        run_details, consensus_result.judge_reasoning,
    ))
    conn.commit()
    conn.close()


def get_job_results(job_id: str) -> list[dict]:
    """Get all question results for a job."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM grading_results WHERE job_id = ? ORDER BY question",
        (job_id,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["run_details"] = json.loads(d["run_details"])
        results.append(d)
    return results
