"""Content generation orchestrating RAG, LLM writing, and verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from jinja2 import Template

from config import get_settings

from .contracts import GeneratedContent, GenerationRequest, PlanItem, VerificationReport
from .llm_client import LLMClient
from .rag import RAGChunk, RAGEngine


SYSTEM_PROMPT = """You are the Writer agent for {{ project_name }}. Craft concise, factual content.
You always cite sources in the `Sources` section using the format [label]."""

CALL_TO_ACTION = """Next steps: Encourage readers to take a measurable action aligned with the plan."""


@dataclass
class ResearchAgent:
    """Retrieves supporting passages for the writer."""

    rag: RAGEngine

    def gather(self, plan_item: PlanItem, top_k: int = 3) -> List[Tuple[RAGChunk, float]]:
        query = f"{plan_item.title} {plan_item.summary}"
        return self.rag.search(query, top_k=top_k)


@dataclass
class WriterAgent:
    """Composes content using the LLM client."""

    llm: LLMClient

    def compose(
        self,
        request: GenerationRequest,
        references: List[Tuple[RAGChunk, float]],
    ) -> GeneratedContent:
        settings = get_settings()
        plan_item = request.plan_item
        context_blocks = [f"[{idx + 1}] {chunk.text}" for idx, (chunk, _) in enumerate(references)]
        citations = [chunk.source for chunk, _ in references]
        context_text = "\n\n".join(context_blocks)
        prompt_template = Template(
            """Task: Create {{ format_desc }} for channel {{ channel }} on {{ date }}.
Plan summary: {{ summary }}.
Catalogue focus: {{ catalog_item }}.
Tone of voice: {{ tone }}.
Context:
{{ context }}
{% if cta %}Include a short call to action referencing: {{ cta }}.{% endif %}
Provide markdown formatted output with sections: Overview, Key Points, Audience, Sources.
"""
        )
        prompt = prompt_template.render(
            format_desc="long-form article" if request.format == "long" else "short update",
            channel=plan_item.channel,
            date=plan_item.date.isoformat(),
            summary=plan_item.summary,
            catalog_item=plan_item.catalog_item or "General insight",
            tone=request.tone_of_voice,
            context=context_text or "No context provided.",
            cta=CALL_TO_ACTION if request.include_call_to_action else "",
        )
        system_prompt = Template(SYSTEM_PROMPT).render(project_name=settings.project_name)
        result = self.llm.generate(prompt, system=system_prompt)
        bullet_points = plan_item.summary.split("; ")
        body = result.content
        if "Sources" not in body:
            sources_block = "\n\nSources:\n" + "\n".join(
                f"- [{idx + 1}] {citation}" for idx, citation in enumerate(citations)
            )
            body = body.strip() + sources_block
        return GeneratedContent(
            title=plan_item.title,
            body=body,
            bullet_points=bullet_points,
            sources=citations,
            citations=[f"[{idx + 1}]" for idx in range(len(citations))],
            llm_model=result.model,
            cost_usd=result.cost,
        )


@dataclass
class VerifierAgent:
    """Performs lightweight quality checks on generated content."""

    def review(self, content: GeneratedContent) -> VerificationReport:
        issues: List[str] = []
        warnings: List[str] = []
        if not content.sources:
            warnings.append("No sources cited by writer agent")
        if "Sources" not in content.body:
            issues.append("Body missing Sources section")
        if len(content.body) < 100:
            warnings.append("Generated body is very short")
        passed = not issues
        return VerificationReport(passed=passed, issues=issues, warnings=warnings)


@dataclass
class ContentGenerator:
    """High-level facade coordinating research, writing, and verification."""

    research_agent: ResearchAgent
    writer_agent: WriterAgent
    verifier_agent: VerifierAgent

    def generate(self, request: GenerationRequest) -> Tuple[GeneratedContent, VerificationReport]:
        references = self.research_agent.gather(request.plan_item)
        content = self.writer_agent.compose(request, references)
        report = self.verifier_agent.review(content)
        return content, report

    @classmethod
    def with_defaults(cls, rag: RAGEngine | None = None, llm: LLMClient | None = None) -> "ContentGenerator":
        rag_engine = rag or RAGEngine()
        llm_client = llm or LLMClient()
        research = ResearchAgent(rag_engine)
        writer = WriterAgent(llm_client)
        verifier = VerifierAgent()
        return cls(research_agent=research, writer_agent=writer, verifier_agent=verifier)
