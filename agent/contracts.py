"""Pydantic contracts shared across the agent platform."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, field_validator
from pydantic import FieldValidationInfo


DocumentType = Literal["text", "docx", "pdf", "markdown"]
Channel = Literal["blog", "email", "instagram", "podcast", "telegram", "youtube"]


class DocumentInput(BaseModel):
    """Specification for a document that needs to be parsed."""

    path: str
    type: DocumentType = "text"
    label: str = "generic"
    locale: str | None = None


class ParsedDocument(BaseModel):
    """Structured representation of an ingested document."""

    label: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[str] = Field(default_factory=list)

    @field_validator("chunks", mode="before")
    @classmethod
    def default_chunks(cls, value: Iterable[str] | None) -> List[str]:
        if value is None:
            return []
        return [chunk for chunk in value if chunk]


class CatalogItem(BaseModel):
    """Generic catalogue item used for planning and generation."""

    name: str
    tagline: str = ""
    benefits: List[str] = Field(default_factory=list)
    target_audience: List[str] = Field(default_factory=list)
    notes: str = ""


class PlanRequest(BaseModel):
    """Request payload for building a schedule."""

    start_date: date
    end_date: date
    channels: Sequence[Channel]
    cadence_days: int = 2
    timezone: str = "UTC"
    objectives: List[str] = Field(default_factory=list)

    @field_validator("cadence_days")
    @classmethod
    def validate_cadence(cls, cadence: int) -> int:
        if cadence <= 0:
            raise ValueError("cadence_days must be positive")
        return cadence

    @field_validator("end_date")
    @classmethod
    def validate_range(cls, end_date: date, info: FieldValidationInfo) -> date:
        start_date = info.data.get("start_date") if info.data else None
        if start_date and end_date < start_date:
            msg = "end_date must be greater than or equal to start_date"
            raise ValueError(msg)
        return end_date


class AwarenessEvent(BaseModel):
    """Represents a notable event to align planned content."""

    date: date
    name: str
    tags: List[str] = Field(default_factory=list)


class PlanItem(BaseModel):
    """Single scheduled content item."""

    date: date
    channel: Channel
    title: str
    summary: str
    catalog_item: Optional[str] = None
    target_audience: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    awareness_event: Optional[str] = None

    def key(self) -> str:
        """Return a deterministic key for lookups."""

        return f"{self.date.isoformat()}::{self.channel}"


class Plan(BaseModel):
    """Collection of plan items."""

    items: List[PlanItem]

    def to_export_rows(self) -> List[Dict[str, str]]:
        """Return serialisable export rows."""

        rows: List[Dict[str, str]] = []
        for item in self.items:
            rows.append(
                {
                    "date": item.date.isoformat(),
                    "channel": item.channel,
                    "title": item.title,
                    "summary": item.summary,
                    "catalog_item": item.catalog_item or "",
                    "target_audience": ", ".join(item.target_audience),
                    "awareness_event": item.awareness_event or "",
                    "sources": ", ".join(item.sources),
                }
            )
        return rows


class GenerationRequest(BaseModel):
    """Request for long-form content generation."""

    plan_item: PlanItem
    tone_of_voice: str = "informative"
    format: Literal["short", "long"] = "short"
    include_call_to_action: bool = True


class GeneratedContent(BaseModel):
    """Output of the writer agent."""

    title: str
    body: str
    bullet_points: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    llm_model: str = ""
    cost_usd: float = 0.0


class VerificationReport(BaseModel):
    """Result of automated content verification."""

    passed: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    """Parameters for exporting generated artefacts."""

    plan: Plan
    generated: Dict[str, GeneratedContent]
    output_dir: str
    include_formats: Sequence[Literal["json", "csv", "markdown", "docx", "pdf"]] = Field(
        default_factory=lambda: ["json", "markdown"]
    )


class PipelineStep(BaseModel):
    """Single step in a declarative pipeline definition."""

    name: str
    uses: str
    with_config: Dict[str, Any] = Field(default_factory=dict)


class PipelineDefinition(BaseModel):
    """Pipeline defined via YAML DSL."""

    name: str
    description: str = ""
    steps: List[PipelineStep]


class TraceEvent(BaseModel):
    """Structured log for audit and tracing purposes."""

    timestamp: datetime
    trace_id: str
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
