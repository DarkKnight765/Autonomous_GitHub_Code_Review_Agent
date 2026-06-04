"""
LangGraph review pipeline definition.

Wires all node functions into a StateGraph and compiles it
into an executable review pipeline.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from src.review.nodes import (
    aggregate_findings,
    fetch_diff,
    fetch_file_context,
    generate_summary,
    load_feedback,
    post_results,
    query_rag,
    review_chunks,
)
from src.review.state import ReviewState

logger = logging.getLogger(__name__)


def build_review_graph() -> StateGraph:
    """
    Build the review pipeline as a LangGraph StateGraph.

    Pipeline flow:
        START → fetch_diff → fetch_file_context → query_rag → load_feedback
              → review_chunks → aggregate_findings → generate_summary
              → post_results → END

    Returns:
        A compiled StateGraph ready to invoke.
    """
    builder = StateGraph(ReviewState)

    # ── Add Nodes ───────────────────────────────────────────────
    builder.add_node("fetch_diff", fetch_diff)
    builder.add_node("fetch_file_context", fetch_file_context)
    builder.add_node("query_rag", query_rag)
    builder.add_node("load_feedback", load_feedback)
    builder.add_node("review_chunks", review_chunks)
    builder.add_node("aggregate_findings", aggregate_findings)
    builder.add_node("generate_summary", generate_summary)
    builder.add_node("post_results", post_results)

    # ── Define Flow ─────────────────────────────────────────────
    builder.add_edge(START, "fetch_diff")
    builder.add_edge("fetch_diff", "fetch_file_context")
    builder.add_edge("fetch_file_context", "query_rag")
    builder.add_edge("query_rag", "load_feedback")
    builder.add_edge("load_feedback", "review_chunks")
    builder.add_edge("review_chunks", "aggregate_findings")
    builder.add_edge("aggregate_findings", "generate_summary")
    builder.add_edge("generate_summary", "post_results")
    builder.add_edge("post_results", END)

    logger.info("📐 Review graph built with 8 nodes")
    return builder


# ── Compile the default graph ───────────────────────────────────

review_graph = build_review_graph().compile()

logger.info("✅ Review pipeline compiled and ready")
