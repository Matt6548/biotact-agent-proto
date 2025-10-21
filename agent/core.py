"""Execution core coordinating pipeline steps and audit logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import yaml

from config import get_settings

from .contracts import (
    AwarenessEvent,
    DocumentInput,
    ExportRequest,
    GenerationRequest,
    PipelineDefinition,
    Plan,
    PlanRequest,
    TraceEvent,
)
from .doc_parser import DocumentParser
from .exporter import Exporter
from .generator import ContentGenerator
from .llm_client import LLMClient
from .planner import Planner
from .rag import RAGEngine
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentCore:
    """Coordinates parsing, planning, generation, and export."""

    def __init__(
        self,
        parser: DocumentParser | None = None,
        rag: RAGEngine | None = None,
        llm: LLMClient | None = None,
        exporter: Exporter | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        settings = get_settings()
        self.parser = parser or DocumentParser()
        self.rag = rag or RAGEngine()
        self.llm = llm or LLMClient()
        self.generator = ContentGenerator.with_defaults(self.rag, self.llm)
        self.exporter = exporter or Exporter()
        self.registry = registry or ToolRegistry()
        self.trace_id = uuid4().hex
        self.audit_path = Path(settings.audit_log_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.registry.register("documents.parse", self._tool_parse)
        self.registry.register("plan.schedule", self._tool_plan)
        self.registry.register("content.generate", self._tool_generate)
        self.registry.register("export.write", self._tool_export)

    def _log(self, level: str, message: str, **details: Any) -> None:
        event = TraceEvent(
            timestamp=datetime.utcnow(),
            trace_id=self.trace_id,
            level=level,
            message=message,
            details=details,
        )
        payload = event.model_dump()
        payload["timestamp"] = event.timestamp.isoformat() + "Z"
        logger.log(getattr(logging, level), message, extra={"trace_id": self.trace_id, **details})
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def run_pipeline(
        self, definition: PipelineDefinition, initial_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        state: Dict[str, Any] = {"trace_id": self.trace_id}
        if initial_state:
            state.update(initial_state)
        for step in definition.steps:
            tool = self.registry.get(step.uses)
            self._log("INFO", f"Executing step {step.name}", config=step.with_config)
            result = tool(state=state, **step.with_config)
            if isinstance(result, dict):
                state.update(result)
            self._log("INFO", f"Completed step {step.name}", keys=list(result.keys()) if isinstance(result, dict) else [])
        return state

    def _tool_parse(self, state: Dict[str, Any], **config: Any) -> Dict[str, Any]:
        raw_inputs = config.get("documents") or state.get("documents") or []
        inputs = [
            doc if isinstance(doc, DocumentInput) else DocumentInput.model_validate(doc)
            for doc in raw_inputs
        ]
        parsed = self.parser.parse(inputs)
        self.rag.index(parsed)
        catalog = self.parser.extract_catalog_from_many(parsed)
        self._log("INFO", "Parsed documents", documents=len(parsed), catalog=len(catalog))
        return {"parsed_documents": parsed, "catalog": catalog}

    def _tool_plan(self, state: Dict[str, Any], **config: Any) -> Dict[str, Any]:
        request_data = dict(config)
        catalog = state.get("catalog", {})
        events_data = request_data.pop("awareness_events", config.get("awareness_events", []))
        if "channels" not in request_data and state.get("plan_request"):
            request_data["channels"] = state["plan_request"].channels
        plan_request = PlanRequest.model_validate(request_data)
        events = [AwarenessEvent.model_validate(item) for item in events_data]
        planner = Planner(catalog=catalog, awareness_events=events)
        plan = planner.build_plan(plan_request)
        self._log("INFO", "Plan generated", items=len(plan.items))
        return {"plan_request": plan_request, "plan": plan}

    def _tool_generate(self, state: Dict[str, Any], **config: Any) -> Dict[str, Any]:
        plan: Plan = state["plan"]
        generation_results: Dict[str, Any] = {}
        verification_results: Dict[str, Any] = {}
        for item in plan.items:
            request_payload = {**config, "plan_item": item}
            generation_request = GenerationRequest.model_validate(request_payload)
            content, report = self.generator.generate(generation_request)
            generation_results[item.key()] = content
            verification_results[item.key()] = report
        self._log("INFO", "Content generated", count=len(generation_results))
        return {"generated": generation_results, "verification_reports": verification_results}

    def _tool_export(self, state: Dict[str, Any], **config: Any) -> Dict[str, Any]:
        plan: Plan = state["plan"]
        generated = state.get("generated", {})
        request_payload = {
            "plan": plan,
            "generated": generated,
            "output_dir": config.get("output_dir", "outputs"),
            "include_formats": config.get("formats", ["json", "markdown", "pdf", "docx"]),
        }
        export_request = ExportRequest.model_validate(request_payload)
        paths = self.exporter.export(export_request)
        self._log("INFO", "Exports created", formats=list(paths))
        return {"exports": paths}


def load_pipeline(path: Path) -> PipelineDefinition:
    """Load a pipeline definition from YAML."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PipelineDefinition.model_validate(data)
