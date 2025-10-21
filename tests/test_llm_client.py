"""Tests for the LLM client fallback behaviour."""

from __future__ import annotations

from agent.llm_client import LLMClient, OfflineProvider


def test_llm_client_uses_offline_provider_when_no_keys() -> None:
    client = LLMClient(providers=[OfflineProvider()])
    result = client.generate("Hello world")
    assert result.provider == "offline"
    assert "offline-response" in result.content
