# Agent Platform

A modular agent platform for orchestrating document parsing, planning, content generation,
and export workflows. The platform supports declarative pipelines, plugin skills, and a
pluggable LLM layer with OpenAI/Ollama/Offline backends. It is designed as a production-ready
foundation for startups exploring AI-assisted editorial or marketing automation.

```
+--------------------+     +----------------+     +------------------+     +----------------+
| Document Parser    | --> | Planner        | --> | Writer Agents     | --> | Exporter        |
| (DOCX/PDF/Text)    |     | (cadence, RAG) |     | (RAG + LLM)       |     | (JSON/MD/PDF)   |
+--------------------+     +----------------+     +------------------+     +----------------+
         |                        |                        |                          |
         v                        v                        v                          v
   Tool Registry           Contracts/RAG             Skills & DSL               Structured Logs
```

## Features

- **Modular architecture** with separate modules for parsing, planning, generation, export, and
  RAG retrieval.
- **Pipeline DSL** defined in YAML (`pipelines/example.yml`) to compose workflows via `documents.parse`,
  `plan.schedule`, `content.generate`, and `export.write` steps.
- **LLM abstraction layer** supporting OpenAI, Ollama, and an offline fallback with retries,
  exponential backoff, and cost tracing.
- **RAG engine** indexing local corpora and providing citations that flow into exports and
  verification reports.
- **Structured contracts** using Pydantic models for validation across modules and skills.
- **Plugin skills** (`skills/`) with guidance and sample implementation to extend platform
  capabilities.
- **Exports** to JSON, Markdown, DOCX, and PDF with PII masking and a Sources section.
- **Audit logging** with JSON events persisted to `logs/audit.log`.
- **CI pipeline** executing linting (Ruff, Black, Isort) and pytest-based tests.

## Getting Started

### Installation

```bash
poetry install
poetry run python main.py --help
```

Copy `.env.example` to `.env` and configure API keys when integrating with hosted LLMs. By
default the offline provider is used which keeps the platform fully runnable without
external connectivity.

### CLI Examples

```bash
python main.py run --pipeline pipelines/example.yml --input samples/inputs/project_brief.md
python main.py plan --days 7 --document data/corpus/knowledge_base.txt
python main.py generate --days 4 --tone inspirational --document data/corpus/brand_story.txt
python main.py export --output-dir outputs/demo --format json --format markdown
python main.py eval --document data/corpus/knowledge_base.txt
```

`plan`, `generate`, and `export` commands construct ephemeral pipelines behind the scenes,
so they can be customised with additional `--document` inputs and channel lists.

### Pipeline DSL

Pipelines are defined with a list of steps referencing registered tools:

```yaml
name: demo-pipeline
steps:
  - name: parse-documents
    uses: documents.parse
    with_config:
      documents:
        - path: data/corpus/knowledge_base.txt
          type: text
          label: knowledge
  - name: schedule-window
    uses: plan.schedule
    with_config:
      start_date: 2025-01-01
      end_date: 2025-01-07
      channels: [blog, email, instagram]
  - name: generate-articles
    uses: content.generate
    with_config:
      tone_of_voice: confident
  - name: export-artifacts
    uses: export.write
    with_config:
      output_dir: samples/outputs/pipeline_run
      formats: [json, markdown]
```

Run the pipeline with `python main.py run --pipeline pipelines/example.yml` to generate demo artefacts.

## Contracts and Skills

- Contracts live in `agent/contracts.py` and define typed models for documents, plans,
  generation requests, and exports.
- Custom skills reside in `skills/`. Each skill ships with a `skill.yaml` manifest, a `run.py`
  entry point, and optional tests. The sample skill demonstrates using the shared LLM client
  to produce an offline summary while remaining fully testable.

## Demo Artifacts

- `samples/inputs/project_brief.md` – launch brief used for demos.
- `samples/outputs/pipeline_plan.json` – generated plan snapshot.
- `samples/outputs/pipeline_markdown.md` – Markdown export with citations.
- `samples/screenshots/` – add CLI/UI screenshots as the platform evolves.

## Extending the Platform

1. **Add corpora**: place additional knowledge files under `data/corpus/` for RAG.
2. **Create skills**: scaffold a directory in `skills/` and register tools in pipelines.
3. **Connect new exporters**: extend `agent/exporter.py` to support CMS or database sinks.
4. **Integrate web UI**: prototype Streamlit or Gradio experiences in `webui/app.py`.
5. **Automate**: describe additional pipelines via YAML and run them through CI or cron jobs.

## Testing and Quality

```bash
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
poetry run pytest
```

The GitHub Actions workflow (`.github/workflows/ci.yml`) executes the same commands on
push and pull requests to ensure consistent quality.
