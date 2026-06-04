"""
CLI script to index a repository into ChromaDB for RAG.

Usage:
    python scripts/index_repo.py --path /path/to/local/repo
    python scripts/index_repo.py --path .
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import setup_logging
from src.rag.indexer import CodebaseIndexer


def main():
    parser = argparse.ArgumentParser(
        description="Index a repository into ChromaDB for RAG-powered code review"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the local repository to index",
    )
    parser.add_argument(
        "--collection",
        default="codebase",
        help="ChromaDB collection name (default: codebase)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing index before indexing",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size in approximate tokens (default: 500)",
    )

    args = parser.parse_args()
    setup_logging("INFO")

    logger = logging.getLogger(__name__)
    logger.info(f"🔧 Indexing repository at: {args.path}")

    indexer = CodebaseIndexer(
        collection_name=args.collection,
        chunk_size=args.chunk_size,
    )

    if args.clear:
        logger.info("🗑 Clearing existing index...")
        indexer.clear()

    stats = indexer.index_directory(args.path)

    print("\n" + "=" * 50)
    print("Indexing Results")
    print("=" * 50)
    print(f"  Files indexed:  {stats['files_indexed']}")
    print(f"  Chunks added:   {stats['chunks_added']}")
    print(f"  Files skipped:  {stats['files_skipped']}")
    print(f"  Total in index: {indexer.count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
