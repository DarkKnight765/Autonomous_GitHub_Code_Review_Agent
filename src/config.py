"""
Central configuration module for AGCRA.

Loads environment variables from .env file, validates required keys,
and provides typed access to all settings.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when a required configuration value is missing."""


@dataclass(frozen=True)
class Settings:
    """Typed application settings loaded from environment variables."""

    # ── GitHub ──────────────────────────────────────────────────
    github_token: str = ""
    github_webhook_secret: str = ""
    target_repo: str = ""

    # ── Anthropic / Claude ──────────────────────────────────────
    anthropic_api_key: str = ""
    review_model: str = "claude-sonnet-4-20250514"

    # ── Server ──────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # ── Storage Paths ───────────────────────────────────────────
    chroma_db_path: str = field(
        default_factory=lambda: str(_PROJECT_ROOT / "data" / "chroma_db")
    )
    feedback_db_path: str = field(
        default_factory=lambda: str(_PROJECT_ROOT / "data" / "feedback.db")
    )

    # ── Review Behavior ─────────────────────────────────────────
    review_event: str = "COMMENT"  # COMMENT or REQUEST_CHANGES
    max_findings_per_pr: int = 20
    min_severity: str = "low"  # low, medium, high

    def validate(self) -> None:
        """Validate that all required settings are present. Raises ConfigError on failure."""
        missing: list[str] = []

        if not self.github_token:
            missing.append("GITHUB_TOKEN")
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")

        if missing:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in the values."
            )

        # Validate enum-like fields
        if self.review_event not in ("COMMENT", "REQUEST_CHANGES", "APPROVE"):
            raise ConfigError(
                f"REVIEW_EVENT must be COMMENT, REQUEST_CHANGES, or APPROVE. "
                f"Got: {self.review_event}"
            )

        if self.min_severity not in ("low", "medium", "high"):
            raise ConfigError(
                f"MIN_SEVERITY must be low, medium, or high. Got: {self.min_severity}"
            )


def load_settings() -> Settings:
    """Load settings from environment variables and validate."""
    settings = Settings(
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
        target_repo=os.getenv("TARGET_REPO", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        review_model=os.getenv("REVIEW_MODEL", "claude-sonnet-4-20250514"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        chroma_db_path=os.getenv(
            "CHROMA_DB_PATH", str(_PROJECT_ROOT / "data" / "chroma_db")
        ),
        feedback_db_path=os.getenv(
            "FEEDBACK_DB_PATH", str(_PROJECT_ROOT / "data" / "feedback.db")
        ),
        review_event=os.getenv("REVIEW_EVENT", "COMMENT"),
        max_findings_per_pr=int(os.getenv("MAX_FINDINGS_PER_PR", "20")),
        min_severity=os.getenv("MIN_SEVERITY", "low"),
    )

    settings.validate()
    return settings


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
