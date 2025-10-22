"""Tests for planning logic."""

from __future__ import annotations

from datetime import date

from agent.contracts import AwarenessEvent, CatalogItem, PlanRequest
from agent.planner import Planner


def test_planner_rotates_catalog_items() -> None:
    catalog = {
        "Vitality": CatalogItem(name="Vitality", tagline="Energy", benefits=["Focus boost"]),
        "Clarity": CatalogItem(name="Clarity", tagline="Focus", benefits=["Calm alert"]),
    }
    request = PlanRequest(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
        channels=["blog"],
        cadence_days=1,
    )
    planner = Planner(catalog=catalog)
    plan = planner.build_plan(request)
    assert len(plan.items) == 3
    assert {item.catalog_item for item in plan.items} == {"Vitality", "Clarity"}


def test_planner_includes_awareness_event() -> None:
    catalog = {
        "Vitality": CatalogItem(name="Vitality", tagline="Energy"),
    }
    request = PlanRequest(
        start_date=date(2025, 5, 1),
        end_date=date(2025, 5, 1),
        channels=["email"],
        cadence_days=1,
    )
    events = [AwarenessEvent(date=date(2025, 5, 1), name="Focus Day")]
    planner = Planner(catalog=catalog, awareness_events=events)
    plan = planner.build_plan(request)
    assert plan.items[0].awareness_event == "Focus Day"
