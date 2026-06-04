"""
Feedback learning module.

Uses dismissed suggestion history to re-weight future review prompts
and suppress findings that match previously dismissed patterns.
"""

from __future__ import annotations

import logging

from src.feedback.store import FeedbackStore

logger = logging.getLogger(__name__)


class FeedbackLearner:
    """
    Learns from dismissed suggestions to improve future reviews.

    Uses simple text matching and category weighting to suppress
    findings similar to previously dismissed ones.

    Usage:
        learner = FeedbackLearner()
        context = learner.build_suppression_context("owner/repo")
        should_skip = learner.should_suppress(finding, dismissed_patterns)
    """

    def __init__(self, store: FeedbackStore | None = None):
        self._store = store or FeedbackStore()

    def build_suppression_context(self, repo: str) -> str:
        """
        Build a prompt section listing patterns to avoid.

        This is injected into the review system prompt so Claude
        knows which types of suggestions to skip.

        Args:
            repo: Repository in 'owner/repo' format.

        Returns:
            A formatted string listing dismissed patterns, or "None"
            if no feedback exists.
        """
        patterns = self._store.get_dismissed_patterns(repo, limit=30)

        if not patterns:
            return "None"

        # Group by similarity (simple keyword overlap)
        unique_patterns: list[str] = []
        for p in patterns:
            # Check if this pattern is too similar to one we already have
            is_duplicate = False
            for existing in unique_patterns:
                if self._text_similarity(p, existing) > 0.7:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_patterns.append(p)

        # Format for prompt injection
        lines = []
        for i, pattern in enumerate(unique_patterns[:15], 1):
            # Truncate long patterns
            truncated = pattern[:150] + "..." if len(pattern) > 150 else pattern
            lines.append(f"{i}. {truncated}")

        # Also include category statistics
        category_stats = self._store.get_dismissed_by_category(repo)
        if category_stats:
            lines.append("")
            lines.append("Categories most frequently dismissed:")
            for cat, count in list(category_stats.items())[:5]:
                lines.append(f"  - {cat}: {count} times")

        return "\n".join(lines)

    def should_suppress(
        self,
        finding: dict,
        dismissed_patterns: list[str],
        threshold: float = 0.6,
    ) -> bool:
        """
        Check if a finding should be suppressed based on past feedback.

        Uses simple text similarity between the finding's title/body
        and previously dismissed suggestion texts.

        Args:
            finding: A review finding dict with 'title' and 'body'.
            dismissed_patterns: List of dismissed suggestion texts.
            threshold: Similarity threshold (0-1). Higher = stricter matching.

        Returns:
            True if the finding should be suppressed.
        """
        if not dismissed_patterns:
            return False

        finding_text = f"{finding.get('title', '')} {finding.get('body', '')}"

        for pattern in dismissed_patterns:
            similarity = self._text_similarity(finding_text, pattern)
            if similarity > threshold:
                logger.debug(
                    f"Suppressing finding '{finding.get('title', '')}' "
                    f"(similarity={similarity:.2f} with dismissed pattern)"
                )
                return True

        return False

    def get_review_stats(self, repo: str) -> dict:
        """
        Get review statistics for a repository.

        Returns:
            Dict with average_score, total_reviews, total_dismissed,
            and category breakdown.
        """
        avg_score = self._store.get_average_score(repo)
        history = self._store.get_review_history(repo)
        dismissed_stats = self._store.get_dismissed_by_category(repo)

        return {
            "average_score": round(avg_score, 1) if avg_score else None,
            "total_reviews": len(history),
            "total_dismissed": sum(dismissed_stats.values()),
            "dismissed_by_category": dismissed_stats,
            "recent_reviews": history[:5],
        }

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """
        Simple word-overlap similarity (Jaccard index).

        This is intentionally simple — for production, you'd use
        embedding-based similarity via ChromaDB.
        """
        if not text1 or not text2:
            return 0.0

        # Normalize and tokenize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Remove very common words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "this", "that", "it", "and", "or", "not", "no", "but",
        }
        words1 -= stop_words
        words2 -= stop_words

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)
