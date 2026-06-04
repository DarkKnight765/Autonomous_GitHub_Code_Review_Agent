"""Tests for the feedback store and learning module."""

from __future__ import annotations

import os
import tempfile

import pytest

from src.feedback.learning import FeedbackLearner
from src.feedback.store import FeedbackStore


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create a FeedbackStore with a temp database."""
    s = FeedbackStore(db_path=temp_db)
    yield s
    s.close()


# ── FeedbackStore Tests ─────────────────────────────────────────

def test_record_and_retrieve_dismissed(store):
    store.record_dismissed(
        repo="owner/repo",
        pr_number=1,
        suggestion_text="Consider using enumerate",
        category="style",
    )

    patterns = store.get_dismissed_patterns("owner/repo")
    assert len(patterns) == 1
    assert "enumerate" in patterns[0]


def test_dismissed_patterns_are_repo_specific(store):
    store.record_dismissed("repo-a", 1, "Suggestion A", "style")
    store.record_dismissed("repo-b", 1, "Suggestion B", "style")

    patterns_a = store.get_dismissed_patterns("repo-a")
    patterns_b = store.get_dismissed_patterns("repo-b")

    assert len(patterns_a) == 1
    assert len(patterns_b) == 1
    assert "Suggestion A" in patterns_a[0]
    assert "Suggestion B" in patterns_b[0]


def test_record_and_retrieve_review_history(store):
    store.record_review("owner/repo", pr_number=1, quality_score=8, findings_count=3)
    store.record_review("owner/repo", pr_number=2, quality_score=6, findings_count=7)

    history = store.get_review_history("owner/repo")
    assert len(history) == 2


def test_average_score(store):
    store.record_review("owner/repo", 1, quality_score=8, findings_count=2)
    store.record_review("owner/repo", 2, quality_score=6, findings_count=5)

    avg = store.get_average_score("owner/repo")
    assert avg == 7.0


def test_average_score_empty_repo(store):
    avg = store.get_average_score("nonexistent/repo")
    assert avg is None


def test_dismissed_by_category(store):
    store.record_dismissed("r", 1, "s1", "style")
    store.record_dismissed("r", 1, "s2", "style")
    store.record_dismissed("r", 1, "s3", "bug")

    categories = store.get_dismissed_by_category("r")
    assert categories["style"] == 2
    assert categories["bug"] == 1


# ── FeedbackLearner Tests ───────────────────────────────────────

def test_text_similarity_identical():
    sim = FeedbackLearner._text_similarity(
        "consider using enumerate here",
        "consider using enumerate here",
    )
    assert sim == 1.0


def test_text_similarity_different():
    sim = FeedbackLearner._text_similarity(
        "fix null pointer exception",
        "optimize database query performance",
    )
    assert sim < 0.3


def test_text_similarity_empty():
    assert FeedbackLearner._text_similarity("", "something") == 0.0
    assert FeedbackLearner._text_similarity("", "") == 0.0


def test_should_suppress_matching_pattern(temp_db):
    store = FeedbackStore(db_path=temp_db)
    learner = FeedbackLearner(store=store)

    finding = {
        "title": "Consider using enumerate instead of range(len())",
        "body": "Using enumerate is more Pythonic than range(len())",
    }
    dismissed = ["Consider using enumerate instead of range(len()) for iteration"]

    assert learner.should_suppress(finding, dismissed, threshold=0.4) is True
    store.close()


def test_should_not_suppress_unrelated_pattern(temp_db):
    store = FeedbackStore(db_path=temp_db)
    learner = FeedbackLearner(store=store)

    finding = {
        "title": "SQL injection vulnerability",
        "body": "User input is not sanitized before SQL query",
    }
    dismissed = ["Consider using enumerate instead of range(len())"]

    assert learner.should_suppress(finding, dismissed) is False
    store.close()
