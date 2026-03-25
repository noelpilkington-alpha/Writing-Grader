"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# --- Grading ---

class GradeRequest(BaseModel):
    """Request to grade a student submission."""
    student_name: str = Field(..., description="Student's full name")
    test_code: str = Field(..., description="Test code, e.g. G3.1")
    responses: dict[str, str] = Field(
        ...,
        description="Question responses keyed by question number (as string). E.g. {'1': 'answer...', '2': '...'}"
    )
    num_runs: int = Field(default=3, ge=1, le=5, description="Number of parallel grading runs (1-5)")


class GradeResponse(BaseModel):
    """Response after submitting a grading job."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Status of a grading job."""
    job_id: str
    student_name: str
    test_code: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class QuestionResultResponse(BaseModel):
    """Result for a single question."""
    question: int
    ideas_score: int
    ideas_max: int
    conventions_score: int
    conventions_max: int
    total_score: int
    total_max: int
    feedback: str
    consensus_method: str
    run_scores: list[int] = Field(default_factory=list, description="Total scores from each run")
    judge_reasoning: str = ""


class JobResultResponse(BaseModel):
    """Complete grading result for a job."""
    job_id: str
    student_name: str
    test_code: str
    status: str
    total_score: int
    total_max: int
    questions: list[QuestionResultResponse]


# --- Tests ---

class TestCreateRequest(BaseModel):
    """Request to create or update a test."""
    test_code: str = Field(..., description="Test code, e.g. G3.1")
    grade_level: int = Field(..., ge=3, le=8, description="Grade level (3-8)")
    title: str = Field(default="", description="Test title/description")
    passage: str = Field(default="", description="Reading passage text")
    questions: dict[str, str] = Field(
        default_factory=dict,
        description="Question texts keyed by number. E.g. {'1': 'Revise sentence 2...'}"
    )
    q11_article: Optional[str] = Field(default=None, description="Separate Q11 article text (G3-G5)")


class TestResponse(BaseModel):
    """Response for a test."""
    test_code: str
    grade_level: int
    title: str
    has_passage: bool
    question_count: int
    has_q11_article: bool
    created_at: str
    updated_at: str


class TestListResponse(BaseModel):
    """List of tests."""
    tests: list[TestResponse]


# --- Prompts ---

class PromptUploadRequest(BaseModel):
    """Request to upload a grading prompt."""
    prompt_text: str = Field(..., description="Full grading prompt text")
    version: str = Field(default="V2", description="Prompt version label")


class PromptResponse(BaseModel):
    """Response for a prompt."""
    test_code: str
    version: str
    active: bool
    created_at: str
    prompt_length: int


# --- API Keys ---

class ApiKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., description="Name/label for this API key")


class ApiKeyResponse(BaseModel):
    """Response after creating an API key."""
    key: str
    name: str
    message: str
