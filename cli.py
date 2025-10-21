"""Command line interface for the agent platform."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import typer
from rich import print

from agent.contracts import DocumentInput, PipelineDefinition, PipelineStep
from agent.core import AgentCore, load_pipeline
from agent.doc_parser import convert_docx_directory

app = typer.Typer(add_completion=False, help="Agent Platform CLI")


def _infer_document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"


def _document_inputs(paths: List[Path]) -> List[DocumentInput]:
    return [
        DocumentInput(path=str(path), type=_infer_document_type(path), label=path.stem)
        for path in paths
    ]


@app.command()
def run(
    pipeline: Path = typer.Option(
        ..., "--pipeline", "-p", help="Path to pipeline YAML", exists=True, dir_okay=False
    ),
    context: Optional[Path] = typer.Option(None, "--context", "-c", help="Optional context JSON/YAML"),
    input_paths: List[Path] = typer.Option(
        [],
        "--input",
        "-i",
        help="Documents injected into pipeline state",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Execute a declarative pipeline."""

    definition = load_pipeline(pipeline)
    initial_state = {}
    if input_paths:
        initial_state["documents"] = _document_inputs(input_paths)
    if context:
        text = context.read_text(encoding="utf-8")
        try:
            context_data = json.loads(text)
        except json.JSONDecodeError:
            import yaml

            context_data = yaml.safe_load(text)
        if context_data:
            initial_state.update(context_data)
    core = AgentCore()
    result = core.run_pipeline(definition, initial_state=initial_state)
    exports = result.get("exports")
    if exports:
        print("[green]Exports created:[/green]")
        for fmt, path in exports.items():
            print(f" • {fmt}: {path}")
    else:
        print("[yellow]Pipeline completed with no exports.[/yellow]")


@app.command()
def parse(directory: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Convert all DOCX files in a directory to text for inspection."""

    created = convert_docx_directory(directory)
    if not created:
        print("[yellow]No DOCX files discovered.[/yellow]")
    else:
        print("[green]Generated text files:[/green]")
        for path in created:
            print(f" • {path}")


@app.command()
def plan(
    days: int = typer.Option(7, min=1, help="Number of days to plan"),
    start: Optional[date] = typer.Option(None, help="Start date; defaults to today"),
    cadence: int = typer.Option(2, min=1, help="Cadence in days"),
    channel: List[str] = typer.Option(
        ["blog", "email", "instagram"], "--channel", "-c", help="Channels to rotate"
    ),
    document: List[Path] = typer.Option([], "--document", "-d", exists=True, help="Reference documents"),
    output: Optional[Path] = typer.Option(None, help="Optional path to write plan JSON"),
) -> None:
    """Generate a schedule for the requested horizon."""

    start_date = start or date.today()
    end_date = start_date + timedelta(days=days - 1)
    documents = _document_inputs(document)
    pipeline = PipelineDefinition(
        name="ad-hoc-plan",
        steps=[
            PipelineStep(name="parse", uses="documents.parse", with_config={}),
            PipelineStep(
                name="plan",
                uses="plan.schedule",
                with_config={
                    "start_date": start_date,
                    "end_date": end_date,
                    "channels": channel,
                    "cadence_days": cadence,
                },
            ),
        ],
    )
    core = AgentCore()
    state = core.run_pipeline(pipeline, initial_state={"documents": documents})
    plan_obj = state.get("plan")
    if not plan_obj:
        print("[red]Plan generation failed.[/red]")
        raise typer.Exit(code=1)
    print("[green]Planned items:[/green]")
    for item in plan_obj.items:
        print(
            f" • {item.date.isoformat()} | {item.channel} | {item.title}"
        )
    if output:
        payload = [item.model_dump() for item in plan_obj.items]
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[blue]Plan written to {output}[/blue]")


@app.command()
def generate(
    days: int = typer.Option(7, min=1),
    start: Optional[date] = typer.Option(None),
    channel: List[str] = typer.Option(["blog", "email", "instagram"], "--channel", "-c"),
    document: List[Path] = typer.Option([], "--document", "-d", exists=True),
    tone: str = typer.Option("informative", help="Tone of voice"),
    include_call_to_action: bool = typer.Option(True, help="Include CTA"),
) -> None:
    """Plan and generate content in a single run."""

    start_date = start or date.today()
    end_date = start_date + timedelta(days=days - 1)
    documents = _document_inputs(document)
    pipeline = PipelineDefinition(
        name="ad-hoc-generate",
        steps=[
            PipelineStep(name="parse", uses="documents.parse", with_config={}),
            PipelineStep(
                name="plan",
                uses="plan.schedule",
                with_config={
                    "start_date": start_date,
                    "end_date": end_date,
                    "channels": channel,
                },
            ),
            PipelineStep(
                name="generate",
                uses="content.generate",
                with_config={
                    "tone_of_voice": tone,
                    "include_call_to_action": include_call_to_action,
                },
            ),
        ],
    )
    core = AgentCore()
    state = core.run_pipeline(pipeline, initial_state={"documents": documents})
    generated = state.get("generated", {})
    print(f"[green]Generated {len(generated)} artefacts.[/green]")
    for key, content in generated.items():
        print(f"[bold]{key}[/bold]: {content.title} -> {content.llm_model}")


@app.command()
def export(
    pipeline: Optional[Path] = typer.Option(None, help="Pipeline to execute before export"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir"),
    document: List[Path] = typer.Option([], "--document", "-d", exists=True),
    formats: List[str] = typer.Option(["json", "markdown", "pdf", "docx"], "--format"),
) -> None:
    """Export artefacts using optional pipeline or ad-hoc steps."""

    core = AgentCore()
    initial_state = {"documents": _document_inputs(document)}
    if pipeline:
        definition = load_pipeline(pipeline)
    else:
        definition = PipelineDefinition(
            name="ad-hoc-export",
            steps=[
                PipelineStep(name="parse", uses="documents.parse", with_config={}),
                PipelineStep(
                    name="plan",
                    uses="plan.schedule",
                    with_config={
                        "start_date": date.today(),
                        "end_date": date.today() + timedelta(days=6),
                        "channels": ["blog", "email", "instagram"],
                    },
                ),
                PipelineStep(name="generate", uses="content.generate", with_config={}),
                PipelineStep(
                    name="export",
                    uses="export.write",
                    with_config={"output_dir": output_dir, "formats": formats},
                ),
            ],
        )
    state = core.run_pipeline(definition, initial_state=initial_state)
    exports = state.get("exports", {})
    if not exports:
        print("[yellow]No exports produced.[/yellow]")
    else:
        print("[green]Exports:[/green]")
        for fmt, path in exports.items():
            print(f" • {fmt}: {path}")


@app.command()
def eval(pipeline: Optional[Path] = typer.Option(None), document: List[Path] = typer.Option([], "--document", "-d", exists=True)) -> None:
    """Evaluate verification reports by executing a pipeline."""

    core = AgentCore()
    initial_state = {"documents": _document_inputs(document)}
    if pipeline:
        definition = load_pipeline(pipeline)
    else:
        definition = PipelineDefinition(
            name="ad-hoc-eval",
            steps=[
                PipelineStep(name="parse", uses="documents.parse", with_config={}),
                PipelineStep(
                    name="plan",
                    uses="plan.schedule",
                    with_config={
                        "start_date": date.today(),
                        "end_date": date.today() + timedelta(days=6),
                        "channels": ["blog", "email", "instagram"],
                    },
                ),
                PipelineStep(name="generate", uses="content.generate", with_config={}),
            ],
        )
    state = core.run_pipeline(definition, initial_state=initial_state)
    reports = state.get("verification_reports", {})
    if not reports:
        print("[yellow]No verification reports available.[/yellow]")
        return
    passed = sum(1 for report in reports.values() if report.passed)
    print(f"[green]{passed}/{len(reports)} items passed automated verification.[/green]")
    for key, report in reports.items():
        if not report.passed:
            print(f"[red]{key} issues:[/red] {'; '.join(report.issues)}")
        if report.warnings:
            print(f"[yellow]{key} warnings:[/yellow] {'; '.join(report.warnings)}")


if __name__ == "__main__":
    app()
