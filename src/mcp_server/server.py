"""
Custom MCP Server for GitHub Code Review.

Exposes GitHub operations as MCP tools that Claude can invoke.
This is the centerpiece for interview discussions — demonstrates
hands-on MCP experience with a real external system.

Run standalone:   python -m src.mcp_server.server
Test with:        mcp dev src/mcp_server/server.py
"""

from __future__ import annotations

import logging
import os
import sys

from github import Github
from mcp.server.fastmcp import FastMCP

# Write logs to stderr so they don't corrupt MCP's stdio JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── Initialize MCP Server ──────────────────────────────────────

mcp = FastMCP(
    "github-reviewer",
    instructions=(
        "An MCP server that provides tools for reviewing GitHub pull requests. "
        "Use these tools to fetch PR diffs, read file contents, search for "
        "similar patterns in the codebase, and post review comments."
    ),
)


def _get_github() -> Github:
    """Get an authenticated GitHub client."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    return Github(token)


# ── Tool: get_pr_diff ───────────────────────────────────────────

@mcp.tool()
def get_pr_diff(repo: str, pr_number: int) -> str:
    """
    Fetch the complete diff for a GitHub pull request.

    Args:
        repo: Repository in 'owner/repo' format (e.g., 'octocat/hello-world')
        pr_number: The pull request number

    Returns:
        The unified diff text for all changed files in the PR.
    """
    logger.info(f"Fetching diff for {repo} PR #{pr_number}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        pr = repository.get_pull(pr_number)
        files = pr.get_files()

        diff_parts = []
        for f in files:
            diff_parts.append(f"--- a/{f.filename}")
            diff_parts.append(f"+++ b/{f.filename}")
            diff_parts.append(f"Status: {f.status} | +{f.additions}/-{f.deletions}")
            if f.patch:
                diff_parts.append(f.patch)
            else:
                diff_parts.append("(binary file or no patch data)")
            diff_parts.append("")  # blank line separator

        return "\n".join(diff_parts)

    finally:
        gh.close()


# ── Tool: get_pr_metadata ──────────────────────────────────────

@mcp.tool()
def get_pr_metadata(repo: str, pr_number: int) -> str:
    """
    Get metadata for a GitHub pull request (title, author, branches, stats).

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: The pull request number

    Returns:
        Formatted metadata string with PR details.
    """
    logger.info(f"Fetching metadata for {repo} PR #{pr_number}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        pr = repository.get_pull(pr_number)

        return (
            f"PR #{pr.number}: {pr.title}\n"
            f"Author: {pr.user.login}\n"
            f"Branch: {pr.head.ref} → {pr.base.ref}\n"
            f"State: {pr.state} | Draft: {pr.draft}\n"
            f"Files changed: {pr.changed_files}\n"
            f"Additions: +{pr.additions} | Deletions: -{pr.deletions}\n"
            f"Created: {pr.created_at}\n"
            f"URL: {pr.html_url}\n"
            f"\nDescription:\n{pr.body or '(no description)'}"
        )

    finally:
        gh.close()


# ── Tool: get_file_content ──────────────────────────────────────

@mcp.tool()
def get_file_content(repo: str, path: str, ref: str = "main") -> str:
    """
    Read the content of a specific file from a GitHub repository.

    Args:
        repo: Repository in 'owner/repo' format
        path: File path relative to repo root (e.g., 'src/main.py')
        ref: Branch name or commit SHA (defaults to 'main')

    Returns:
        The file content as text, or an error message if not found.
    """
    logger.info(f"Fetching {path}@{ref} from {repo}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        content = repository.get_contents(path, ref=ref)

        if isinstance(content, list):
            return f"Error: {path} is a directory, not a file"

        return content.decoded_content.decode("utf-8")

    except Exception as e:
        return f"Error fetching {path}: {e}"

    finally:
        gh.close()


# ── Tool: post_review_comment ───────────────────────────────────

@mcp.tool()
def post_review_comment(
    repo: str,
    pr_number: int,
    path: str,
    position: int,
    body: str,
) -> str:
    """
    Post an inline review comment on a specific line of a PR diff.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: The pull request number
        path: File path the comment applies to (e.g., 'src/main.py')
        position: Line position in the diff (not the absolute file line number)
        body: The comment text (supports GitHub markdown)

    Returns:
        Confirmation message.
    """
    logger.info(f"Posting inline comment on {repo} PR #{pr_number} at {path}:{position}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        pr = repository.get_pull(pr_number)

        pr.create_review(
            body="",
            event="COMMENT",
            comments=[{"path": path, "position": position, "body": body}],
        )

        return f"✅ Comment posted on {path} at position {position}"

    finally:
        gh.close()


# ── Tool: post_pr_summary ──────────────────────────────────────

@mcp.tool()
def post_pr_summary(repo: str, pr_number: int, body: str) -> str:
    """
    Post a summary comment on a pull request.

    Use this for overall review summaries with quality scores,
    top concerns, and recommendations.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: The pull request number
        body: The summary comment text (supports GitHub markdown)

    Returns:
        Confirmation message.
    """
    logger.info(f"Posting summary comment on {repo} PR #{pr_number}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        pr = repository.get_pull(pr_number)
        pr.create_issue_comment(body)

        return f"✅ Summary comment posted on PR #{pr_number}"

    finally:
        gh.close()


# ── Tool: search_codebase ──────────────────────────────────────

@mcp.tool()
def search_codebase(query: str, n_results: int = 5) -> str:
    """
    Search the indexed codebase for similar code patterns using RAG.

    This queries a ChromaDB vector store that has been pre-indexed
    with the repository's code. Useful for finding existing patterns
    that new code should follow.

    Args:
        query: The code or description to search for
        n_results: Number of similar results to return (default: 5)

    Returns:
        Similar code snippets from the codebase, or a message if
        the index is not available.
    """
    logger.info(f"Searching codebase for: {query[:80]}...")

    try:
        from src.rag.retriever import PatternRetriever

        retriever = PatternRetriever()
        results = retriever.find_similar(query, n_results=n_results)

        if not results:
            return "No similar patterns found in the codebase index."

        parts = [f"Found {len(results)} similar patterns:\n"]
        for i, result in enumerate(results, 1):
            parts.append(f"--- Match {i} (from {result.get('file_path', 'unknown')}) ---")
            parts.append(result.get("content", ""))
            parts.append("")

        return "\n".join(parts)

    except ImportError:
        return "⚠ Codebase index not available. Run `python scripts/index_repo.py` first."
    except Exception as e:
        return f"⚠ Search failed: {e}"


# ── Tool: list_pr_files ─────────────────────────────────────────

@mcp.tool()
def list_pr_files(repo: str, pr_number: int) -> str:
    """
    List all files changed in a pull request.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: The pull request number

    Returns:
        A formatted list of changed files with their status and stats.
    """
    logger.info(f"Listing files for {repo} PR #{pr_number}")
    gh = _get_github()

    try:
        repository = gh.get_repo(repo)
        pr = repository.get_pull(pr_number)
        files = pr.get_files()

        parts = [f"Files changed in PR #{pr_number}:\n"]
        for f in files:
            status_icon = {
                "added": "🟢",
                "modified": "🟡",
                "removed": "🔴",
                "renamed": "🔵",
            }.get(f.status, "⚪")

            parts.append(
                f"  {status_icon} {f.filename} "
                f"(+{f.additions}/-{f.deletions}) [{f.status}]"
            )

        return "\n".join(parts)

    finally:
        gh.close()


# ── Entrypoint ──────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting GitHub Reviewer MCP Server (stdio transport)...")
    mcp.run(transport="stdio")
