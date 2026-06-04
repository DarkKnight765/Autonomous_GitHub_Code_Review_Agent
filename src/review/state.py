"""
LangGraph state definition for the review pipeline.

Defines the typed state that flows through every node in the
review graph. Uses Annotated reducers for fields that accumulate
data across nodes.
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def _list_reducer(existing: list, new: list) -> list:
    """Reducer that appends new items to existing list (never overwrites)."""
    return existing + new


class ReviewFinding(TypedDict):
    """A single review finding from Claude's analysis."""

    file: str  # path to file
    line: int  # line number in new file version
    position: int  # diff position for GitHub API
    severity: str  # high, medium, low
    category: str  # bug, security, performance, style, maintainability
    title: str  # short one-line description
    body: str  # detailed explanation with suggestion
    suggested_fix: str  # optional code suggestion


class ReviewState(TypedDict, total=False):
    """
    Complete state flowing through the LangGraph review pipeline.

    Fields marked with Annotated[..., reducer] accumulate data
    across nodes instead of being overwritten.
    """

    # ── Input (set at invocation) ───────────────────────────────
    repo: str  # "owner/repo"
    pr_number: int

    # ── Fetched Data (set by fetch nodes) ───────────────────────
    diff_chunks: list[dict]  # parsed diff chunks per file
    pr_metadata: dict  # title, body, author, branches, stats
    file_contents: dict  # {file_path: full_file_content}

    # ── RAG Context (set by query_rag node) ─────────────────────
    similar_patterns: list[str]  # related code from ChromaDB

    # ── Feedback Context (set by load_feedback node) ────────────
    past_dismissed: list[str]  # patterns to avoid repeating

    # ── Review Results (accumulated by review nodes) ────────────
    findings: Annotated[list[dict], _list_reducer]

    # ── Output (set by aggregate/summary nodes) ─────────────────
    summary: str  # final markdown summary comment
    quality_score: int  # 1-10 overall score
    top_concerns: list[str]  # top 3 issues
    review_posted: bool  # whether results were posted to GitHub

    # ── Error tracking ──────────────────────────────────────────
    errors: Annotated[list[str], _list_reducer]
