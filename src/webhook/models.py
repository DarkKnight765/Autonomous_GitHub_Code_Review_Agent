"""
Pydantic models for GitHub webhook payloads.

Defines the structure of incoming pull_request webhook events
so we can validate and extract data safely.
"""

from __future__ import annotations

from pydantic import BaseModel


class UserData(BaseModel):
    """GitHub user information."""

    login: str
    id: int
    avatar_url: str = ""


class BranchRef(BaseModel):
    """Branch reference in a pull request (head or base)."""

    ref: str  # branch name
    sha: str  # commit SHA
    label: str = ""


class PullRequestData(BaseModel):
    """Core pull request data from the webhook payload."""

    number: int
    title: str
    body: str | None = None
    state: str = "open"
    user: UserData
    head: BranchRef
    base: BranchRef
    diff_url: str = ""
    patch_url: str = ""
    html_url: str = ""
    created_at: str = ""
    updated_at: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    mergeable: bool | None = None
    draft: bool = False


class RepositoryData(BaseModel):
    """Repository information from the webhook payload."""

    id: int
    full_name: str  # "owner/repo"
    name: str
    private: bool = False
    clone_url: str = ""
    html_url: str = ""
    default_branch: str = "main"


class PullRequestEvent(BaseModel):
    """
    Top-level GitHub pull_request webhook event.

    GitHub sends this when a PR is opened, closed, synchronized,
    edited, or undergoes other state changes.
    """

    action: str  # opened, synchronize, closed, edited, etc.
    number: int
    pull_request: PullRequestData
    repository: RepositoryData
    sender: UserData

    @property
    def is_reviewable(self) -> bool:
        """Check if this event should trigger a review."""
        return (
            self.action in ("opened", "synchronize")
            and self.pull_request.state == "open"
            and not self.pull_request.draft
        )

    @property
    def repo_full_name(self) -> str:
        return self.repository.full_name

    @property
    def pr_number(self) -> int:
        return self.pull_request.number


class WebhookResponse(BaseModel):
    """Standard response for webhook endpoint."""

    ok: bool = True
    message: str = "Event received"
    review_triggered: bool = False
    pr_number: int | None = None
