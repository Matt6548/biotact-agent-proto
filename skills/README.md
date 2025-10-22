# Skills Extension Guide

Skills allow teams to add domain-specific automations to the platform. A skill contains a
`skill.yaml` manifest describing its inputs/outputs and a Python module implementing the
logic. Tests can live under `tests/` to validate the behaviour.

```text
skills/
  sample_skill/
    skill.yaml       # Metadata and I/O schema
    run.py           # Entry point executed by the platform
    tests/           # Pytest-based verification
```

To register a new skill:

1. Create a directory under `skills/` with your skill name.
2. Implement `run(payload: dict) -> dict` that returns serialisable data.
3. Use `agent.contracts` models for validation where appropriate.
4. Document usage examples in `skill.yaml`.

Skills can call the shared `LLMClient`, `RAGEngine`, or export utilities. They should avoid
side effects and return rich metadata so downstream pipelines can reason about outputs.
