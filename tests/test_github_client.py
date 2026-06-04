"""Tests for the GitHub client."""

from __future__ import annotations

import pytest

from src.github_client.client import (
    FileChange,
    GitHubReviewClient,
    ReviewComment,
    ReviewSubmission,
)

# ── Data Class Tests ────────────────────────────────────────────

def test_file_change_creation():
    fc = FileChange(
        filename="src/main.py",
        status="modified",
        additions=10,
        deletions=5,
        changes=15,
        patch="@@ -1,3 +1,4 @@\n import os\n+import sys",
    )
    assert fc.filename == "src/main.py"
    assert fc.status == "modified"
    assert fc.additions == 10
    assert fc.patch is not None


def test_file_change_binary_file():
    fc = FileChange(
        filename="image.png",
        status="added",
        additions=0,
        deletions=0,
        changes=0,
        patch=None,  # binary files have no patch
    )
    assert fc.patch is None


def test_review_comment_creation():
    comment = ReviewComment(
        path="src/main.py",
        position=10,
        body="Consider using a constant here.",
    )
    assert comment.path == "src/main.py"
    assert comment.position == 10


def test_review_submission_defaults():
    submission = ReviewSubmission(
        body="LGTM",
    )
    assert submission.event == "COMMENT"
    assert submission.comments == []


def test_review_submission_with_comments():
    submission = ReviewSubmission(
        body="Found some issues",
        event="REQUEST_CHANGES",
        comments=[
            ReviewComment(path="a.py", position=1, body="Bug here"),
            ReviewComment(path="b.py", position=5, body="Security issue"),
        ],
    )
    assert len(submission.comments) == 2
    assert submission.event == "REQUEST_CHANGES"


# ── Client Tests (require GITHUB_TOKEN — marked for skip) ──────

@pytest.mark.skip(reason="Requires GITHUB_TOKEN — run manually")
def test_client_get_pr_metadata():
    import os
    client = GitHubReviewClient(token=os.environ["GITHUB_TOKEN"])
    metadata = client.get_pr_metadata("octocat/hello-world", 1)
    assert "title" in metadata
    assert "author" in metadata
    client.close()
