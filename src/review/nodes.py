"""
LangGraph node functions for the review pipeline.

Each function takes the current ReviewState and returns a partial
state update. These are wired together in graph.py.
"""

from __future__ import annotations

import json
import logging
import os

from src.config import load_settings
from src.github_client.client import GitHubReviewClient, ReviewComment, ReviewSubmission
from src.github_client.diff_parser import DiffParser, format_diff_for_review
from src.review.prompts import (
    CHUNK_REVIEW_SYSTEM,
    CHUNK_REVIEW_USER,
    SUMMARY_SYSTEM,
    SUMMARY_USER,
)
from src.review.state import ReviewState

logger = logging.getLogger(__name__)


def _get_settings():
    """Load settings, handling missing env vars gracefully."""
    try:
        return load_settings()
    except Exception:
        return None


def _get_provider() -> str:
    """Get the configured LLM provider ('gemini' or 'anthropic')."""
    settings = _get_settings()
    return (
        settings.llm_provider if settings
        else os.getenv("LLM_PROVIDER", "gemini")
    )


def _get_review_model() -> str:
    """Get the configured review model."""
    settings = _get_settings()
    default = "gemini-2.0-flash"
    return settings.review_model if settings else os.getenv("REVIEW_MODEL", default)


def call_llm(system: str, user: str) -> str:
    """
    Provider-agnostic LLM call. Routes to Groq, Gemini, or Anthropic
    based on the LLM_PROVIDER environment variable.

    Returns the raw text response from the model.
    """
    provider = _get_provider()
    model = _get_review_model()
    settings = _get_settings()

    if provider == "groq":
        from groq import Groq
        api_key = (
            settings.groq_api_key if settings
            else os.getenv("GROQ_API_KEY", "")
        )
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content

    elif provider == "gemini":
        from google import genai
        from google.genai import types
        api_key = (
            settings.gemini_api_key if settings
            else os.getenv("GEMINI_API_KEY", "")
        )
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=4096,
            ),
        )
        return response.text

    else:  # anthropic
        from anthropic import Anthropic
        api_key = (
            settings.anthropic_api_key if settings
            else os.getenv("ANTHROPIC_API_KEY", "")
        )
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text




# ── Node 1: Fetch Diff ─────────────────────────────────────────

def fetch_diff(state: ReviewState) -> dict:
    """
    Fetch the PR diff and metadata from GitHub.

    Populates: diff_chunks, pr_metadata
    """
    repo = state["repo"]
    pr_number = state["pr_number"]
    logger.info(f"📥 Fetching diff for {repo} PR #{pr_number}")

    settings = _get_settings()
    token = settings.github_token if settings else os.getenv("GITHUB_TOKEN", "")

    with GitHubReviewClient(token=token) as client:
        # Fetch metadata
        pr_metadata = client.get_pr_metadata(repo, pr_number)

        # Fetch file changes
        file_changes = client.get_pr_diff(repo, pr_number)

    # Parse diffs into structured chunks
    parser = DiffParser()
    file_diffs = parser.parse_pr_files(file_changes)

    # Convert to serializable dicts for state
    diff_chunks = []
    for fd in file_diffs:
        diff_chunks.append({
            "file_path": fd.file_path,
            "total_additions": fd.total_additions,
            "total_deletions": fd.total_deletions,
            "formatted": format_diff_for_review(fd),
            "hunks": [
                {
                    "old_start": h.old_start,
                    "new_start": h.new_start,
                    "section_header": h.section_header,
                    "lines": [
                        {
                            "content": ln.content,
                            "line_type": ln.line_type,
                            "new_line_number": ln.new_line_number,
                            "diff_position": ln.diff_position,
                        }
                        for ln in h.lines
                    ],
                }
                for h in fd.hunks
            ],
        })

    logger.info(
        f"📋 Parsed {len(diff_chunks)} files, "
        f"+{pr_metadata.get('additions', 0)}/-{pr_metadata.get('deletions', 0)}"
    )

    return {
        "diff_chunks": diff_chunks,
        "pr_metadata": pr_metadata,
        "errors": [],
    }


# ── Node 2: Fetch File Context ─────────────────────────────────

def fetch_file_context(state: ReviewState) -> dict:
    """
    Fetch full file content for each changed file.

    Gives Claude surrounding context beyond just the diff hunk.
    Populates: file_contents
    """
    repo = state["repo"]
    pr_metadata = state.get("pr_metadata", {})
    diff_chunks = state.get("diff_chunks", [])
    head_sha = pr_metadata.get("head_sha", "main")

    logger.info(f"📄 Fetching file contents for {len(diff_chunks)} files")

    settings = _get_settings()
    token = settings.github_token if settings else os.getenv("GITHUB_TOKEN", "")

    file_contents: dict[str, str] = {}
    errors: list[str] = []

    with GitHubReviewClient(token=token) as client:
        for chunk in diff_chunks:
            file_path = chunk["file_path"]
            try:
                content = client.get_file_content(repo, file_path, ref=head_sha)
                if content:
                    # Truncate very large files to avoid token limits
                    if len(content) > 15000:
                        content = content[:15000] + "\n\n... (truncated, file too large)"
                    file_contents[file_path] = content
            except Exception as e:
                logger.warning(f"Could not fetch {file_path}: {e}")
                errors.append(f"Could not fetch {file_path}: {e}")

    logger.info(f"📄 Fetched content for {len(file_contents)}/{len(diff_chunks)} files")

    return {
        "file_contents": file_contents,
        "errors": errors,
    }


# ── Node 3: Query RAG ──────────────────────────────────────────

def query_rag(state: ReviewState) -> dict:
    """
    Query ChromaDB for similar code patterns.

    Populates: similar_patterns
    """
    diff_chunks = state.get("diff_chunks", [])
    logger.info("🔍 Querying RAG for similar patterns...")

    similar_patterns: list[str] = []

    try:
        from src.rag.retriever import PatternRetriever

        retriever = PatternRetriever()

        # Query for each diff chunk
        for chunk in diff_chunks[:5]:  # limit to 5 files to avoid overloading
            formatted = chunk.get("formatted", "")
            if formatted:
                results = retriever.find_similar(formatted, n_results=3)
                for r in results:
                    pattern = f"[{r.get('file_path', 'unknown')}]\n{r.get('content', '')}"
                    if pattern not in similar_patterns:
                        similar_patterns.append(pattern)

        logger.info(f"🔍 Found {len(similar_patterns)} similar patterns")

    except ImportError:
        logger.info("⏭ RAG not available (ChromaDB not indexed). Skipping.")
    except Exception as e:
        logger.warning(f"⚠ RAG query failed: {e}")

    return {
        "similar_patterns": similar_patterns,
        "errors": [],
    }


# ── Node 4: Load Feedback ──────────────────────────────────────

def load_feedback(state: ReviewState) -> dict:
    """
    Load previously dismissed suggestions from the feedback store.

    Populates: past_dismissed
    """
    repo = state["repo"]
    logger.info("📚 Loading feedback history...")

    past_dismissed: list[str] = []

    try:
        from src.feedback.store import FeedbackStore

        store = FeedbackStore()
        past_dismissed = store.get_dismissed_patterns(repo, limit=50)
        logger.info(f"📚 Loaded {len(past_dismissed)} dismissed patterns")

    except ImportError:
        logger.info("⏭ Feedback store not available. Skipping.")
    except Exception as e:
        logger.warning(f"⚠ Feedback load failed: {e}")

    return {
        "past_dismissed": past_dismissed,
        "errors": [],
    }


# ── Node 5: Review Chunks (Core AI Node) ───────────────────────

def review_chunks(state: ReviewState) -> dict:
    """
    Send each diff chunk to Claude for analysis.

    This is the core AI node. For each changed file, builds a prompt
    with the diff, file context, similar patterns, and dismissed
    patterns, then calls Claude and parses the structured JSON response.

    Populates: findings
    """
    diff_chunks = state.get("diff_chunks", [])
    pr_metadata = state.get("pr_metadata", {})
    file_contents = state.get("file_contents", {})
    similar_patterns = state.get("similar_patterns", [])
    past_dismissed = state.get("past_dismissed", [])

    logger.info(f"🤖 Reviewing {len(diff_chunks)} file diffs with LLM...")

    # Build dismissed patterns context
    dismissed_text = "None" if not past_dismissed else "\n".join(
        f"- {p}" for p in past_dismissed[:20]
    )

    # Build similar patterns context
    patterns_text = "No codebase patterns indexed." if not similar_patterns else "\n\n".join(
        similar_patterns[:10]
    )

    all_findings: list[dict] = []
    errors: list[str] = []

    for chunk in diff_chunks:
        file_path = chunk["file_path"]
        formatted_diff = chunk.get("formatted", "")

        if not formatted_diff.strip():
            continue

        # Get full file context
        file_context = file_contents.get(file_path, "(full file content not available)")

        # Build the system prompt with dismissed patterns
        system_prompt = CHUNK_REVIEW_SYSTEM.format(dismissed_patterns=dismissed_text)

        # Build the user prompt
        user_prompt = CHUNK_REVIEW_USER.format(
            pr_title=pr_metadata.get("title", ""),
            pr_description=pr_metadata.get("body", "")[:1000],
            pr_author=pr_metadata.get("author", ""),
            diff_chunk=formatted_diff,
            file_context=file_context[:8000],  # limit context size
            similar_patterns=patterns_text[:4000],
        )

        try:
            response_text = call_llm(system=system_prompt, user=user_prompt).strip()

            # Handle markdown-fenced JSON
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            result = json.loads(response_text)
            findings = result.get("findings", [])

            # Add diff position mapping for each finding
            for finding in findings:
                finding["file"] = file_path  # ensure correct file path
                # Try to map line number to diff position
                line_num = finding.get("line", 0)
                position = _find_diff_position(chunk, line_num)
                finding["position"] = position if position else 1

            all_findings.extend(findings)

            logger.info(
                f"  📝 {file_path}: {len(findings)} findings"
            )

        except json.JSONDecodeError as e:
            logger.error(f"  ❌ Failed to parse Claude response for {file_path}: {e}")
            errors.append(f"JSON parse error for {file_path}: {e}")
        except Exception as e:
            logger.error(f"  ❌ Review failed for {file_path}: {e}")
            errors.append(f"Review error for {file_path}: {e}")

    logger.info(f"🤖 Review complete: {len(all_findings)} total findings")

    return {
        "findings": all_findings,
        "errors": errors,
    }


def _find_diff_position(chunk: dict, line_number: int) -> int | None:
    """Map a file line number to a diff position for GitHub API."""
    for hunk in chunk.get("hunks", []):
        for line in hunk.get("lines", []):
            if line.get("new_line_number") == line_number:
                return line.get("diff_position")
    return None


# ── Node 6: Aggregate Findings ─────────────────────────────────

def aggregate_findings(state: ReviewState) -> dict:
    """
    Deduplicate, sort, and filter findings.

    Sorts by severity (high → medium → low), removes duplicates,
    and applies the max findings limit.

    Updates: findings
    """
    findings = state.get("findings", [])
    _past_dismissed = state.get("past_dismissed", [])  # noqa: F841

    logger.info(f"📊 Aggregating {len(findings)} findings...")

    settings = _get_settings()
    max_findings = settings.max_findings_per_pr if settings else 20
    min_severity = settings.min_severity if settings else "low"

    # Severity ordering
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    min_rank = severity_rank.get(min_severity, 2)

    # Filter by minimum severity
    filtered = [
        f for f in findings
        if severity_rank.get(f.get("severity", "low"), 2) <= min_rank
    ]

    # Deduplicate by file + line + title
    seen = set()
    deduped = []
    for f in filtered:
        key = (f.get("file", ""), f.get("line", 0), f.get("title", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    # Sort by severity (high first)
    deduped.sort(key=lambda f: severity_rank.get(f.get("severity", "low"), 2))

    # Apply max limit
    final = deduped[:max_findings]

    logger.info(
        f"📊 Aggregated: {len(findings)} → {len(filtered)} (severity filter) "
        f"→ {len(deduped)} (deduped) → {len(final)} (capped)"
    )

    return {
        "findings": final,
    }


# ── Node 7: Generate Summary ───────────────────────────────────

def generate_summary(state: ReviewState) -> dict:
    """
    Generate the final summary comment with quality score.

    Calls Claude to produce a polished markdown summary based on
    all aggregated findings.

    Populates: summary, quality_score, top_concerns
    """
    findings = state.get("findings", [])
    pr_metadata = state.get("pr_metadata", {})
    repo = state["repo"]
    pr_number = state["pr_number"]

    logger.info("Generating review summary...")

    # Build findings JSON for the prompt
    findings_json = json.dumps(findings, indent=2) if findings else "No issues found."

    user_prompt = SUMMARY_USER.format(
        repo=repo,
        pr_number=pr_number,
        pr_title=pr_metadata.get("title", ""),
        pr_author=pr_metadata.get("author", ""),
        files_changed=pr_metadata.get("changed_files", 0),
        additions=pr_metadata.get("additions", 0),
        deletions=pr_metadata.get("deletions", 0),
        findings_json=findings_json,
    )

    try:
        summary = call_llm(system=SUMMARY_SYSTEM, user=user_prompt).strip()

        # Calculate quality score based on findings
        high_count = sum(1 for f in findings if f.get("severity") == "high")
        medium_count = sum(1 for f in findings if f.get("severity") == "medium")
        low_count = sum(1 for f in findings if f.get("severity") == "low")

        if high_count >= 3:
            quality_score = 2
        elif high_count >= 1:
            quality_score = 4
        elif medium_count >= 5:
            quality_score = 5
        elif medium_count >= 2:
            quality_score = 6
        elif medium_count >= 1:
            quality_score = 7
        elif low_count >= 1:
            quality_score = 8
        else:
            quality_score = 9

        # Extract top concerns
        top_concerns = []
        for f in findings[:3]:
            concern = f"[{f.get('severity', 'unknown').upper()}] {f.get('title', 'Unknown issue')}"
            top_concerns.append(concern)

        logger.info(f"📝 Summary generated — Quality score: {quality_score}/10")

        return {
            "summary": summary,
            "quality_score": quality_score,
            "top_concerns": top_concerns,
            "errors": [],
        }

    except Exception as e:
        logger.error(f"❌ Summary generation failed: {e}")
        # Fallback summary
        return {
            "summary": (
                f"## 🤖 AGCRA — Automated Code Review\n\n"
                f"Review completed with {len(findings)} findings. "
                f"Summary generation encountered an error."
            ),
            "quality_score": 5,
            "top_concerns": [],
            "errors": [f"Summary generation failed: {e}"],
        }


# ── Node 8: Post Results ───────────────────────────────────────

def post_results(state: ReviewState) -> dict:
    """
    Post review comments and summary to GitHub.

    Posts inline comments for each finding (mapped to correct diff
    positions) and a summary comment with the quality score.

    Populates: review_posted
    """
    repo = state["repo"]
    pr_number = state["pr_number"]
    findings = state.get("findings", [])
    summary = state.get("summary", "")

    logger.info(f"📤 Posting results to {repo} PR #{pr_number}...")

    settings = _get_settings()
    token = settings.github_token if settings else os.getenv("GITHUB_TOKEN", "")
    review_event = settings.review_event if settings else "COMMENT"

    try:
        with GitHubReviewClient(token=token) as client:
            # Build inline comments from findings
            inline_comments = []
            for f in findings:
                position = f.get("position")
                if position and position > 0:
                    severity_emoji = {
                        "high": "🔴",
                        "medium": "🟡",
                        "low": "🔵",
                    }.get(f.get("severity", "low"), "⚪")

                    comment_body = (
                        f"{severity_emoji} **{f.get('title', 'Issue')}** "
                        f"({f.get('severity', 'unknown')} / {f.get('category', 'general')})\n\n"
                        f"{f.get('body', '')}"
                    )

                    if f.get("suggested_fix"):
                        comment_body += f"\n\n**Suggested fix:**\n```\n{f['suggested_fix']}\n```"

                    inline_comments.append(
                        ReviewComment(
                            path=f.get("file", ""),
                            position=position,
                            body=comment_body,
                        )
                    )

            # Post the review with inline comments
            if inline_comments:
                submission = ReviewSubmission(
                    body=f"AGCRA found {len(findings)} issue(s) in this PR.",
                    event=review_event,
                    comments=inline_comments,
                )
                client.post_review(repo, pr_number, submission)

            # Post the summary as a separate issue comment
            if summary:
                client.post_issue_comment(repo, pr_number, summary)

        logger.info(
            f"✅ Posted {len(inline_comments)} inline comments "
            f"and summary to {repo} PR #{pr_number}"
        )

        # Record the review in feedback store
        try:
            from src.feedback.store import FeedbackStore

            store = FeedbackStore()
            store.record_review(
                repo=repo,
                pr_number=pr_number,
                quality_score=state.get("quality_score", 0),
                findings_count=len(findings),
            )
        except Exception as e:
            logger.warning(f"Could not record review in feedback store: {e}")

        return {
            "review_posted": True,
            "errors": [],
        }

    except Exception as e:
        logger.error(f"❌ Failed to post results: {e}", exc_info=True)
        return {
            "review_posted": False,
            "errors": [f"Failed to post results: {e}"],
        }
