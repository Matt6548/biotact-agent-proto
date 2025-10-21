"""Tests for retrieval augmented generation helpers."""

from __future__ import annotations

from agent.contracts import ParsedDocument
from agent.rag import RAGEngine


def test_rag_engine_returns_relevant_chunk() -> None:
    doc = ParsedDocument(
        label="catalog",
        text="",
        metadata={"path": "catalog.txt"},
        chunks=["Vitality Complex keeps energy stable for remote teams."],
    )
    engine = RAGEngine()
    engine.index([doc])
    results = engine.search("energy for remote teams")
    assert results
    chunk, score = results[0]
    assert "Vitality" in chunk.text
    assert score > 0
