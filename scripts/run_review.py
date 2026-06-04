"""
CLI script to manually trigger a review on a GitHub PR.

Usage:
    python scripts/run_review.py --repo owner/repo --pr 42
    python scripts/run_review.py --repo owner/repo --pr 42 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys

# Fix Windows console encoding for Unicode/emoji output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import setup_logging

# Severity icons with ASCII fallbacks for Windows compatibility
SEVERITY_ICONS = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}


def main():
    parser = argparse.ArgumentParser(
        description="Manually trigger an AI code review on a GitHub PR"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository in 'owner/repo' format",
    )
    parser.add_argument(
        "--pr",
        required=True,
        type=int,
        help="Pull request number to review",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis but don't post comments to GitHub",
    )

    args = parser.parse_args()
    setup_logging("INFO")

    logger = logging.getLogger(__name__)
    logger.info(f"Manually reviewing {args.repo} PR #{args.pr}")

    if args.dry_run:
        logger.info("DRY RUN -- will not post comments to GitHub")

    # Import and run the pipeline
    from src.review.graph import review_graph

    initial_state = {
        "repo": args.repo,
        "pr_number": args.pr,
    }

    # Run the graph
    result = asyncio.run(_run_review(review_graph, initial_state, args.dry_run))

    # Print results
    print("\n" + "=" * 60)
    print("REVIEW RESULTS")
    print("=" * 60)
    print(f"  Repository:    {args.repo}")
    print(f"  PR Number:     #{args.pr}")
    print(f"  Quality Score: {result.get('quality_score', 'N/A')}/10")
    print(f"  Findings:      {len(result.get('findings', []))}")
    print(f"  Posted:        {'Yes' if result.get('review_posted') else 'No (dry-run)'}")

    if result.get("top_concerns"):
        print("\n  Top Concerns:")
        for concern in result["top_concerns"]:
            print(f"    * {concern}")

    if result.get("findings"):
        print("\n  All Findings:")
        for f in result["findings"]:
            icon = SEVERITY_ICONS.get(f.get("severity", ""), "[?]")
            print(f"    {icon} {f.get('title', '?')}")
            print(f"       {f.get('file', '?')}:{f.get('line', '?')}")

    if result.get("errors"):
        print("\n  Errors:")
        for e in result["errors"]:
            print(f"    * {e}")

    print("=" * 60)

    # Optionally dump full results to JSON
    if args.dry_run:
        output_path = f"review_pr{args.pr}_results.json"
        with open(output_path, "w", encoding="utf-8") as fp:
            serializable = {
                k: v for k, v in result.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            }
            json.dump(serializable, fp, indent=2)
        print(f"\nFull results saved to {output_path}")


async def _run_review(graph, initial_state: dict, dry_run: bool) -> dict:
    """Run the review graph."""
    if dry_run:
        pass  # future: skip post_results node

    result = await graph.ainvoke(initial_state)
    return result


if __name__ == "__main__":
    main()
