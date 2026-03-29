"""Data models for the grading engine."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class ConsensusMethod(str, Enum):
    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    JUDGE = "judge"
    SINGLE = "single"  # fallback / only one valid run


@dataclass
class QuestionScore:
    """Score for a single grading run of one question."""
    question: int
    ideas_score: int
    ideas_max: int
    conventions_score: int
    conventions_max: int
    total_score: int
    total_max: int
    feedback: str
    internal_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> QuestionScore:
        return cls(
            question=d.get("question", 0),
            ideas_score=d.get("ideas_score", 0),
            ideas_max=d.get("ideas_max", 0),
            conventions_score=d.get("conventions_score", 0),
            conventions_max=d.get("conventions_max", 0),
            total_score=d.get("total_score", 0),
            total_max=d.get("total_max", 0),
            feedback=d.get("feedback", ""),
            internal_notes=d.get("internal_notes", ""),
        )

    @classmethod
    def blank(cls, qnum: int, max_score: int) -> QuestionScore:
        ideas_max, conv_max = sub_maxes(qnum)
        return cls(
            question=qnum,
            ideas_score=0, ideas_max=ideas_max,
            conventions_score=0, conventions_max=conv_max,
            total_score=0, total_max=max_score,
            feedback="It looks like this question was left blank. Give it a try next time — you can do it!",
            internal_notes="No response provided.",
        )

    @classmethod
    def gibberish(cls, qnum: int, max_score: int) -> QuestionScore:
        ideas_max, conv_max = sub_maxes(qnum)
        return cls(
            question=qnum,
            ideas_score=0, ideas_max=ideas_max,
            conventions_score=0, conventions_max=conv_max,
            total_score=0, total_max=max_score,
            feedback=(
                "It looks like this response contains random or placeholder text "
                "rather than a written answer. Take your time and give it a real try — "
                "even a short, honest answer can earn points!"
            ),
            internal_notes="GIBBERISH_DETECTED: Response flagged as nonsense/random characters.",
        )


@dataclass
class ConsensusResult:
    """Final grading result for one question after consensus."""
    question: int
    final_score: QuestionScore
    consensus_method: ConsensusMethod
    runs: list[QuestionScore] = field(default_factory=list)
    judge_reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            **self.final_score.to_dict(),
            "consensus_method": self.consensus_method.value,
            "run_count": len(self.runs),
            "runs": [r.to_dict() for r in self.runs],
            "judge_reasoning": self.judge_reasoning,
        }


@dataclass
class StudentResult:
    """Complete grading result for one student."""
    student: str
    test_code: str
    prompt_version: str
    questions: dict[str, ConsensusResult] = field(default_factory=dict)
    total_score: int = 0
    total_max: int = 0

    def compute_totals(self):
        self.total_score = sum(q.final_score.total_score for q in self.questions.values())
        self.total_max = sum(q.final_score.total_max for q in self.questions.values())

    def to_dict(self) -> dict:
        self.compute_totals()
        return {
            "student": self.student,
            "test": self.test_code,
            "prompt_version": self.prompt_version,
            "total_score": self.total_score,
            "total_max": self.total_max,
            "questions": {k: v.to_dict() for k, v in self.questions.items()},
        }


def sub_maxes(qnum: int) -> tuple[int, int]:
    """Return (ideas_max, conventions_max) for a given question number."""
    if qnum <= 5:
        return (1, 1)
    if qnum <= 10:
        return (2, 1)
    return (15, 5)


def max_score_for(qnum: int) -> int:
    """Return the max total score for a question number."""
    if qnum <= 5:
        return 2
    if qnum <= 10:
        return 3
    return 20
