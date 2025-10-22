"""Planning utilities for scheduling content across channels."""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
from typing import Deque, Dict, Iterable, List, Optional, Sequence

from .contracts import AwarenessEvent, CatalogItem, Plan, PlanItem, PlanRequest


class Planner:
    """Generate channel schedules using catalogue metadata."""

    def __init__(
        self,
        catalog: Dict[str, CatalogItem],
        awareness_events: Iterable[AwarenessEvent] | None = None,
    ) -> None:
        self.catalog = catalog
        self.awareness_events: Dict[date, AwarenessEvent] = {
            event.date: event for event in (awareness_events or [])
        }
        self._catalog_cycle: Deque[str] = deque(sorted(catalog.keys()))

    def _next_catalog_item(self) -> Optional[str]:
        if not self._catalog_cycle:
            return None
        name = self._catalog_cycle[0]
        self._catalog_cycle.rotate(-1)
        return name

    def _channel_for_index(self, channels: Sequence[str], index: int) -> str:
        return channels[index % len(channels)]

    def _awareness_for_date(self, day: date) -> Optional[AwarenessEvent]:
        return self.awareness_events.get(day)

    def build_plan(self, request: PlanRequest) -> Plan:
        """Build a plan for the given time period."""

        channels = list(request.channels)
        if not channels:
            raise ValueError("At least one channel must be provided")

        current = request.start_date
        index = 0
        items: List[PlanItem] = []
        while current <= request.end_date:
            if (current - request.start_date).days % request.cadence_days != 0:
                current += timedelta(days=1)
                continue
            channel = self._channel_for_index(channels, index)
            index += 1

            awareness = self._awareness_for_date(current)
            catalog_name = self._next_catalog_item()
            catalog_entry = self.catalog.get(catalog_name) if catalog_name else None

            title_parts: List[str] = []
            if awareness:
                title_parts.append(awareness.name)
            if catalog_entry:
                title_parts.append(catalog_entry.name)
            else:
                title_parts.append("Insight Spotlight")
            title = " – ".join(title_parts)

            summary_parts: List[str] = []
            if catalog_entry:
                summary_parts.append(catalog_entry.tagline or catalog_entry.notes[:120])
                if catalog_entry.benefits:
                    summary_parts.append("; ".join(catalog_entry.benefits[:2]))
            if awareness:
                summary_parts.append(f"Aligned with {awareness.name}")
            if not summary_parts:
                summary_parts.append("Scheduled content item")
            summary = " ".join(summary_parts)

            target = catalog_entry.target_audience if catalog_entry else []
            sources = [f"catalog:{catalog_entry.name}"] if catalog_entry else []
            if awareness:
                sources.append(f"event:{awareness.name}")

            items.append(
                PlanItem(
                    date=current,
                    channel=channel,
                    title=title,
                    summary=summary,
                    catalog_item=catalog_entry.name if catalog_entry else None,
                    target_audience=target,
                    awareness_event=awareness.name if awareness else None,
                    sources=sources,
                )
            )
            current += timedelta(days=1)

        return Plan(items=items)
