"""
FastAPI webhook application.

Receives GitHub pull_request webhook events, validates the payload,
and dispatches reviews to the LangGraph pipeline.
"""

from __future__ import annotations

import json
import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import Settings, load_settings, setup_logging
from src.webhook.models import PullRequestEvent, WebhookResponse
from src.webhook.security import verify_webhook_signature

logger = logging.getLogger(__name__)

# ── App Factory ─────────────────────────────────────────────────


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="AGCRA — Autonomous GitHub Code Review Agent",
        description="Receives GitHub webhook events and triggers AI-powered code reviews",
        version="0.1.0",
    )

    # Store settings on app state for access in routes
    if settings is None:
        try:
            settings = load_settings()
        except Exception as e:
            logger.warning(f"Could not load settings: {e}. Using defaults for startup.")
            settings = None

    app.state.settings = settings
    app.state.review_count = 0

    # ── Routes ──────────────────────────────────────────────────

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "AGCRA",
            "version": "0.1.0",
            "reviews_processed": app.state.review_count,
        }

    @app.post("/webhook", response_model=WebhookResponse)
    async def handle_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        """
        Handle incoming GitHub webhook events.

        Validates the HMAC signature, parses the pull_request event,
        and dispatches a review if the event is reviewable.
        """
        settings: Settings | None = app.state.settings

        # 1. Verify webhook signature
        webhook_secret = settings.github_webhook_secret if settings else ""
        body = await verify_webhook_signature(request, webhook_secret)

        # 2. Check event type
        event_type = request.headers.get("X-GitHub-Event", "")
        if event_type != "pull_request":
            logger.info(f"Ignoring non-PR event: {event_type}")
            return WebhookResponse(message=f"Ignoring event type: {event_type}")

        # 3. Parse payload
        try:
            payload = json.loads(body)
            event = PullRequestEvent(**payload)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return JSONResponse(
                status_code=400,
                content={"ok": False, "message": f"Invalid payload: {e}"},
            )

        # 4. Check if this PR event should trigger a review
        if not event.is_reviewable:
            logger.info(
                f"Skipping PR #{event.pr_number} in {event.repo_full_name} "
                f"(action={event.action}, state={event.pull_request.state}, "
                f"draft={event.pull_request.draft})"
            )
            return WebhookResponse(
                message=f"PR #{event.pr_number} not reviewable (action={event.action})",
                pr_number=event.pr_number,
            )

        # 5. Dispatch review as a background task
        logger.info(
            f"🚀 Triggering review for PR #{event.pr_number} "
            f"in {event.repo_full_name} "
            f"({event.pull_request.additions}+/{event.pull_request.deletions}-)"
        )

        background_tasks.add_task(
            _run_review,
            repo=event.repo_full_name,
            pr_number=event.pr_number,
            settings=settings,
        )

        app.state.review_count += 1

        return WebhookResponse(
            message=f"Review triggered for PR #{event.pr_number}",
            review_triggered=True,
            pr_number=event.pr_number,
        )

    return app


async def _run_review(repo: str, pr_number: int, settings: Settings | None) -> None:
    """
    Execute the review pipeline for a pull request.

    This runs as a FastAPI background task so the webhook responds immediately.
    The actual LangGraph pipeline will be wired in Phase 8.
    """
    logger.info(f"📝 Starting review for {repo} PR #{pr_number}...")

    try:
        # Phase 8: This will invoke the LangGraph review pipeline
        # For now, just log the event
        from src.review.graph import review_graph  # noqa: F811

        result = await review_graph.ainvoke(
            {
                "repo": repo,
                "pr_number": pr_number,
            }
        )

        logger.info(
            f"✅ Review complete for {repo} PR #{pr_number} — "
            f"Quality score: {result.get('quality_score', 'N/A')}/10, "
            f"Findings: {len(result.get('findings', []))}"
        )

    except ImportError:
        # Review pipeline not yet built — log placeholder
        logger.info(
            f"⏳ Review pipeline not yet available. "
            f"Would review {repo} PR #{pr_number} here."
        )
    except Exception as e:
        logger.error(f"❌ Review failed for {repo} PR #{pr_number}: {e}", exc_info=True)


# ── Entrypoint ──────────────────────────────────────────────────

# Create the default app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    setup_logging("INFO")
    logger.info("Starting AGCRA webhook listener...")
    uvicorn.run(
        "src.webhook.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
