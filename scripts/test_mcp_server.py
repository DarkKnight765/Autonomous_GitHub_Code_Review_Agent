"""
CLI script to test the MCP server tools locally.

Usage:
    python scripts/test_mcp_server.py --tool get_pr_diff --repo owner/repo --pr 1
    python scripts/test_mcp_server.py --tool list_pr_files --repo owner/repo --pr 1
    python scripts/test_mcp_server.py --tool get_file_content --repo owner/repo --path README.md
    python scripts/test_mcp_server.py --tool search_codebase --query "database connection"
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Test MCP server tools locally without running the full server"
    )
    parser.add_argument(
        "--tool",
        required=True,
        choices=[
            "get_pr_diff", "get_pr_metadata", "get_file_content",
            "post_review_comment", "post_pr_summary", "search_codebase",
            "list_pr_files",
        ],
        help="MCP tool to test",
    )
    parser.add_argument("--repo", help="Repository in 'owner/repo' format")
    parser.add_argument("--pr", type=int, help="Pull request number")
    parser.add_argument("--path", help="File path (for get_file_content)")
    parser.add_argument("--ref", default="main", help="Git ref (default: main)")
    parser.add_argument("--query", help="Search query (for search_codebase)")
    parser.add_argument("--body", help="Comment body (for post tools)")
    parser.add_argument("--position", type=int, help="Diff position (for post_review_comment)")

    args = parser.parse_args()
    setup_logging("INFO")

    logging.getLogger(__name__)

    # Import the MCP server tools
    from src.mcp_server.server import (
        get_file_content,
        get_pr_diff,
        get_pr_metadata,
        list_pr_files,
        post_pr_summary,
        post_review_comment,
        search_codebase,
    )

    print(f"\n🔧 Testing tool: {args.tool}\n")

    try:
        if args.tool == "get_pr_diff":
            result = get_pr_diff(repo=args.repo, pr_number=args.pr)
        elif args.tool == "get_pr_metadata":
            result = get_pr_metadata(repo=args.repo, pr_number=args.pr)
        elif args.tool == "get_file_content":
            result = get_file_content(repo=args.repo, path=args.path, ref=args.ref)
        elif args.tool == "list_pr_files":
            result = list_pr_files(repo=args.repo, pr_number=args.pr)
        elif args.tool == "search_codebase":
            result = search_codebase(query=args.query)
        elif args.tool == "post_review_comment":
            result = post_review_comment(
                repo=args.repo,
                pr_number=args.pr,
                path=args.path,
                position=args.position,
                body=args.body or "Test comment from AGCRA",
            )
        elif args.tool == "post_pr_summary":
            result = post_pr_summary(
                repo=args.repo,
                pr_number=args.pr,
                body=args.body or "Test summary from AGCRA",
            )
        else:
            print(f"Unknown tool: {args.tool}")
            return

        print("─" * 60)
        print(result)
        print("─" * 60)
        print("\n✅ Tool executed successfully")

    except Exception as e:
        print(f"\n❌ Tool failed: {e}")
        raise


if __name__ == "__main__":
    main()
