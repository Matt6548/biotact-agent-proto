"""Lightweight retrieval augmented generation utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .contracts import ParsedDocument


@dataclass
class RAGChunk:
    """Chunk of text stored for retrieval."""

    text: str
    source: str
    order: int


class RAGEngine:
    """Simple term-overlap based retriever."""

    def __init__(self) -> None:
        self._chunks: List[RAGChunk] = []

    def index(self, documents: Iterable[ParsedDocument]) -> None:
        """Index parsed documents for retrieval."""

        for doc in documents:
            for order, chunk in enumerate(doc.chunks):
                citation = f"{doc.metadata.get('path', doc.label)}#chunk-{order}"
                self._chunks.append(RAGChunk(text=chunk, source=citation, order=order))

    def search(self, query: str, top_k: int = 3) -> List[Tuple[RAGChunk, float]]:
        """Return top chunks ranked by cosine similarity over term counts."""

        if not query.strip():
            return []
        query_terms = self._tokenise(query)
        scored: List[Tuple[RAGChunk, float]] = []
        for chunk in self._chunks:
            chunk_terms = self._tokenise(chunk.text)
            score = self._cosine_similarity(query_terms, chunk_terms)
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        return [token.lower() for token in text.split() if token]

    @staticmethod
    def _cosine_similarity(query_terms: List[str], doc_terms: List[str]) -> float:
        if not doc_terms or not query_terms:
            return 0.0
        query_counts = {}
        for term in query_terms:
            query_counts[term] = query_counts.get(term, 0) + 1
        doc_counts = {}
        for term in doc_terms:
            doc_counts[term] = doc_counts.get(term, 0) + 1
        intersection = set(query_counts) & set(doc_counts)
        numerator = sum(query_counts[t] * doc_counts[t] for t in intersection)
        query_norm = math.sqrt(sum(value * value for value in query_counts.values()))
        doc_norm = math.sqrt(sum(value * value for value in doc_counts.values()))
        if query_norm == 0 or doc_norm == 0:
            return 0.0
        return numerator / (query_norm * doc_norm)
