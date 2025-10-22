"""Tests for document parsing utilities."""

from __future__ import annotations

from pathlib import Path

from agent.contracts import DocumentInput
from agent.doc_parser import DocumentParser, chunk_text, mask_pii


def test_mask_pii_replaces_sensitive_tokens() -> None:
    text = "Contact us at ops@example.com or +1-202-555-0175"
    masked = mask_pii(text)
    assert "example" not in masked
    assert "0175" not in masked


def test_document_parser_reads_text(tmp_path: Path) -> None:
    text_file = tmp_path / "catalog.txt"
    text_file.write_text(
        "VITALITY COMPLEX\nDaily support\n- Supports focus\n- Smooth energy\n", encoding="utf-8"
    )
    parser = DocumentParser(chunk_size=16)
    documents = parser.parse([DocumentInput(path=str(text_file), type="text", label="catalog")])
    assert documents[0].chunks
    catalog = parser.extract_catalog_from_many(documents)
    assert "Vitality Complex" in catalog


def test_chunk_text_respects_limits() -> None:
    text = "one two three four"
    chunks = chunk_text(text, max_chars=7)
    assert len(chunks) == 2
