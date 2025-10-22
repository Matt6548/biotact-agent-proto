"""Tests for the sample summary skill."""

from skills.sample_skill import run


def test_sample_skill_returns_offline_summary() -> None:
    payload = {"text": "The platform ingests documents and plans content."}
    result = run(payload)
    assert "offline" in result["provider"].lower()
    assert "platform" in result["summary"].lower()
