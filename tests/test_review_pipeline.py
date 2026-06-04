"""Tests for the review pipeline state and helpers."""

from __future__ import annotations

from src.review.state import ReviewState, _list_reducer


def test_list_reducer_appends():
    result = _list_reducer([1, 2], [3, 4])
    assert result == [1, 2, 3, 4]


def test_list_reducer_empty():
    result = _list_reducer([], [1])
    assert result == [1]


def test_list_reducer_both_empty():
    result = _list_reducer([], [])
    assert result == []


def test_review_state_structure():
    """Verify ReviewState can be instantiated with minimal fields."""
    state: ReviewState = {
        "repo": "owner/repo",
        "pr_number": 42,
    }
    assert state["repo"] == "owner/repo"
    assert state["pr_number"] == 42
