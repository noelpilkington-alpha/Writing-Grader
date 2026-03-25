"""Prompt and test content loading."""

import json
from pathlib import Path
from typing import Optional


def load_prompt(test_code: str, prompts_dir: Path) -> str:
    """Load a V2 grading prompt for the given test code.

    Looks for: {prompts_dir}/{test_code} CJ V2.txt
    """
    path = prompts_dir / f"{test_code} CJ V2.txt"
    if not path.exists():
        raise FileNotFoundError(f"No grading prompt found at {path}")
    return path.read_text(encoding="utf-8")


def load_test_content(test_code: str, cache_path: Path) -> Optional[dict]:
    """Load cached test content (passage, questions, q11_article).

    Returns dict with keys: passage, questions, q11_article (optional).
    Returns None if test_code is not in cache.
    """
    if not cache_path.exists():
        return None
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    return cache.get(test_code)


def load_q11_article(test_code: str, cache_path: Path) -> Optional[str]:
    """Load the separate Q11 article for G3-G5 tests."""
    grade_num = int(test_code.split(".")[0][1:])
    if grade_num >= 6:
        return None
    entry = load_test_content(test_code, cache_path)
    if entry is None:
        return None
    return entry.get("q11_article")


def build_grading_passage(passage: str, q11_article: Optional[str], qnum: int) -> str:
    """Build the passage to send for grading.

    For Q11 on G3-G5 tests, appends the separate Q11 article.
    """
    if qnum == 11 and q11_article:
        return passage + "\n\nQ11 ARTICLE:\n" + q11_article
    return passage
