"""
Codebase indexer for ChromaDB RAG.

Indexes repository source files into a ChromaDB vector store so the
review pipeline can find similar existing patterns when analyzing diffs.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.config import load_settings

logger = logging.getLogger(__name__)

# File extensions to index
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".kt", ".scala", ".r", ".sql", ".sh", ".bash", ".yaml", ".yml",
    ".json", ".toml", ".md", ".txt",
}

# Directories to skip
SKIP_DIRS = {
    "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".eggs", "*.egg-info", ".idea", ".vscode",
}

# Max file size to index (skip huge generated files)
MAX_FILE_SIZE = 100_000  # 100KB


class CodebaseIndexer:
    """
    Indexes a codebase into ChromaDB for RAG-powered code review.

    Usage:
        indexer = CodebaseIndexer()
        indexer.index_directory("/path/to/repo")
    """

    def __init__(
        self,
        chroma_path: str | None = None,
        collection_name: str = "codebase",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        # Resolve ChromaDB path
        if chroma_path is None:
            try:
                settings = load_settings()
                chroma_path = settings.chroma_db_path
            except Exception:
                chroma_path = "./data/chroma_db"

        # Ensure directory exists
        os.makedirs(chroma_path, exist_ok=True)

        # Initialize ChromaDB
        self._client = chromadb.PersistentClient(path=chroma_path)
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

        logger.info(
            f"CodebaseIndexer initialized — collection='{collection_name}', "
            f"path='{chroma_path}', existing docs={self._collection.count()}"
        )

    def index_directory(self, repo_path: str) -> dict:
        """
        Index all source files in a directory tree.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Stats dict with files_indexed, chunks_added, files_skipped.
        """
        repo_root = Path(repo_path).resolve()
        if not repo_root.is_dir():
            raise ValueError(f"Not a directory: {repo_root}")

        logger.info(f"📂 Indexing codebase at {repo_root}...")

        stats = {"files_indexed": 0, "chunks_added": 0, "files_skipped": 0}

        for file_path in repo_root.rglob("*"):
            # Skip directories and non-indexable files
            if not file_path.is_file():
                continue

            # Skip by extension
            if file_path.suffix.lower() not in INDEXABLE_EXTENSIONS:
                stats["files_skipped"] += 1
                continue

            # Skip by directory name
            if any(skip in file_path.parts for skip in SKIP_DIRS):
                stats["files_skipped"] += 1
                continue

            # Skip large files
            if file_path.stat().st_size > MAX_FILE_SIZE:
                logger.debug(f"Skipping large file: {file_path}")
                stats["files_skipped"] += 1
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                relative_path = str(file_path.relative_to(repo_root))
                chunks = self._split_into_chunks(content)

                if not chunks:
                    continue

                # Generate IDs based on file path + chunk index + content hash
                ids = []
                documents = []
                metadatas = []

                for i, chunk in enumerate(chunks):
                    content_hash = hashlib.md5(chunk.encode()).hexdigest()[:8]
                    chunk_id = f"{relative_path}::{i}::{content_hash}"
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append({
                        "file_path": relative_path,
                        "chunk_index": i,
                        "language": file_path.suffix.lstrip("."),
                        "total_chunks": len(chunks),
                    })

                # Upsert into ChromaDB (handles duplicates)
                self._collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )

                stats["files_indexed"] += 1
                stats["chunks_added"] += len(chunks)

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
                stats["files_skipped"] += 1

        logger.info(
            f"✅ Indexing complete: {stats['files_indexed']} files, "
            f"{stats['chunks_added']} chunks, {stats['files_skipped']} skipped"
        )
        return stats

    def index_file(self, file_path: str, content: str, language: str = "") -> int:
        """
        Index a single file's content.

        Args:
            file_path: Relative path of the file.
            content: The file content.
            language: Programming language (e.g., 'python').

        Returns:
            Number of chunks added.
        """
        chunks = self._split_into_chunks(content)
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:8]
            chunk_id = f"{file_path}::{i}::{content_hash}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "file_path": file_path,
                "chunk_index": i,
                "language": language,
                "total_chunks": len(chunks),
            })

        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def _split_into_chunks(self, content: str) -> list[str]:
        """
        Split file content into overlapping chunks by lines.

        Uses a sliding window approach with configurable chunk size
        and overlap (measured in approximate token count).
        """
        if not content.strip():
            return []

        lines = content.split("\n")
        chunks: list[str] = []
        current_chunk_lines: list[str] = []
        current_size = 0

        for line in lines:
            # Rough token estimate: ~4 chars per token
            line_tokens = len(line) // 4 + 1
            current_size += line_tokens
            current_chunk_lines.append(line)

            if current_size >= self._chunk_size:
                chunks.append("\n".join(current_chunk_lines))
                # Keep overlap lines for next chunk
                overlap_size = 0
                overlap_start = len(current_chunk_lines)
                for j in range(len(current_chunk_lines) - 1, -1, -1):
                    overlap_size += len(current_chunk_lines[j]) // 4 + 1
                    if overlap_size >= self._chunk_overlap:
                        overlap_start = j
                        break
                current_chunk_lines = current_chunk_lines[overlap_start:]
                current_size = sum(len(ln) // 4 + 1 for ln in current_chunk_lines)

        # Don't forget the last chunk
        if current_chunk_lines:
            chunks.append("\n".join(current_chunk_lines))

        return chunks

    def clear(self) -> None:
        """Clear all documents from the collection."""
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name="codebase",
            embedding_function=self._embedding_fn,
        )
        logger.info("🗑 Codebase index cleared")

    @property
    def count(self) -> int:
        """Number of chunks in the index."""
        return self._collection.count()
