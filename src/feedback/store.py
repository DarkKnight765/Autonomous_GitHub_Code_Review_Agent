"""
Feedback storage using SQLite.

Persists dismissed review suggestions and review history so the agent
can learn from feedback and avoid repeating unhelpful suggestions.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, datetime

from src.config import load_settings

logger = logging.getLogger(__name__)


class FeedbackStore:
    """
    SQLite-backed storage for review feedback and history.

    Tables:
        - dismissed_suggestions: suggestions users dismissed
        - review_history: metadata about past reviews

    Usage:
        store = FeedbackStore()
        store.record_dismissed("owner/repo", 42, "Check for null values", "style")
        patterns = store.get_dismissed_patterns("owner/repo")
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            try:
                settings = load_settings()
                db_path = settings.feedback_db_path
            except Exception:
                db_path = "./data/feedback.db"

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

        logger.debug(f"FeedbackStore initialized at {db_path}")

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS dismissed_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                file_path TEXT DEFAULT '',
                suggestion_text TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                quality_score INTEGER DEFAULT 0,
                findings_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_dismissed_repo
                ON dismissed_suggestions(repo);

            CREATE INDEX IF NOT EXISTS idx_history_repo
                ON review_history(repo);
        """)
        self._conn.commit()

    # ── Dismissed Suggestions ───────────────────────────────────

    def record_dismissed(
        self,
        repo: str,
        pr_number: int,
        suggestion_text: str,
        category: str = "general",
        file_path: str = "",
    ) -> None:
        """Record a suggestion that was dismissed by a reviewer."""
        self._conn.execute(
            """
            INSERT INTO dismissed_suggestions
                (repo, pr_number, file_path, suggestion_text, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                repo,
                pr_number,
                file_path,
                suggestion_text,
                category,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

        logger.debug(
            f"Recorded dismissed suggestion for {repo} PR #{pr_number}: "
            f"{suggestion_text[:60]}..."
        )

    def get_dismissed_patterns(self, repo: str, limit: int = 50) -> list[str]:
        """
        Get recently dismissed suggestion patterns for a repo.

        Returns:
            List of suggestion text strings, most recent first.
        """
        cursor = self._conn.execute(
            """
            SELECT DISTINCT suggestion_text
            FROM dismissed_suggestions
            WHERE repo = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (repo, limit),
        )
        return [row["suggestion_text"] for row in cursor.fetchall()]

    def get_dismissed_by_category(self, repo: str) -> dict[str, int]:
        """Get count of dismissed suggestions by category."""
        cursor = self._conn.execute(
            """
            SELECT category, COUNT(*) as count
            FROM dismissed_suggestions
            WHERE repo = ?
            GROUP BY category
            ORDER BY count DESC
            """,
            (repo,),
        )
        return {row["category"]: row["count"] for row in cursor.fetchall()}

    # ── Review History ──────────────────────────────────────────

    def record_review(
        self,
        repo: str,
        pr_number: int,
        quality_score: int,
        findings_count: int,
    ) -> None:
        """Record metadata about a completed review."""
        self._conn.execute(
            """
            INSERT INTO review_history
                (repo, pr_number, quality_score, findings_count, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                repo,
                pr_number,
                quality_score,
                findings_count,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

        logger.debug(
            f"Recorded review for {repo} PR #{pr_number}: "
            f"score={quality_score}, findings={findings_count}"
        )

    def get_review_history(
        self, repo: str, limit: int = 20
    ) -> list[dict]:
        """Get recent review history for a repo."""
        cursor = self._conn.execute(
            """
            SELECT pr_number, quality_score, findings_count, created_at
            FROM review_history
            WHERE repo = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (repo, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_average_score(self, repo: str) -> float | None:
        """Get the average quality score for a repo."""
        cursor = self._conn.execute(
            """
            SELECT AVG(quality_score) as avg_score
            FROM review_history
            WHERE repo = ?
            """,
            (repo,),
        )
        row = cursor.fetchone()
        return row["avg_score"] if row and row["avg_score"] else None

    # ── Cleanup ─────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
