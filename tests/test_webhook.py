"""Tests for the webhook listener."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.webhook.app import create_app


@pytest.fixture
def app():
    """Create a test app with empty webhook secret so signature verification is skipped."""
    test_settings = Settings(
        github_token="test-token",
        anthropic_api_key="test-key",
        github_webhook_secret="",  # empty = skip verification in tests
    )
    return create_app(settings=test_settings)


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


# ── Health Check ────────────────────────────────────────────────

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AGCRA"


# ── Webhook — Non-PR Events ────────────────────────────────────

def test_webhook_ignores_non_pr_events(client):
    response = client.post(
        "/webhook",
        json={"action": "created"},
        headers={"X-GitHub-Event": "issues"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Ignoring event type" in data["message"]


# ── Webhook — PR Events ────────────────────────────────────────

SAMPLE_PR_PAYLOAD = {
    "action": "opened",
    "number": 1,
    "pull_request": {
        "number": 1,
        "title": "Add new feature",
        "body": "This PR adds a cool feature",
        "state": "open",
        "user": {"login": "testuser", "id": 123, "avatar_url": ""},
        "head": {"ref": "feature-branch", "sha": "abc123", "label": ""},
        "base": {"ref": "main", "sha": "def456", "label": ""},
        "additions": 50,
        "deletions": 10,
        "changed_files": 3,
        "draft": False,
    },
    "repository": {
        "id": 456,
        "full_name": "owner/repo",
        "name": "repo",
        "private": False,
        "default_branch": "main",
    },
    "sender": {"login": "testuser", "id": 123, "avatar_url": ""},
}


def test_webhook_accepts_pr_opened(client):
    response = client.post(
        "/webhook",
        json=SAMPLE_PR_PAYLOAD,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["review_triggered"] is True
    assert data["pr_number"] == 1


def test_webhook_skips_draft_pr(client):
    payload = json.loads(json.dumps(SAMPLE_PR_PAYLOAD))
    payload["pull_request"]["draft"] = True

    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["review_triggered"] is False


def test_webhook_skips_closed_pr(client):
    payload = json.loads(json.dumps(SAMPLE_PR_PAYLOAD))
    payload["action"] = "closed"

    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["review_triggered"] is False


def test_webhook_handles_invalid_payload(client):
    response = client.post(
        "/webhook",
        json={"invalid": "data"},
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 400
