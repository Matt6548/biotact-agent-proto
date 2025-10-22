"""Export utilities for plan and generated artefacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

from fpdf import FPDF
from docx import Document

from .contracts import ExportRequest, GeneratedContent, Plan
from .doc_parser import mask_pii


class Exporter:
    """Export content into multiple formats with optional PII masking."""

    def __init__(self, mask_sensitive: bool = True) -> None:
        self.mask_sensitive = mask_sensitive

    def _mask(self, value: str) -> str:
        return mask_pii(value) if self.mask_sensitive else value

    def export(self, request: ExportRequest) -> Dict[str, Path]:
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results: Dict[str, Path] = {}
        plan = request.plan
        if "json" in request.include_formats:
            results["json"] = self._export_json(plan, request.generated, output_dir)
        if "csv" in request.include_formats:
            results["csv"] = self._export_csv(plan, output_dir)
        if "markdown" in request.include_formats:
            results["markdown"] = self._export_markdown(plan, request.generated, output_dir)
        if "docx" in request.include_formats:
            results["docx"] = self._export_docx(plan, request.generated, output_dir)
        if "pdf" in request.include_formats:
            results["pdf"] = self._export_pdf(plan, request.generated, output_dir)
        return results

    def _export_json(self, plan: Plan, generated: Dict[str, GeneratedContent], directory: Path) -> Path:
        path = directory / "plan.json"
        payload: List[Dict[str, str]] = []
        for item in plan.items:
            key = item.key()
            content = generated.get(key)
            payload.append(
                {
                    "date": item.date.isoformat(),
                    "channel": item.channel,
                    "title": self._mask(item.title),
                    "summary": self._mask(item.summary),
                    "body": self._mask(content.body if content else ""),
                    "sources": content.sources if content else item.sources,
                }
            )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _export_csv(self, plan: Plan, directory: Path) -> Path:
        path = directory / "plan.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "date",
                    "channel",
                    "title",
                    "summary",
                    "catalog_item",
                    "target_audience",
                    "awareness_event",
                    "sources",
                ],
            )
            writer.writeheader()
            for row in plan.to_export_rows():
                writer.writerow({k: self._mask(v) for k, v in row.items()})
        return path

    def _export_markdown(
        self, plan: Plan, generated: Dict[str, GeneratedContent], directory: Path
    ) -> Path:
        path = directory / "plan.md"
        sections: List[str] = ["# Content Plan", ""]
        for item in plan.items:
            key = item.key()
            content = generated.get(key)
            sections.append(f"## {self._mask(item.title)} ({item.date.isoformat()} • {item.channel})")
            sections.append(self._mask(item.summary))
            sections.append("")
            if content:
                sections.append(content.body)
            else:
                sections.append("_No generated content yet._")
            sections.append("")
        path.write_text("\n".join(sections), encoding="utf-8")
        return path

    def _export_docx(self, plan: Plan, generated: Dict[str, GeneratedContent], directory: Path) -> Path:
        path = directory / "plan.docx"
        document = Document()
        document.add_heading("Content Plan", level=0)
        for item in plan.items:
            key = item.key()
            content = generated.get(key)
            document.add_heading(f"{self._mask(item.title)} ({item.date.isoformat()} • {item.channel})", level=1)
            document.add_paragraph(self._mask(item.summary))
            if content:
                for paragraph in content.body.splitlines():
                    document.add_paragraph(self._mask(paragraph))
            else:
                document.add_paragraph("No generated content yet.")
        document.save(path)
        return path

    def _export_pdf(self, plan: Plan, generated: Dict[str, GeneratedContent], directory: Path) -> Path:
        path = directory / "plan.pdf"
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, "Content Plan")
        for item in plan.items:
            key = item.key()
            content = generated.get(key)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(
                0,
                8,
                f"{self._mask(item.title)} ({item.date.isoformat()} • {item.channel})",
            )
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 6, self._mask(item.summary))
            if content:
                pdf.set_font("Helvetica", size=10)
                pdf.multi_cell(0, 5, content.body)
            else:
                pdf.multi_cell(0, 5, "No generated content yet.")
            pdf.ln(4)
        pdf.output(str(path))
        return path
