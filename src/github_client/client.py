"""
GitHub API client wrapper using PyGithub.

Provides a clean interface for all GitHub operations needed by the
review pipeline: fetching PRs, reading diffs, posting review comments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from github import Auth, Github
from github.PullRequest import PullRequest
from github.Repository import Repository

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents a single file changed in a pull request."""

    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    changes: int
    patch: str | None  # unified diff patch (None for binary files)
    previous_filename: str | None = None  # for renames


@dataclass
class ReviewComment:
    """An inline review comment to post on a specific line."""

    path: str  # file path relative to repo root
    position: int  # line position in the diff (NOT the absolute line number)
    body: str  # markdown comment body


@dataclass
class ReviewSubmission:
    """A complete review to submit on a pull request."""

    body: str  # summary comment
    event: str = "COMMENT"  # COMMENT, APPROVE, REQUEST_CHANGES
    comments: list[ReviewComment] = field(default_factory=list)


class GitHubReviewClient:
    """
    Wraps PyGithub for all GitHub operations needed by AGCRA.

    Usage:
        client = GitHubReviewClient(token="ghp_...")
        diff = client.get_pr_diff("owner/repo", 42)
        client.post_review("owner/repo", 42, submission)
    """

    def __init__(self, token: str) -> None:
        self._gh = Github(auth=Auth.Token(token))
        logger.debug("GitHubReviewClient initialized")

    def _get_repo(self, repo_full_name: str) -> Repository:
        """Get a repository by full name (owner/repo)."""
        return self._gh.get_repo(repo_full_name)

    def _get_pr(self, repo_full_name: str, pr_number: int) -> PullRequest:
        """Get a pull request by repository and number."""
        repo = self._get_repo(repo_full_name)
        return repo.get_pull(pr_number)

    # ── Read Operations ─────────────────────────────────────────

    def get_pr_metadata(self, repo_full_name: str, pr_number: int) -> dict:
        """
        Get pull request metadata.

        Returns:
            Dict with title, body, author, branches, stats, etc.
        """
        pr = self._get_pr(repo_full_name, pr_number)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "author": pr.user.login,
            "head_ref": pr.head.ref,
            "base_ref": pr.base.ref,
            "head_sha": pr.head.sha,
            "base_sha": pr.base.sha,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "html_url": pr.html_url,
            "created_at": str(pr.created_at),
            "draft": pr.draft,
        }

    def get_pr_diff(self, repo_full_name: str, pr_number: int) -> list[FileChange]:
        """
        Get all file changes (diffs) for a pull request.

        Returns:
            List of FileChange objects with patch data for each changed file.
        """
        pr = self._get_pr(repo_full_name, pr_number)
        files = pr.get_files()

        changes: list[FileChange] = []
        for f in files:
            changes.append(
                FileChange(
                    filename=f.filename,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    changes=f.changes,
                    patch=f.patch,  # None for binary files
                    previous_filename=f.previous_filename,
                )
            )

        logger.info(
            f"Fetched {len(changes)} file changes for "
            f"{repo_full_name} PR #{pr_number}"
        )
        return changes

    def get_pr_file_list(self, repo_full_name: str, pr_number: int) -> list[str]:
        """Get just the list of changed file paths in a PR."""
        pr = self._get_pr(repo_full_name, pr_number)
        return [f.filename for f in pr.get_files()]

    def get_file_content(
        self,
        repo_full_name: str,
        file_path: str,
        ref: str = "main",
    ) -> str | None:
        """
        Get the content of a file at a specific ref (branch/commit).

        Returns:
            The decoded file content as a string, or None if the file
            doesn't exist or is binary.
        """
        try:
            repo = self._get_repo(repo_full_name)
            content = repo.get_contents(file_path, ref=ref)

            # get_contents can return a list for directories
            if isinstance(content, list):
                logger.warning(f"{file_path} is a directory, not a file")
                return None

            return content.decoded_content.decode("utf-8")

        except Exception as e:
            logger.warning(f"Could not fetch {file_path}@{ref}: {e}")
            return None

    # ── Write Operations ────────────────────────────────────────

    def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        submission: ReviewSubmission,
    ) -> None:
        """
        Post a complete review on a pull request.

        This creates a review with an overall comment and optional
        inline comments on specific lines.
        """
        pr = self._get_pr(repo_full_name, pr_number)

        # Build the comments list for PyGithub
        comments = []
        for c in submission.comments:
            comments.append(
                {
                    "path": c.path,
                    "position": c.position,
                    "body": c.body,
                }
            )

        # Post the review
        pr.create_review(
            body=submission.body,
            event=submission.event,
            comments=comments if comments else [],
        )

        logger.info(
            f"✅ Posted review on {repo_full_name} PR #{pr_number} "
            f"({len(comments)} inline comments, event={submission.event})"
        )

    def post_issue_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> None:
        """
        Post a standalone comment on a PR (not tied to a review).

        Useful for posting summary reports that don't need to be
        part of a formal review.
        """
        pr = self._get_pr(repo_full_name, pr_number)
        pr.create_issue_comment(body)

        logger.info(
            f"💬 Posted issue comment on {repo_full_name} PR #{pr_number}"
        )

    # ── Cleanup ─────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying GitHub connection."""
        self._gh.close()
        logger.debug("GitHubReviewClient closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
