"""Sample skill demonstrating how to call the shared LLM client."""

from __future__ import annotations

from agent.llm_client import LLMClient


def run(payload: dict) -> dict:
    """Summarise the provided text using the platform LLM layer."""

    text = payload.get("text", "")
    client = LLMClient()
    result = client.generate(f"Summarise the following for a status update:\n{text}")
    return {"summary": result.content, "provider": result.provider}
