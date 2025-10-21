"""Tests for export functionality."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from agent.contracts import ExportRequest, GeneratedContent, Plan, PlanItem
from agent.exporter import Exporter


def test_exporter_creates_requested_files(tmp_path: Path) -> None:
    item = PlanItem(
        date=date(2025, 1, 1),
        channel="blog",
        title="Focus Ritual",
        summary="Daily routine",
        catalog_item="Vitality",
    )
    plan = Plan(items=[item])
    generated = {
        item.key(): GeneratedContent(
            title=item.title,
            body="Overview\nDetails\n\nSources:\n- [1] demo",
            bullet_points=["Daily routine"],
            sources=["demo"],
            citations=["[1]"],
            llm_model="offline",
            cost_usd=0.0,
        )
    }
    request = ExportRequest(
        plan=plan,
        generated=generated,
        output_dir=str(tmp_path),
        include_formats=["json", "markdown"],
    )
    exporter = Exporter(mask_sensitive=False)
    paths = exporter.export(request)
    assert (tmp_path / "plan.json").exists()
    assert (tmp_path / "plan.md").exists()
    assert set(paths.keys()) == {"json", "markdown"}
