"""
Pattern retriever for ChromaDB RAG.

Queries the indexed codebase to find similar code patterns,
providing context for the AI reviewer.
"""

from __future__ import annotations

import logging

import chromadb
from chromadb.utils import embedding_functions

from src.config import load_settings

logger = logging.getLogger(__name__)


class PatternRetriever:
    """
    Retrieves similar code patterns from the ChromaDB index.

    Usage:
        retriever = PatternRetriever()
        results = retriever.find_similar("def process_data(df):", n_results=5)
    """

    def __init__(
        self,
        chroma_path: str | None = None,
        collection_name: str = "codebase",
    ):
        # Resolve ChromaDB path
        if chroma_path is None:
            try:
                settings = load_settings()
                chroma_path = settings.chroma_db_path
            except Exception:
                chroma_path = "./data/chroma_db"

        # Initialize ChromaDB client
        self._client = chromadb.PersistentClient(path=chroma_path)
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        try:
            self._collection = self._client.get_collection(
                name=collection_name,
                embedding_function=self._embedding_fn,
            )
            logger.info(
                f"PatternRetriever connected — "
                f"{self._collection.count()} chunks in index"
            )
        except Exception:
            # Collection doesn't exist yet
            self._collection = None
            logger.warning(
                "⚠ Codebase collection not found. "
                "Run `python scripts/index_repo.py` to create it."
            )

    @property
    def is_available(self) -> bool:
        """Check if the index is available and has data."""
        return self._collection is not None and self._collection.count() > 0

    def find_similar(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Find code snippets similar to the query text.

        Args:
            query: Code or description to search for.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with 'content', 'file_path', 'chunk_index',
            'language', and 'distance' keys.
        """
        if not self.is_available:
            return []

        # Truncate very long queries to avoid embedding issues
        if len(query) > 5000:
            query = query[:5000]

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, self._collection.count()),
            )

            matches: list[dict] = []
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for doc, meta, dist in zip(documents, metadatas, distances):
                matches.append({
                    "content": doc,
                    "file_path": meta.get("file_path", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "language": meta.get("language", ""),
                    "distance": dist,
                })

            return matches

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return []

    def find_related_files(self, file_path: str, n_results: int = 5) -> list[str]:
        """
        Find files related to a given file path.

        Uses the file content as a query to find similar files.

        Args:
            file_path: Path of the file to find relations for.
            n_results: Maximum number of results.

        Returns:
            List of related file paths.
        """
        if not self.is_available:
            return []

        try:
            # Query by metadata filter for the same directory
            # and by content similarity
            results = self._collection.query(
                query_texts=[f"code in {file_path}"],
                n_results=n_results,
                where={"file_path": {"$ne": file_path}},
            )

            file_paths = set()
            for meta in results.get("metadatas", [[]])[0]:
                file_paths.add(meta.get("file_path", ""))

            return list(file_paths)

        except Exception as e:
            logger.error(f"Related files query failed: {e}")
            return []
